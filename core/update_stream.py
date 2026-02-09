"""
Update Stream Handler for Mode 4 Action Registry.

Sends intermediate status updates during long-running operations instead
of leaving the user waiting in silence.

Implements the "Human Wait" UX improvement:
- "Found the email from Jason."
- "Analyzing the attachments..."
- "Drafting your response with Ollama..."
"""

import asyncio
import logging
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)


class UpdateStream:
    """
    Sends intermediate status updates during long-running operations.
    """

    def __init__(self, telegram_handler=None):
        self.telegram = telegram_handler
        self.active_streams: dict = {}  # user_id -> message_id mapping

    async def start_stream(self, user_id: int, initial_message: str) -> Optional[str]:
        """
        Start a new update stream for a user.
        Returns the stream_id (or None if telegram is unavailable).
        """
        if not self.telegram:
            logger.debug("[UPDATE_STREAM] No telegram handler, skipping stream")
            return None

        try:
            msg = await self.telegram.send_response(user_id, initial_message)
            if msg and hasattr(msg, "message_id"):
                self.active_streams[user_id] = msg.message_id
                return f"{user_id}_{msg.message_id}"
        except Exception as e:
            logger.warning("[UPDATE_STREAM] Failed to start stream: %s", e)

        return None

    async def update(self, user_id: int, new_status: str):
        """Update the status message for this user."""
        if not self.telegram:
            return

        if user_id not in self.active_streams:
            # No active stream, just send new message
            try:
                await self.telegram.send_response(user_id, new_status)
            except Exception as e:
                logger.warning("[UPDATE_STREAM] Failed to send update: %s", e)
            return

        # Try to edit existing message
        try:
            if hasattr(self.telegram, "edit_message"):
                await self.telegram.edit_message(
                    user_id,
                    self.active_streams[user_id],
                    new_status,
                )
            else:
                await self.telegram.send_response(user_id, new_status)
        except Exception as e:
            logger.debug("[UPDATE_STREAM] Failed to edit message: %s", e)
            try:
                await self.telegram.send_response(user_id, new_status)
            except Exception:
                pass

    async def finish(self, user_id: int, final_message: str):
        """Finish the stream and send final result."""
        if user_id in self.active_streams:
            del self.active_streams[user_id]

        if self.telegram:
            try:
                await self.telegram.send_response(user_id, final_message)
            except Exception as e:
                logger.warning("[UPDATE_STREAM] Failed to send final message: %s", e)

    async def with_updates(
        self,
        user_id: int,
        operation: Callable,
        steps: List[str],
    ) -> Any:
        """
        Execute an operation with step-by-step updates.

        Example:
            await update_stream.with_updates(
                user_id=123,
                operation=email_processor.create_draft,
                steps=[
                    "Finding email from Jason...",
                    "Analyzing thread context...",
                    "Generating response with Ollama...",
                    "Formatting draft...",
                ]
            )
        """
        await self.start_stream(user_id, steps[0])

        try:
            for i, step in enumerate(steps[1:], 1):
                await asyncio.sleep(0.5)
                prev_done = f"Done: {steps[i - 1]}"
                await self.update(user_id, f"{prev_done}\n\n{step}")

            result = await operation()
            await self.finish(user_id, f"Done: {steps[-1]}\n\nComplete!")
            return result

        except Exception as e:
            await self.finish(user_id, f"Error: {e}")
            raise
