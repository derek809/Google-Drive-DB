"""
SharePoint List Reader for Hybrid Operations Backend

Manages Action Items via SharePoint Lists with optimistic concurrency,
stale task recovery, and heartbeat-based crash safety.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class StaleItemError(Exception):
    """Raised when a stale item reset operation fails."""
    pass


class SharePointListReader:
    """
    Reads and manages SharePoint List items for the operations pipeline.

    Implements crash-safe task processing with:
    - Optimistic locking via If-Match/etag on claim
    - Heartbeat-based stale detection and automatic recovery
    - Atomic status transitions with recovery logging
    """

    def __init__(
        self,
        graph_client,
        config_loader: Callable[[str], Any],
    ) -> None:
        """
        Initialize SharePoint List reader.

        Args:
            graph_client: Authenticated Graph API client with get/post/patch
                methods. Handles 401 refresh automatically.
            config_loader: Callable that resolves dotted config keys to values.
        """
        self._graph = graph_client
        self._site_id = config_loader("sharepoint.site_id")
        self._stale_threshold_minutes = (
            config_loader("microsoft.stale_task_threshold_minutes") or 15
        )
        self._action_items_list = config_loader("microsoft.action_items_list_id")

        logger.info(
            "SharePointListReader initialized (site=%s, stale_threshold=%dm)",
            self._site_id,
            self._stale_threshold_minutes,
        )

    def _list_items_url(self, list_id: str) -> str:
        """Build the Graph API URL for list items."""
        return f"{GRAPH_BASE}/sites/{self._site_id}/lists/{list_id}/items"

    def _item_url(self, list_id: str, item_id: str) -> str:
        """Build the Graph API URL for a specific list item."""
        return f"{self._list_items_url(list_id)}/{item_id}"

    def poll_action_items(self, list_id: str) -> List[Dict[str, Any]]:
        """
        Poll for actionable items from a SharePoint list.

        Queries items where Status is 'Pending' or where Status is 'Processing'
        but the item is stale (Modified timestamp older than the configured
        threshold). Stale 'Processing' items are atomically reset to 'Pending'
        with a RecoveryLog note before being returned.

        Args:
            list_id: The SharePoint list identifier to poll.

        Returns:
            List of actionable item dicts, each containing 'id', 'fields',
            'etag', and 'file_id' keys.
        """
        logger.info("Polling action items from list %s", list_id)

        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=self._stale_threshold_minutes
        )
        cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        filter_query = (
            "fields/Status eq 'Pending' or "
            "(fields/Status eq 'Processing' and fields/Modified lt "
            f"'{cutoff_iso}')"
        )
        url = (
            f"{self._list_items_url(list_id)}"
            f"?$filter={filter_query}"
            f"&$expand=fields"
        )

        try:
            resp = self._graph.get(url)
            raw_items = resp.get("value", []) if isinstance(resp, dict) else []
        except Exception as exc:
            logger.error("Failed to poll list %s: %s", list_id, exc)
            return []

        actionable: List[Dict[str, Any]] = []

        for item in raw_items:
            fields = item.get("fields", {})
            item_id = item.get("id", "")
            etag = item.get("@odata.etag", "")

            if fields.get("Status") == "Processing":
                try:
                    self._reset_stale_item(list_id, item_id, etag)
                except StaleItemError as exc:
                    logger.warning(
                        "Skipping stale item %s — reset failed: %s",
                        item_id,
                        exc,
                    )
                    continue

                try:
                    refreshed = self._graph.get(
                        f"{self._item_url(list_id, item_id)}?$expand=fields"
                    )
                    fields = refreshed.get("fields", fields)
                    etag = refreshed.get("@odata.etag", etag)
                except Exception as exc:
                    logger.warning(
                        "Could not refresh item %s after reset: %s",
                        item_id,
                        exc,
                    )

            actionable.append(
                {
                    "id": item_id,
                    "fields": fields,
                    "etag": etag,
                    "file_id": fields.get("FileID", ""),
                }
            )

        logger.info(
            "Polled %d actionable items from list %s", len(actionable), list_id
        )
        return actionable

    def _reset_stale_item(
        self, list_id: str, item_id: str, etag: str
    ) -> None:
        """
        Reset a stale 'Processing' item back to 'Pending' with a recovery note.

        Args:
            list_id: The SharePoint list identifier.
            item_id: The item to reset.
            etag: Current etag for optimistic locking.

        Raises:
            StaleItemError: If the atomic reset fails.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        recovery_note = (
            f"Reset from Processing at {now_iso} due to stale heartbeat"
        )

        url = f"{self._item_url(list_id, item_id)}/fields"
        headers = {
            "Content-Type": "application/json",
            "If-Match": etag,
        }
        payload = {
            "Status": "Pending",
            "RecoveryLog": recovery_note,
        }

        try:
            self._graph.patch(url, headers=headers, data=payload)
            logger.info(
                "Reset stale item %s to Pending: %s", item_id, recovery_note
            )
        except Exception as exc:
            logger.error("Failed to reset stale item %s: %s", item_id, exc)
            raise StaleItemError(
                f"Failed to reset stale item {item_id}: {exc}"
            ) from exc

    def claim_task(
        self, list_id: str, item_id: str, etag: str
    ) -> bool:
        """
        Claim a task by atomically updating its status to 'Processing'.

        Uses If-Match header for optimistic locking to prevent race conditions
        when multiple bot instances attempt to claim the same task.

        Args:
            list_id: The SharePoint list identifier.
            item_id: The item to claim.
            etag: Current etag for optimistic locking.

        Returns:
            True if the task was successfully claimed, False if another
            process claimed it first (412 response).
        """
        url = f"{self._item_url(list_id, item_id)}/fields"
        headers = {
            "Content-Type": "application/json",
            "If-Match": etag,
        }
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "Status": "Processing",
            "LastBotHeartbeat": now_iso,
        }

        try:
            self._graph.patch(url, headers=headers, data=payload)
            logger.info("Claimed task %s in list %s", item_id, list_id)
            return True
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if status == 412:
                logger.warning(
                    "Race condition claiming task %s — another process won",
                    item_id,
                )
                return False
            logger.error("Failed to claim task %s: %s", item_id, exc)
            return False

    def update_heartbeat(self, list_id: str, item_id: str) -> None:
        """
        Update the heartbeat timestamp for a task being processed.

        Best-effort operation with no etag requirement. Heartbeat updates
        prevent the task from being detected as stale by other instances.

        Args:
            list_id: The SharePoint list identifier.
            item_id: The item to update.
        """
        url = f"{self._item_url(list_id, item_id)}/fields"
        headers = {"Content-Type": "application/json"}
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {"LastBotHeartbeat": now_iso}

        try:
            self._graph.patch(url, headers=headers, data=payload)
            logger.debug("Heartbeat updated for task %s", item_id)
        except Exception as exc:
            logger.warning(
                "Heartbeat update failed for task %s (best effort): %s",
                item_id,
                exc,
            )

    def complete_task(
        self, list_id: str, item_id: str, notes: str
    ) -> None:
        """
        Mark a task as complete with completion notes and timestamp.

        Args:
            list_id: The SharePoint list identifier.
            item_id: The item to complete.
            notes: Completion notes describing the outcome.
        """
        url = f"{self._item_url(list_id, item_id)}/fields"
        headers = {"Content-Type": "application/json"}
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "Status": "Complete",
            "CompletionNotes": notes,
            "CompletedAt": now_iso,
        }

        try:
            self._graph.patch(url, headers=headers, data=payload)
            logger.info("Completed task %s: %s", item_id, notes[:80])
        except Exception as exc:
            logger.error("Failed to complete task %s: %s", item_id, exc)
            raise
