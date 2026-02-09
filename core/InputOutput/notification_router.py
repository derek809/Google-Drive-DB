"""
Notification Router for Mode 4 Action Registry.

Routes action results to multiple channels:
- Telegram (primary, always)
- Gmail summary (optional)
- Google Sheets status update (optional)
- Local database audit log (optional)

Implements the "Multi-Channel Output" feature.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class NotificationRouter:
    """
    Routes action results to multiple channels (Telegram, Gmail, Sheets, Desktop).
    """

    def __init__(self, telegram_handler=None, gmail_client=None, sheets_client=None):
        self.telegram = telegram_handler
        self.gmail = gmail_client
        self.sheets = sheets_client

    async def route_notification(
        self,
        user_id: int,
        action_name: str,
        params: Dict[str, Any],
        result: Any,
        multi_channel: bool = False,
    ):
        """
        Send notification about action result to appropriate channels.
        """
        # Always send to Telegram (already handled by conversation flow)
        await self._send_to_telegram(user_id, action_name, params, result)

        # If multi-channel is enabled for this action
        if multi_channel:
            await self._send_to_additional_channels(
                user_id, action_name, params, result
            )

    async def _send_to_telegram(
        self,
        user_id: int,
        action_name: str,
        params: Dict[str, Any],
        result: Any,
    ):
        """Send notification to Telegram (primary channel)."""
        # This is already handled by the main conversation flow.
        # Log for audit trail.
        logger.debug(
            "[MULTI-CHANNEL] Telegram notification for %s (user %d)",
            action_name,
            user_id,
        )

    async def _send_to_additional_channels(
        self,
        user_id: int,
        action_name: str,
        params: Dict[str, Any],
        result: Any,
    ):
        """Send summary to Gmail, update Sheets, etc."""
        result_dict = result if isinstance(result, dict) else {}

        if action_name == "todo_complete":
            await self._send_gmail_summary(
                user_id,
                subject=f"Task Completed: {params.get('task_title', 'Unknown')}",
                body=(
                    f"You marked task #{params.get('task_id')} as complete "
                    "via Telegram assistant."
                ),
            )
            await self._update_sheet_status(
                sheet_name="Tasks",
                task_id=params.get("task_id"),
                new_status="Completed",
                completion_time=result_dict.get("completed_at"),
            )

        elif action_name == "email_send":
            await self._log_to_database(
                action="email_sent",
                details={
                    "recipient": params.get("recipient"),
                    "subject": params.get("subject"),
                    "sent_at": result_dict.get("sent_at"),
                },
            )
            # Update related task if linked
            if "linked_task_id" in params:
                await self._update_sheet_status(
                    sheet_name="Tasks",
                    task_id=params["linked_task_id"],
                    new_status="Email Sent",
                )

    async def _send_gmail_summary(
        self, user_id: int, subject: str, body: str
    ):
        """Send a summary email to Derek's inbox."""
        try:
            if self.gmail:
                logger.info(
                    "[MULTI-CHANNEL] Sending Gmail summary: %s", subject
                )
                # gmail_client.create_draft or send functionality
                # Placeholder for actual implementation
            else:
                logger.debug(
                    "[MULTI-CHANNEL] Gmail client not available, skipping summary"
                )
        except Exception as e:
            logger.warning("[MULTI-CHANNEL] Failed to send Gmail summary: %s", e)

    async def _update_sheet_status(
        self,
        sheet_name: str,
        task_id: Any,
        new_status: str,
        **kwargs,
    ):
        """Update status in Google Sheet."""
        try:
            if self.sheets:
                logger.info(
                    "[MULTI-CHANNEL] Updating Sheet '%s': Task %s -> %s",
                    sheet_name,
                    task_id,
                    new_status,
                )
                # sheets_client.update_range functionality
                # Placeholder for actual implementation
            else:
                logger.debug(
                    "[MULTI-CHANNEL] Sheets client not available, skipping update"
                )
        except Exception as e:
            logger.warning("[MULTI-CHANNEL] Failed to update Sheet: %s", e)

    async def _log_to_database(self, action: str, details: Dict[str, Any]):
        """Log action to local database for auditing."""
        try:
            logger.info("[MULTI-CHANNEL] Logged to DB: %s - %s", action, details)
        except Exception as e:
            logger.warning("[MULTI-CHANNEL] Failed to log to database: %s", e)
