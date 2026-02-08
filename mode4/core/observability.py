"""
Observability module for Mode 4.

Provides structured logging, performance metrics, health checks,
circuit breakers, and self-healing utilities — all without external services.

Components:
    StructuredLogger  – JSON-formatted, rotated log files.
    PerformanceTracker – Per-action latency percentiles and cost tracking.
    HealthChecker     – Component connectivity / status checks.
    CircuitBreaker    – Automatic fallback after repeated failures.
"""

import json
import logging
import os
import shutil
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Structured Logger ────────────────────────────────────────────────────────

class StructuredLogger:
    """
    Configures three rotating log files:
        mode4.log         – INFO and above
        mode4_errors.log  – ERROR and above
        mode4_audit.log   – INFO, PII-redacted

    All logs are emitted as single-line JSON for easy parsing.
    """

    MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
    BACKUP_COUNT = 5

    PII_PATTERNS = ["@", "gmail", "phone", "ssn", "token"]

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_dir = log_dir

        self._setup_handler("mode4.log", logging.INFO)
        self._setup_handler("mode4_errors.log", logging.ERROR)
        self._audit_path = os.path.join(log_dir, "mode4_audit.log")

    def _setup_handler(self, filename: str, level: int):
        path = os.path.join(self.log_dir, filename)
        handler = RotatingFileHandler(
            path, maxBytes=self.MAX_BYTES, backupCount=self.BACKUP_COUNT, encoding="utf-8"
        )
        handler.setLevel(level)
        fmt = logging.Formatter("%(message)s")  # JSON lines
        handler.setFormatter(fmt)

        root = logging.getLogger("mode4")
        root.addHandler(handler)

    def audit(self, event: str, **data):
        """Write a PII-redacted audit entry."""
        entry = {"ts": time.time(), "event": event}
        for k, v in data.items():
            entry[k] = self._redact(str(v))
        try:
            with open(self._audit_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    @classmethod
    def _redact(cls, text: str) -> str:
        for pat in cls.PII_PATTERNS:
            if pat in text.lower():
                return "[REDACTED]"
        return text


# ── Performance Tracker ──────────────────────────────────────────────────────

class PerformanceTracker:
    """
    In-memory latency and cost tracker.

    Stores the last 1 000 measurements per action and computes percentiles.
    Optionally persists daily summaries to SQLite.
    """

    MAX_HISTORY = 1000

    def __init__(self, db_manager=None):
        self.db = db_manager
        self._latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.MAX_HISTORY))
        self._costs: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.MAX_HISTORY))
        self._call_counts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)

    @contextmanager
    def track(self, action: str):
        """Context manager to measure latency for *action*."""
        start = time.monotonic()
        error = False
        try:
            yield
        except Exception:
            error = True
            self._error_counts[action] += 1
            raise
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._latencies[action].append(elapsed_ms)
            self._call_counts[action] += 1
            if elapsed_ms > 100:
                logger.debug("Slow action %s: %.1fms", action, elapsed_ms)

    def record_llm_call(self, model: str, tokens: int, cost_usd: float, latency_ms: float, success: bool):
        """Log a single LLM API call."""
        key = f"llm:{model}"
        self._latencies[key].append(latency_ms)
        self._costs[key].append(cost_usd)
        self._call_counts[key] += 1
        if not success:
            self._error_counts[key] += 1

    def percentile(self, action: str, p: int) -> float:
        """Return the p-th percentile latency (ms) for *action*."""
        data = sorted(self._latencies.get(action, []))
        if not data:
            return 0.0
        idx = int(len(data) * p / 100)
        idx = min(idx, len(data) - 1)
        return data[idx]

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of all tracked actions."""
        result = {}
        for action in self._latencies:
            result[action] = {
                "calls": self._call_counts.get(action, 0),
                "errors": self._error_counts.get(action, 0),
                "p50_ms": self.percentile(action, 50),
                "p95_ms": self.percentile(action, 95),
                "p99_ms": self.percentile(action, 99),
            }
            costs = list(self._costs.get(action, []))
            if costs:
                result[action]["total_cost_usd"] = sum(costs)
        return result


# ── Health Checker ───────────────────────────────────────────────────────────

class HealthChecker:
    """
    Run component-level health checks and return a structured report.
    Supports: Ollama, Claude API, Gmail, Sheets, Database.
    """

    def __init__(self, db_manager=None):
        self.db = db_manager

    def check_all(self) -> Dict[str, Dict[str, Any]]:
        """Return health status for each subsystem."""
        return {
            "database": self._check_database(),
            "ollama": self._check_ollama(),
            "claude_api": self._check_claude(),
            "gmail": self._check_gmail(),
            "disk": self._check_disk(),
        }

    def status_text(self) -> str:
        """Human-readable status string for Telegram /status command."""
        checks = self.check_all()
        lines = ["System Health:"]
        for name, info in checks.items():
            icon = "OK" if info.get("ok") else "FAIL"
            detail = info.get("detail", "")
            lines.append(f"  {name}: {icon} {detail}")
        return "\n".join(lines)

    # ── individual checks ────────────────────────────────────────────────

    def _check_database(self) -> Dict[str, Any]:
        if self.db is None:
            return {"ok": False, "detail": "no db_manager"}
        try:
            with self.db.get_connection() as conn:
                conn.execute("SELECT 1")
                # Check WAL mode
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                return {"ok": True, "detail": f"journal_mode={mode}"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    def _check_ollama(self) -> Dict[str, Any]:
        try:
            import ollama
            result = ollama.list()
            models = []
            if hasattr(result, "models"):
                models = [m.model for m in result.models]
            elif isinstance(result, dict) and "models" in result:
                models = [m.get("name", "") for m in result["models"]]
            return {"ok": True, "detail": f"{len(models)} models loaded"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    def _check_claude(self) -> Dict[str, Any]:
        try:
            from m1_config import ANTHROPIC_API_KEY
            if not ANTHROPIC_API_KEY:
                return {"ok": False, "detail": "no API key"}
            return {"ok": True, "detail": "key configured"}
        except ImportError:
            return {"ok": False, "detail": "config not found"}

    def _check_gmail(self) -> Dict[str, Any]:
        try:
            from m1_config import GMAIL_TOKEN_PATH
            if os.path.exists(GMAIL_TOKEN_PATH):
                return {"ok": True, "detail": "token present"}
            return {"ok": False, "detail": "no token"}
        except ImportError:
            return {"ok": False, "detail": "config not found"}

    def _check_disk(self) -> Dict[str, Any]:
        try:
            usage = shutil.disk_usage("/")
            free_gb = usage.free / (1024 ** 3)
            ok = free_gb > 5.0
            return {"ok": ok, "detail": f"{free_gb:.1f} GB free"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}


# ── Circuit Breaker ──────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    Tracks failures for a named service and opens the circuit after
    *failure_threshold* failures within *window_seconds*.

    When open, calls are rejected for *recovery_seconds* before allowing
    a single probe (half-open).
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        window_seconds: float = 60,
        recovery_seconds: float = 120,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.recovery_seconds = recovery_seconds

        self._failures: deque = deque()
        self._state = "closed"          # closed | open | half_open
        self._opened_at: float = 0.0

    @property
    def is_open(self) -> bool:
        if self._state == "closed":
            return False
        if self._state == "open":
            if time.time() - self._opened_at > self.recovery_seconds:
                self._state = "half_open"
                return False  # allow one probe
            return True
        # half_open – let it through
        return False

    def record_success(self):
        if self._state == "half_open":
            self._state = "closed"
            self._failures.clear()
            logger.info("CircuitBreaker[%s]: closed (recovered)", self.name)

    def record_failure(self):
        now = time.time()
        self._failures.append(now)

        # Trim old failures outside window
        cutoff = now - self.window_seconds
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

        if len(self._failures) >= self.failure_threshold:
            self._state = "open"
            self._opened_at = now
            logger.warning(
                "CircuitBreaker[%s]: OPEN after %d failures in %.0fs",
                self.name, len(self._failures), self.window_seconds,
            )

    @property
    def state(self) -> str:
        # re-evaluate for time-based transitions
        if self._state == "open" and time.time() - self._opened_at > self.recovery_seconds:
            self._state = "half_open"
        return self._state
