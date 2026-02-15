"""
OneNote Client for Hybrid Operations Backend

Handles OneNote page content updates via Microsoft Graph API with
optimistic concurrency control. OneNote pages are immutable; updates
require fetch-modify-replace using @odata.etag for conflict detection.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict

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

    Uses optimistic concurrency control with @odata.etag headers to prevent
    silent overwrites when a human and bot edit the same page simultaneously.
    """

    def __init__(
        self,
        graph_client,
        config_loader: Callable[[str], Any],
    ) -> None:
        """
        Initialize OneNote client.

        Args:
            graph_client: Authenticated Graph API client with get/post/patch
                methods. Handles 401 refresh automatically.
            config_loader: Callable that resolves dotted config keys to values.
        """
        self._graph = graph_client
        self._notebook_id = config_loader("microsoft.onenote_notebook_id")
        logger.info("OneNoteClient initialized for notebook %s", self._notebook_id)

    def append_state_summary(
        self, page_id: str, summary_html: str
    ) -> Dict[str, Any]:
        """
        Append an AI state summary to the top of a OneNote page.

        Fetches the current page content, injects a timestamped summary div
        at the top, and attempts an update with optimistic concurrency. On
        412 Precondition Failed, fetches fresh content and retries exactly once.

        Args:
            page_id: The Graph API page identifier.
            summary_html: HTML content to inject as the state summary.

        Returns:
            Dict with 'success', 'page_id', 'timestamp', and 'etag' keys.

        Raises:
            ConcurrentEditError: If the page was modified by another editor
                and the single retry also fails with 412.
            OneNoteUpdateError: If the update fails for any other reason.
        """
        logger.info("Appending state summary to page %s", page_id)

        content, etag = self._fetch_page(page_id)
        updated_html = self._inject_summary(content, summary_html)

        try:
            new_etag = self._update_page(page_id, updated_html, etag)
        except ConcurrentEditError:
            logger.warning(
                "Concurrent edit detected on page %s, retrying once", page_id
            )
            content, etag = self._fetch_page(page_id)
            updated_html = self._inject_summary(content, summary_html)

            try:
                new_etag = self._update_page(page_id, updated_html, etag)
            except ConcurrentEditError:
                logger.error(
                    "Persistent concurrent edit conflict on page %s", page_id
                )
                raise

        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("State summary appended to page %s", page_id)

        return {
            "success": True,
            "page_id": page_id,
            "timestamp": timestamp,
            "etag": new_etag,
        }

    def _fetch_page(self, page_id: str) -> tuple:
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
            meta_resp = self._graph.get(meta_url)

            if isinstance(meta_resp, dict):
                etag = meta_resp.get("@odata.etag", "")
            elif hasattr(meta_resp, "headers"):
                etag = meta_resp.headers.get("ETag", "")
            else:
                etag = ""

            content_url = f"{GRAPH_BASE}/me/onenote/pages/{page_id}/content"
            content_resp = self._graph.get(content_url)

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

    def _inject_summary(self, existing_html: str, summary_html: str) -> str:
        """
        Inject a timestamped AI state summary div at the top of page content.

        Args:
            existing_html: Current page HTML content.
            summary_html: New summary HTML to inject.

        Returns:
            Modified HTML with the summary div prepended after <body>.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        summary_div = (
            f'<div class="ai-state" data-timestamp="{timestamp}">'
            f"{summary_html}</div>"
        )

        body_lower = existing_html.lower()
        body_idx = body_lower.find("<body>")
        if body_idx != -1:
            insert_at = body_idx + len("<body>")
            return (
                existing_html[:insert_at]
                + summary_div
                + existing_html[insert_at:]
            )

        body_attr_idx = body_lower.find("<body ")
        if body_attr_idx != -1:
            close_idx = existing_html.index(">", body_attr_idx) + 1
            return (
                existing_html[:close_idx]
                + summary_div
                + existing_html[close_idx:]
            )

        return summary_div + existing_html

    def _update_page(self, page_id: str, html: str, etag: str) -> str:
        """
        Update a OneNote page with optimistic concurrency control.

        Args:
            page_id: The Graph API page identifier.
            html: The full updated HTML content.
            etag: The @odata.etag value from the last fetch.

        Returns:
            The new etag after a successful update.

        Raises:
            ConcurrentEditError: If the server returns 412 Precondition Failed.
            OneNoteUpdateError: If the update fails for other reasons.
        """
        url = f"{GRAPH_BASE}/me/onenote/pages/{page_id}/content"
        headers = {
            "Content-Type": "application/xhtml+xml",
            "If-Match": etag,
        }

        try:
            resp = self._graph.patch(url, headers=headers, data=html)

            if hasattr(resp, "headers"):
                new_etag = resp.headers.get("ETag", etag)
            elif isinstance(resp, dict):
                new_etag = resp.get("@odata.etag", etag)
            else:
                new_etag = etag

            logger.debug("Updated page %s successfully", page_id)
            return new_etag

        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if status == 412:
                raise ConcurrentEditError(
                    f"Page {page_id} was modified by another editor"
                ) from exc

            logger.error("Failed to update page %s: %s", page_id, exc)
            raise OneNoteUpdateError(
                f"Failed to update OneNote page {page_id}: {exc}"
            ) from exc
