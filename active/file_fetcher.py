"""
Hybrid File Fetcher for Operations Backend

Retrieves file content as bytes from SharePoint (primary) or Google Drive
(fallback) with circuit breaker protection against API throttling.
"""

import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class FileResolutionError(Exception):
    """Raised when a file cannot be fetched from any available source."""
    pass


class FileTooLargeError(Exception):
    """Raised when a fetched file exceeds the configured size limit."""
    pass


class CircuitState(Enum):
    """Circuit breaker states for SharePoint API resilience."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class _ThrottledError(Exception):
    """Internal sentinel for SharePoint 429 responses."""
    pass


class HybridFileFetcher:
    """
    Fetches file content as bytes from SharePoint or Google Drive.

    Implements a circuit breaker pattern to handle SharePoint throttling (429)
    and transient failures. When SharePoint becomes unreliable, automatically
    falls through to Google Drive while the circuit is open. After a cooldown
    period, a single test request determines whether to restore SharePoint.

    All fetch operations return raw bytes, never URLs or streams.
    """

    def __init__(
        self,
        graph_client,
        gdrive_client,
        config_loader: Callable[[str], Any],
        file_session=None,
    ) -> None:
        """
        Initialize hybrid file fetcher with circuit breaker defaults.

        Args:
            graph_client: Authenticated async Graph API client with get method.
                Handles 401 refresh automatically.
            gdrive_client: Legacy Google Drive client with download(path)
                method that returns bytes.
            config_loader: Callable that resolves dotted config keys to values.
            file_session: Optional httpx.AsyncClient with extended timeout
                for large file downloads. When provided, SharePoint downloads
                use this session instead of the graph client's default session.
        """
        self._graph = graph_client
        self._gdrive = gdrive_client
        self._file_session = file_session
        self._site_id = config_loader("sharepoint.site_id")
        self._max_file_size = (
            config_loader("microsoft.max_file_size_mb") or 10
        ) * 1024 * 1024
        self._cooldown_seconds = (
            config_loader("microsoft.circuit_breaker_cooldown_seconds") or 300
        )

        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._failure_threshold = 3
        self._cooldown_until: Optional[datetime] = None

        logger.info(
            "HybridFileFetcher initialized (max_size=%dMB, cooldown=%ds)",
            self._max_file_size // (1024 * 1024),
            self._cooldown_seconds,
        )

    async def fetch(self, file_ref: Dict[str, Any]) -> bytes:
        """
        Fetch file content as bytes from the best available source.

        Attempts SharePoint first when the circuit is closed, falling through
        to Google Drive on failure or when the circuit is open. Enforces a
        maximum file size to prevent memory exhaustion.

        Args:
            file_ref: Dict containing optional 'sharepoint_file_id' and/or
                'google_drive_path' keys identifying the file.

        Returns:
            File content as bytes.

        Raises:
            FileTooLargeError: If the file exceeds the configured size limit.
            FileResolutionError: If the file cannot be fetched from any source.
        """
        sp_file_id = file_ref.get("sharepoint_file_id")
        gdrive_path = file_ref.get("google_drive_path")

        if not sp_file_id and not gdrive_path:
            raise FileResolutionError(
                "file_ref must contain 'sharepoint_file_id' and/or "
                "'google_drive_path'"
            )

        errors: list[str] = []

        if sp_file_id and self._should_try_sharepoint():
            try:
                content = await self._fetch_sharepoint(sp_file_id)
                self._record_success()
                self._enforce_size_limit(content, f"SharePoint:{sp_file_id}")
                return content
            except FileTooLargeError:
                raise
            except _ThrottledError:
                self._open_circuit()
                errors.append("SharePoint: throttled (429)")
                logger.warning(
                    "SharePoint throttled for file %s, falling through to "
                    "Google Drive",
                    sp_file_id,
                )
            except Exception as exc:
                self._record_failure()
                errors.append(f"SharePoint: {exc}")
                logger.warning(
                    "SharePoint fetch failed for %s: %s, trying Google Drive",
                    sp_file_id,
                    exc,
                )
        elif sp_file_id and not self._should_try_sharepoint():
            errors.append("SharePoint: circuit open")

        if gdrive_path:
            try:
                content = self._fetch_gdrive(gdrive_path)
                self._enforce_size_limit(content, f"GDrive:{gdrive_path}")
                return content
            except FileTooLargeError:
                raise
            except Exception as exc:
                errors.append(f"Google Drive: {exc}")
                logger.error(
                    "Google Drive fetch failed for %s: %s", gdrive_path, exc
                )

        raise FileResolutionError(
            f"Could not fetch file from any source: {'; '.join(errors)}"
        )

    def get_health_status(self) -> Dict[str, Any]:
        """
        Return the current health status of the file fetcher.

        Returns:
            Dict with 'circuit_state', 'failure_count', 'cooldown_until',
            and 'sharepoint_healthy' keys.
        """
        return {
            "circuit_state": self._circuit_state.value,
            "failure_count": self._failure_count,
            "cooldown_until": (
                self._cooldown_until.isoformat()
                if self._cooldown_until
                else None
            ),
            "sharepoint_healthy": self._circuit_state == CircuitState.CLOSED,
        }

    # ── SharePoint fetch ──────────────────────────────────────────────────

    async def _fetch_sharepoint(self, file_id: str) -> bytes:
        """
        Fetch file content from SharePoint via Graph API.

        Args:
            file_id: SharePoint drive item ID.

        Returns:
            File content as bytes.

        Raises:
            _ThrottledError: If the API returns 429.
            Exception: On other failures.
        """
        url = (
            f"{GRAPH_BASE}/sites/{self._site_id}/drive/items/"
            f"{file_id}/content"
        )

        try:
            if self._file_session is not None:
                # Use dedicated file download session (5min timeout)
                headers = await self._graph.get_auth_headers()
                resp = await self._file_session.get(
                    url, headers=headers, follow_redirects=True
                )
                if resp.status_code == 429:
                    raise _ThrottledError("SharePoint returned 429")
                resp.raise_for_status()
                return resp.content

            resp = await self._graph.get(url, stream=True)
        except _ThrottledError:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if status == 429:
                raise _ThrottledError("SharePoint returned 429") from exc
            raise

        if hasattr(resp, "status_code") and resp.status_code == 429:
            raise _ThrottledError("SharePoint returned 429")

        if hasattr(resp, "content"):
            return resp.content
        if isinstance(resp, bytes):
            return resp

        raise FileResolutionError(
            f"Unexpected SharePoint response type: {type(resp)}"
        )

    # ── Google Drive fetch ────────────────────────────────────────────────

    def _fetch_gdrive(self, path: str) -> bytes:
        """
        Fetch file content from Google Drive.

        Args:
            path: Google Drive file path.

        Returns:
            File content as bytes.

        Raises:
            FileResolutionError: If the download returns an unexpected type.
        """
        content = self._gdrive.download(path)

        if isinstance(content, bytes):
            return content
        if hasattr(content, "read"):
            return content.read()

        raise FileResolutionError(
            f"Google Drive returned unexpected type: {type(content)}"
        )

    # ── Size enforcement ──────────────────────────────────────────────────

    def _enforce_size_limit(self, content: bytes, source: str) -> None:
        """
        Enforce the maximum file size limit.

        Args:
            content: File content bytes to check.
            source: Human-readable source label for error messages.

        Raises:
            FileTooLargeError: If content exceeds the configured limit.
        """
        if len(content) > self._max_file_size:
            size_mb = len(content) / (1024 * 1024)
            limit_mb = self._max_file_size / (1024 * 1024)
            raise FileTooLargeError(
                f"File from {source} is {size_mb:.1f}MB, "
                f"exceeds {limit_mb:.0f}MB limit"
            )

    # ── Circuit breaker ───────────────────────────────────────────────────

    def _should_try_sharepoint(self) -> bool:
        """Determine whether the circuit allows a SharePoint request."""
        if self._circuit_state == CircuitState.CLOSED:
            return True

        if self._circuit_state == CircuitState.OPEN:
            if (
                self._cooldown_until
                and datetime.now(timezone.utc) >= self._cooldown_until
            ):
                logger.info("Circuit moving to HALF_OPEN for test request")
                self._circuit_state = CircuitState.HALF_OPEN
                return True
            return False

        return True

    def _record_success(self) -> None:
        """Record a successful SharePoint request and close the circuit."""
        if self._circuit_state == CircuitState.HALF_OPEN:
            logger.info("Test request succeeded, closing circuit")
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._cooldown_until = None

    def _record_failure(self) -> None:
        """Record a SharePoint failure and potentially open the circuit."""
        self._failure_count += 1

        if self._circuit_state == CircuitState.HALF_OPEN:
            logger.warning(
                "Test request failed in HALF_OPEN, extending cooldown"
            )
            self._open_circuit()
        elif self._failure_count >= self._failure_threshold:
            self._open_circuit()

    def _open_circuit(self) -> None:
        """Open the circuit breaker, starting the cooldown period."""
        self._circuit_state = CircuitState.OPEN
        self._cooldown_until = datetime.now(timezone.utc) + timedelta(
            seconds=self._cooldown_seconds
        )
        logger.warning(
            "Circuit OPEN — SharePoint disabled until %s (failure_count=%d)",
            self._cooldown_until.isoformat(),
            self._failure_count,
        )
