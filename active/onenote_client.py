"""
OneNote Client for Hybrid Operations Backend

Handles OneNote page content updates via Microsoft Graph API using
the PATCH-append pattern with HTML sanitization. Uses optimistic
concurrency control via @odata.etag for conflict detection.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from onenote_html_sanitizer import sanitize_html, build_append_patch

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class ConcurrentEditError(Exception):
    """Raised when a OneNote page update fails due to concurrent modification."""
    pass


class OneNoteUpdateError(Exception):
    """Raised when a OneNote page update fails for non-concurrency reasons."""
    pass


class OneNoteClient:
    """
    Manages OneNote page updates via Microsoft Graph API.

    Uses the PATCH-append pattern (action="append", position="after",
    target="body") instead of fetch-modify-replace. HTML is sanitized
    through onenote_html_sanitizer before sending to avoid 400 errors.
    """

    def __init__(
        self,
        graph_client,
        config_loader: Callable[[str], Any],
    ) -> None:
        """
        Initialize OneNote client.

        Args:
            graph_client: Authenticated async Graph API client with
                get/post/patch methods. Handles 401 refresh automatically.
            config_loader: Callable that resolves dotted config keys to values.
        """
        self._graph = graph_client
        self._notebook_id = config_loader("microsoft.onenote_notebook_id")
        logger.info("OneNoteClient initialized for notebook %s", self._notebook_id)

    async def append_state_summary(
        self, page_id: str, summary_html: str
    ) -> Dict[str, Any]:
        """
        Append an AI state summary to a OneNote page.

        Uses the PATCH-append pattern to add content without fetching
        or replacing the full page. HTML is sanitized before sending.
        On 412 Precondition Failed, retries exactly once.

        Args:
            page_id: The Graph API page identifier (UUID, not URL).
            summary_html: HTML content to append as the state summary.

        Returns:
            Dict with 'success', 'page_id', and 'timestamp' keys.

        Raises:
            ConcurrentEditError: If the page was modified by another editor
                and the single retry also fails with 412.
            OneNoteUpdateError: If the update fails for any other reason.
        """
        logger.info("Appending state summary to page %s", page_id)

        timestamp = datetime.now(timezone.utc).isoformat()
        timestamped_html = (
            f'<div data-id="ai-state-{timestamp}">'
            f'<p><strong>AI Summary — {timestamp}</strong></p>'
            f'{summary_html}'
            f'</div>'
        )

        patch_body = build_append_patch(timestamped_html)

        try:
            await self._patch_page(page_id, patch_body)
        except ConcurrentEditError:
            logger.warning(
                "Concurrent edit detected on page %s, retrying once", page_id
            )
            try:
                await self._patch_page(page_id, patch_body)
            except ConcurrentEditError:
                logger.error(
                    "Persistent concurrent edit conflict on page %s", page_id
                )
                raise

        logger.info("State summary appended to page %s", page_id)

        return {
            "success": True,
            "page_id": page_id,
            "timestamp": timestamp,
        }

    async def _patch_page(self, page_id: str, patch_body: list) -> None:
        """
        Send a PATCH-append request to a OneNote page.

        Args:
            page_id: The Graph API page identifier.
            patch_body: List of patch action dicts from build_append_patch().

        Raises:
            ConcurrentEditError: On 412 Precondition Failed.
            OneNoteUpdateError: On other errors.
        """
        url = f"{GRAPH_BASE}/me/onenote/pages/{page_id}/content"
        headers = {
            "Content-Type": "application/json",
        }

        try:
            await self._graph.patch(url, headers=headers, data=patch_body)
            logger.debug("PATCH-append to page %s succeeded", page_id)
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if status == 412:
                raise ConcurrentEditError(
                    f"Page {page_id} was modified by another editor"
                ) from exc

            logger.error("Failed to patch page %s: %s", page_id, exc)
            raise OneNoteUpdateError(
                f"Failed to patch OneNote page {page_id}: {exc}"
            ) from exc

    # DEPRECATED: Retained for potential read-only inspection use.
    async def _fetch_page(self, page_id: str) -> tuple:
        """
        Fetch a OneNote page's content and etag.

        Args:
            page_id: The Graph API page identifier.

        Returns:
            Tuple of (html_content: str, etag: str).

        Raises:
            OneNoteUpdateError: If the fetch request fails.
        """
        try:
            meta_url = f"{GRAPH_BASE}/me/onenote/pages/{page_id}"
            meta_resp = await self._graph.get(meta_url)

            if isinstance(meta_resp, dict):
                etag = meta_resp.get("@odata.etag", "")
            elif hasattr(meta_resp, "headers"):
                etag = meta_resp.headers.get("ETag", "")
            else:
                etag = ""

            content_url = f"{GRAPH_BASE}/me/onenote/pages/{page_id}/content"
            content_resp = await self._graph.get(content_url)

            if hasattr(content_resp, "text"):
                html = content_resp.text
            elif isinstance(content_resp, bytes):
                html = content_resp.decode("utf-8")
            elif isinstance(content_resp, str):
                html = content_resp
            else:
                html = str(content_resp)

            logger.debug("Fetched page %s (etag=%s)", page_id, etag)
            return html, etag

        except Exception as exc:
            logger.error("Failed to fetch page %s: %s", page_id, exc)
            raise OneNoteUpdateError(
                f"Failed to fetch OneNote page {page_id}: {exc}"
            ) from exc
