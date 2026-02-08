"""
LLM Router for Mode 4
Routes tasks to the optimal LLM based on capability, cost, and quality scoring.

Routing hierarchy:
    1. Capability table: each task type maps to a preferred model.
    2. Dynamic fallback: Ollama timeout → retry Claude; Claude rate-limit → queue.
    3. Circuit breakers: repeated failures open the circuit for a model.
    4. Cost tracking: per-model token/cost ledger with daily budget enforcement.
    5. Quality scoring: track user corrections to auto-adjust routing weights.

Key principle: User ALWAYS chooses via button for drafts — router only provides
recommendations.  For internal calls (intent classification, data extraction)
the router auto-selects.
"""

import logging
import os
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Capability-based routing table ───────────────────────────────────────────

# Each entry: (preferred_model, timeout_seconds, description)
ROUTING_TABLE: Dict[str, Tuple[str, float, str]] = {
    "intent_classification":       ("ollama/qwen2.5:3b",   2.0,  "Fast local intent detection"),
    "email_draft_simple":          ("ollama/qwen2.5:3b",   5.0,  "Simple email with style injection"),
    "email_draft_complex":         ("claude/sonnet",       10.0,  "Multi-thread context drafts"),
    "data_extraction_structured":  ("gemini/flash",         5.0,  "JSON-mode structured extraction"),
    "data_extraction_unstructured":("claude/sonnet",       10.0,  "Reasoning-heavy extraction"),
    "summarization_long":          ("claude/sonnet",       15.0,  "100k+ context summarisation"),
    "code_generation":             ("claude/opus",         20.0,  "High-quality code generation"),
    "idea_bounce":                 ("kimi/k2",             10.0,  "Creative brainstorming"),
}


# ── Cost estimates per 1K tokens (USD, approximate) ──────────────────────────

_COST_PER_1K = {
    "ollama": 0.0,
    "claude/haiku": 0.00025,
    "claude/sonnet": 0.003,
    "claude/opus": 0.015,
    "gemini/flash": 0.0001,
    "kimi/k2": 0.002,
}


# ── Circuit-breaker helper ───────────────────────────────────────────────────

class _ModelCircuit:
    """Lightweight per-model circuit breaker."""

    def __init__(self, failure_threshold=5, window=60, recovery=120):
        self.failure_threshold = failure_threshold
        self.window = window
        self.recovery = recovery
        self._failures: deque = deque()
        self._open_at: float = 0

    @property
    def is_open(self) -> bool:
        if self._open_at:
            if time.time() - self._open_at > self.recovery:
                self._open_at = 0
                self._failures.clear()
                return False
            return True
        return False

    def record_failure(self):
        now = time.time()
        self._failures.append(now)
        cutoff = now - self.window
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()
        if len(self._failures) >= self.failure_threshold:
            self._open_at = now
            logger.warning("Circuit opened for model")

    def record_success(self):
        if self._open_at:
            self._open_at = 0
            self._failures.clear()


# ── LLMRouter ────────────────────────────────────────────────────────────────

class LLMRouter:
    """
    Routes tasks between Ollama, Claude, Gemini, and Kimi
    based on capability tables, circuit breakers, and quality scores.
    """

    def __init__(self):
        # Keywords for simple/complex detection
        self.simple_task_keywords = [
            'draft', 'rewrite', 'summarize', 'format',
            'meeting request', 'follow up', 'thank you',
            'confirm', 'reschedule', 'w9', 'wiring',
            'invoice', 'receipt', 'acknowledge'
        ]
        self.complex_task_keywords = [
            'complex', 'sensitive', 'negotiate', 'strategy',
            'analyze', 'recommend', 'brainstorm', 'plan',
            'help me figure out', 'what should i', 'advice',
            'legal', 'compliance', 'finra', 'sec', 'audit'
        ]
        self.ambiguous_indicators = [
            'help', 'not sure', 'what should', 'figure out',
            "don't know", 'confused', 'unclear', 'maybe'
        ]

        # Confidence thresholds
        self.high_confidence_threshold = 0.90
        self.medium_confidence_threshold = 0.70

        # Circuit breakers per model
        self._circuits: Dict[str, _ModelCircuit] = defaultdict(
            lambda: _ModelCircuit(failure_threshold=5, window=60, recovery=120)
        )

        # Cost ledger: model -> list of (timestamp, tokens, cost_usd)
        self._cost_log: Dict[str, deque] = defaultdict(lambda: deque(maxlen=5000))

        # Quality scores: model -> list of (timestamp, was_edited)
        self._quality_log: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))

        # Daily budget (USD) — 0 = unlimited
        try:
            self._daily_budget = float(os.getenv("MODE4_DAILY_LLM_BUDGET", "0"))
        except (ValueError, TypeError):
            self._daily_budget = 0

    # ── Capability-based routing ─────────────────────────────────────────

    def route_task(self, task_type: str) -> Tuple[str, float]:
        """
        Return (model_key, timeout) for a task type from the routing table.
        Falls back to ollama if preferred model's circuit is open.
        """
        entry = ROUTING_TABLE.get(task_type)
        if entry is None:
            return ("ollama/qwen2.5:3b", 5.0)

        model, timeout, _ = entry

        # Check circuit breaker
        provider = model.split("/")[0]
        if self._circuits[provider].is_open:
            fallback = self._get_fallback(provider)
            logger.info("Circuit open for %s, falling back to %s", provider, fallback)
            return (fallback, timeout * 1.5)

        # Check daily budget (only for paid models)
        if provider not in ("ollama",) and self._daily_budget > 0:
            spent = self._daily_spend(model)
            if spent >= self._daily_budget:
                logger.warning("Daily budget exceeded for %s ($%.2f/$%.2f)", model, spent, self._daily_budget)
                return ("ollama/qwen2.5:3b", timeout)

        return (model, timeout)

    # ── Dynamic fallback chain ───────────────────────────────────────────

    @staticmethod
    def _get_fallback(failed_provider: str) -> str:
        chain = ["ollama/qwen2.5:3b", "claude/sonnet", "kimi/k2", "gemini/flash"]
        for m in chain:
            if not m.startswith(failed_provider):
                return m
        return "ollama/qwen2.5:3b"

    # ── Recommendation API (user-facing) ─────────────────────────────────

    def get_recommendation(
        self,
        message: str,
        pattern_confidence: float = None,
        sender_known: bool = False,
    ) -> str:
        llm, reason = self.analyze(message, pattern_confidence, sender_known)
        if llm == "ollama":
            if pattern_confidence and pattern_confidence >= self.high_confidence_threshold:
                return f"Ollama ({int(pattern_confidence * 100)}% pattern match - high confidence)"
            elif pattern_confidence and pattern_confidence >= self.medium_confidence_threshold:
                return f"Ollama ({int(pattern_confidence * 100)}% confidence - medium)"
            return "Ollama (simple task detected)"
        elif llm == "claude":
            reason_map = {
                "low_confidence": f"Claude (low pattern confidence - {int((pattern_confidence or 0)*100)}%)",
                "complex_task":   "Claude (complex reasoning needed)",
                "ambiguous":      "Claude (ambiguous request - needs clarification)",
                "compliance":     "Claude (sensitive/compliance topic detected)",
            }
            return reason_map.get(reason, "Claude (recommended for this task)")
        return "Either Ollama or Claude (your choice)"

    def analyze(
        self,
        message: str,
        pattern_confidence: float = None,
        sender_known: bool = False,
    ) -> Tuple[str, str]:
        msg_lower = message.lower()

        if self._has_compliance_keywords(msg_lower):
            return "claude", "compliance"
        if self._is_complex(msg_lower):
            return "claude", "complex_task"
        if self._is_ambiguous(msg_lower):
            return "claude", "ambiguous"

        if pattern_confidence is not None:
            if pattern_confidence >= self.high_confidence_threshold:
                return "ollama", "high_confidence"
            elif pattern_confidence >= self.medium_confidence_threshold:
                return ("ollama" if sender_known else "either"), "medium_confidence"
            return "claude", "low_confidence"

        if self._is_simple(msg_lower):
            return "ollama", "simple_task"
        return "either", "uncertain"

    # ── Cost tracking ────────────────────────────────────────────────────

    def record_call(self, model: str, tokens: int, cost_usd: float, success: bool):
        """Log an API call for cost tracking and circuit breaker updates."""
        provider = model.split("/")[0]
        self._cost_log[model].append((time.time(), tokens, cost_usd))
        if success:
            self._circuits[provider].record_success()
        else:
            self._circuits[provider].record_failure()

    def _daily_spend(self, model: str) -> float:
        today_start = time.time() - (time.time() % 86400)
        return sum(c for ts, _, c in self._cost_log.get(model, []) if ts >= today_start)

    def daily_summary(self) -> Dict[str, Any]:
        """Return today's cost breakdown by model."""
        today_start = time.time() - (time.time() % 86400)
        summary: Dict[str, Any] = {}
        for model, entries in self._cost_log.items():
            today_entries = [(ts, tok, c) for ts, tok, c in entries if ts >= today_start]
            if today_entries:
                summary[model] = {
                    "calls": len(today_entries),
                    "tokens": sum(tok for _, tok, _ in today_entries),
                    "cost_usd": sum(c for _, _, c in today_entries),
                }
        return summary

    # ── Quality scoring ──────────────────────────────────────────────────

    def record_quality(self, model: str, was_edited: bool):
        """Track whether a model's output was edited by the user."""
        self._quality_log[model].append((time.time(), was_edited))

    def quality_scores(self) -> Dict[str, float]:
        """Return edit-rate per model (lower is better)."""
        scores = {}
        for model, entries in self._quality_log.items():
            if entries:
                edit_count = sum(1 for _, edited in entries if edited)
                scores[model] = edit_count / len(entries)
        return scores

    # ── Availability ─────────────────────────────────────────────────────

    def get_availability_status(self) -> Dict[str, bool]:
        status = {"ollama": False, "claude": False, "kimi": False}
        try:
            from ollama_client import OllamaClient
            client = OllamaClient()
            status["ollama"] = client.is_available()
            del client
        except Exception:
            pass
        try:
            from claude_client import ClaudeClient
            client = ClaudeClient()
            status["claude"] = client.is_available()
            del client
        except Exception:
            pass
        try:
            from kimi_client import KimiClient
            client = KimiClient()
            status["kimi"] = client.is_available()
            del client
        except Exception:
            pass
        return status

    def get_fallback_llm(self) -> Optional[str]:
        status = self.get_availability_status()
        for name in ("ollama", "kimi", "claude"):
            if status.get(name):
                return name
        return None

    def get_smart_llm(self) -> Optional[str]:
        status = self.get_availability_status()
        for name in ("kimi", "claude"):
            if status.get(name):
                return name
        return None

    # ── Internal helpers ─────────────────────────────────────────────────

    def _is_simple(self, message: str) -> bool:
        return any(kw in message for kw in self.simple_task_keywords)

    def _is_complex(self, message: str) -> bool:
        return any(kw in message for kw in self.complex_task_keywords)

    def _is_ambiguous(self, message: str) -> bool:
        words = message.split()
        if len(words) < 3:
            return True
        return any(ind in message for ind in self.ambiguous_indicators)

    def _has_compliance_keywords(self, message: str) -> bool:
        compliance_keywords = [
            'finra', 'sec', 'compliance', 'regulatory', 'audit',
            'subpoena', 'legal action', 'investigation', 'lawsuit'
        ]
        return any(kw in message for kw in compliance_keywords)


# ── Routing helper (backward-compatible) ─────────────────────────────────────

def route_draft_request(
    message: str,
    email_data: Dict[str, Any],
    pattern_match: Optional[Dict] = None,
    contact_known: bool = False,
) -> Dict[str, Any]:
    """Route a draft request and return routing decision."""
    router = LLMRouter()

    pattern_confidence = None
    if pattern_match:
        boost = pattern_match.get("confidence_boost", 0)
        keyword_count = pattern_match.get("keyword_matches", 0)
        base = 50
        score = base + boost + (min(keyword_count, 5) * 2)
        if contact_known:
            score += 10
        else:
            score -= 20
        pattern_confidence = max(0, min(100, score)) / 100

    recommended_llm, reason = router.analyze(
        message, pattern_confidence=pattern_confidence, sender_known=contact_known
    )
    recommendation_text = router.get_recommendation(
        message, pattern_confidence=pattern_confidence, sender_known=contact_known
    )

    return {
        "recommended_llm": recommended_llm,
        "recommendation_text": recommendation_text,
        "reason": reason,
        "confidence": pattern_confidence,
        "can_use_ollama": recommended_llm in ("ollama", "either"),
        "should_escalate": recommended_llm == "claude" and reason in ("compliance", "complex_task"),
    }
