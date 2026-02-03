"""
Proactive Engine - Background worker for Mode 4
Sends proactive suggestions, reminders, and morning digest via Telegram
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

logger = logging.getLogger(__name__)


class ProactiveEngineError(Exception):
    """Exception raised when ProactiveEngine encounters an error."""
    pass


class ProactiveEngine:
    """
    Makes Mode 4 proactive instead of just reactive.

    Runs in background every 2 hours checking workspace for:
    - Emails that haven't been replied to in 3+ days
    - Urgent items approaching end of day
    - Drafts created but never sent
    - Pattern-based suggestions (future)

    Also sends morning digest at 7am daily.
    """

    def __init__(self, processor, telegram_handler):
        """
        Initialize with Mode4Processor and TelegramHandler instances.

        Args:
            processor: Mode4Processor instance
            telegram_handler: TelegramHandler instance
        """
        self.processor = processor
        self.telegram = telegram_handler
        self.db_manager = processor.db_manager

        # Load configuration
        try:
            from m1_config import (
                PROACTIVE_CHECK_INTERVAL,
                PROACTIVE_MAX_SUGGESTIONS_PER_DAY,
                PROACTIVE_NO_REPLY_DAYS,
                PROACTIVE_URGENT_HOURS,
                PROACTIVE_DRAFT_UNSENT_DAYS,
                PROACTIVE_MORNING_DIGEST_HOUR,
            )
            self.check_interval = PROACTIVE_CHECK_INTERVAL
            self.max_suggestions_per_day = PROACTIVE_MAX_SUGGESTIONS_PER_DAY
            self.no_reply_days_threshold = PROACTIVE_NO_REPLY_DAYS
            self.urgent_hour_start, self.urgent_hour_end = PROACTIVE_URGENT_HOURS
            self.draft_unsent_days_threshold = PROACTIVE_DRAFT_UNSENT_DAYS
            self.morning_digest_hour = PROACTIVE_MORNING_DIGEST_HOUR
        except ImportError as e:
            logger.error(f"Failed to load config: {e}")
            raise ProactiveEngineError(f"Configuration error: {str(e)}")

        logger.info("Proactive Engine initialized")

    async def worker_loop(self):
        """
        Main background worker loop.

        Runs continuously, checking workspace every N hours (configurable).
        """
        logger.info(f"🤖 Proactive Engine worker started (interval: {self.check_interval/3600}h)")

        while True:
            try:
                logger.info("🔍 Running proactive checks...")

                # Sync with Gmail first
                await self.sync_workspace()

                # Run all proactive checks
                await self.run_all_checks()

                logger.info(f"✅ Check complete. Sleeping for {self.check_interval/3600} hours...")

            except Exception as e:
                logger.error(f"❌ Proactive worker error: {e}", exc_info=True)

            # Wait before next check
            await asyncio.sleep(self.check_interval)

    async def sync_workspace(self):
        """
        Sync workspace with Gmail before checking triggers.

        This ensures we have the latest email activity.
        """
        try:
            # Get workspace items
            items = self.get_workspace_items()

            if not items:
                logger.debug("No workspace items to sync")
                return

            # For each item, check Gmail for new activity
            # This is a placeholder - implement based on your needs
            logger.debug(f"Synced {len(items)} workspace items")

        except Exception as e:
            logger.error(f"Workspace sync error: {e}")

    async def run_all_checks(self):
        """
        Run all proactive check rules.

        Each check function looks for a specific trigger and suggests action.
        """
        items = self.get_workspace_items(status='active')

        if not items:
            logger.info("No active workspace items - nothing to check")
            return

        logger.info(f"Checking {len(items)} workspace items...")

        for item in items:
            # Skip if we already suggested something today
            if self.should_skip_suggestion(item):
                continue

            try:
                # Time-based checks
                await self.check_no_reply_followup(item)
                await self.check_urgent_eod(item)

                # Event-based checks
                await self.check_draft_unsent(item)

            except Exception as e:
                logger.error(f"Error checking item {item.get('id')}: {e}")

    # ========================================================================
    # TIME-BASED CHECKS
    # ========================================================================

    async def check_no_reply_followup(self, item: Dict):
        """
        RULE: No reply in 3+ days → suggest follow-up

        Example alert: "💬 Laura Clarke hasn't replied in 5 days. Follow up?"
        """
        days_old = item.get('days_old', 0)

        if days_old >= self.no_reply_days_threshold:
            await self.suggest(
                item,
                suggestion_type='follow_up',
                message=(
                    f"💬 {item['from_name']} hasn't replied in {days_old} days.\n"
                    f"Subject: {item['subject']}\n\n"
                    f"Want to send a follow-up?"
                )
            )

    async def check_urgent_eod(self, item: Dict):
        """
        RULE: Urgent item + late afternoon (3-5pm) → remind before EOD

        Example alert: "⏰ Urgent: Compliance call prep - tackle before EOD?"
        """
        if item.get('urgency') != 'urgent':
            return

        hour = datetime.now().hour

        if self.urgent_hour_start <= hour <= self.urgent_hour_end:
            await self.suggest(
                item,
                suggestion_type='urgent_eod',
                message=(
                    f"⏰ Urgent: {item['subject']}\n"
                    f"From: {item['from_name']}\n\n"
                    f"Tackle this before EOD?"
                )
            )

    # ========================================================================
    # EVENT-BASED CHECKS
    # ========================================================================

    async def check_draft_unsent(self, item: Dict):
        """
        RULE: Draft exists but not sent for 2+ days → remind to send

        Example alert: "📧 You drafted a reply to Jason 2 days ago - ready to send?"
        """
        draft_id = item.get('related_draft_id')
        if not draft_id:
            return

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT received_at, status FROM message_queue
                    WHERE draft_id=?
                """, (draft_id,))

                row = cursor.fetchone()

            if not row:
                return

            received_at, status = row['received_at'], row['status']

            if status != 'pending':  # Already sent or cancelled
                return

            # Check age
            draft_time = datetime.fromisoformat(received_at)
            draft_age = (datetime.now() - draft_time).days

            if draft_age >= self.draft_unsent_days_threshold:
                await self.suggest(
                    item,
                    suggestion_type='draft_unsent',
                    message=(
                        f"📧 You drafted a reply to {item['from_name']} {draft_age} days ago.\n"
                        f"Subject: {item['subject']}\n\n"
                        f"Ready to send it?"
                    )
                )

        except Exception as e:
            logger.error(f"Error checking draft for item {item.get('id')}: {e}")

    # ========================================================================
    # SUGGESTION MANAGEMENT
    # ========================================================================

    async def suggest(self, item: Dict, suggestion_type: str, message: str):
        """
        Send a suggestion to user via Telegram.

        Also logs the suggestion to prevent spam.
        """
        item_id = item.get('id', 'unknown')
        logger.info(f"💡 Suggesting: {suggestion_type} for item {item_id}")

        try:
            # Send to Telegram
            await self.telegram.send_message(
                chat_id=item.get('chat_id'),
                text=message
            )

            # Update workspace item
            self.update_workspace_item(
                item_id,
                last_bot_suggestion=datetime.now().isoformat(),
                suggestion_count=item.get('suggestion_count', 0) + 1
            )

            # Log suggestion
            self.log_suggestion(item_id, suggestion_type)

        except Exception as e:
            logger.error(f"Failed to send suggestion: {e}")

    def should_skip_suggestion(self, item: Dict) -> bool:
        """
        Check if we should skip suggesting for this item.

        Prevents spam by enforcing max 1 suggestion per item per day.
        """
        last_suggestion = item.get('last_bot_suggestion')

        if not last_suggestion:
            return False  # Never suggested - go ahead

        try:
            last_time = datetime.fromisoformat(last_suggestion)
            hours_ago = (datetime.now() - last_time).total_seconds() / 3600

            if hours_ago < 24:
                logger.debug(f"Skipping item {item.get('id')} - suggested {hours_ago:.1f}h ago")
                return True

        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing last_suggestion: {e}")

        return False

    def log_suggestion(self, workspace_item_id: int, suggestion_type: str):
        """Log a suggestion to database."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO suggestion_log (workspace_item_id, suggestion_type)
                    VALUES (?, ?)
                """, (workspace_item_id, suggestion_type))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log suggestion: {e}")

    # ========================================================================
    # MORNING DIGEST
    # ========================================================================

    async def send_morning_digest(self):
        """
        Send morning summary at configured time (default 7am).

        Shows urgent items, items needing attention, and workspace health.
        """
        logger.info("🌅 Generating morning digest...")

        items = self.get_workspace_items(status='active')

        if not items:
            message = "🌅 Good morning! Your workspace is empty. Nice work! 🎉"
            await self.telegram.send_message(chat_id=None, text=message)
            return

        # Group by urgency
        urgent = [i for i in items if i.get('urgency') == 'urgent']
        normal = [i for i in items if i.get('urgency') == 'normal']
        low = [i for i in items if i.get('urgency') == 'low']

        # Build message
        lines = ["🌅 Good morning! Your MCP workspace:\n"]

        if urgent:
            lines.append("🔴 URGENT TODAY:")
            for item in urgent:
                lines.append(f"{item['id']}. {item['subject']} - {item['from_name']}")
                if item.get('days_old', 0) >= 3:
                    lines.append(f"   → {item['days_old']} days old - needs follow-up?")
            lines.append("")

        if normal:
            lines.append(f"🟡 NEEDS ATTENTION ({len(normal)} items):")
            for item in normal[:3]:  # Show top 3
                lines.append(f"{item['id']}. {item['subject']} - {item['from_name']}")
            if len(normal) > 3:
                lines.append(f"   ... and {len(normal)-3} more")
            lines.append("")

        if low:
            lines.append(f"🟢 LOW PRIORITY ({len(low)} items)")
            lines.append("")

        lines.append("Reply with number or tell me what you need!")

        message = "\n".join(lines)
        await self.telegram.send_message(chat_id=None, text=message)

    async def schedule_morning_digest(self):
        """Schedule morning digest to run at configured hour daily."""
        logger.info(f"⏰ Morning digest scheduler started (target: {self.morning_digest_hour}:00)")

        while True:
            now = datetime.now()

            # Calculate time until next target hour
            target = now.replace(hour=self.morning_digest_hour, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)  # Tomorrow

            seconds_until = (target - now).total_seconds()

            logger.info(f"Next morning digest in {seconds_until/3600:.1f} hours")
            await asyncio.sleep(seconds_until)

            # Send digest
            await self.send_morning_digest()

    # ========================================================================
    # WORKSPACE ITEM MANAGEMENT
    # ========================================================================

    def get_workspace_items(self, status: str = None) -> List[Dict]:
        """
        Get all workspace items from database.

        Args:
            status: Filter by status (active, completed, archived) or None for all

        Returns:
            List of workspace item dicts
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                if status:
                    cursor.execute("""
                        SELECT * FROM workspace_items
                        WHERE status = ?
                        ORDER BY received_at DESC
                    """, (status,))
                else:
                    cursor.execute("""
                        SELECT * FROM workspace_items
                        ORDER BY received_at DESC
                    """)

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get workspace items: {e}")
            return []

    def update_workspace_item(self, item_id: int, **kwargs):
        """
        Update workspace item fields.

        Args:
            item_id: The workspace item ID
            **kwargs: Fields to update (e.g., last_bot_suggestion="2024-01-01")
        """
        if not kwargs:
            return

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Build SET clause dynamically
                set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
                values = list(kwargs.values()) + [item_id]

                cursor.execute(f"""
                    UPDATE workspace_items
                    SET {set_clause}
                    WHERE id = ?
                """, values)

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to update workspace item {item_id}: {e}")


# ========================================================================
# MAIN EXECUTION (for standalone testing)
# ========================================================================

async def main():
    """
    Start all background workers (for standalone testing).

    In production, this is called from Mode4Processor.start_proactive_engine()
    """
    logger.info("🚀 Starting Proactive Engine (standalone mode)...")

    # This would need to be initialized with real processor/telegram instances
    print("⚠️  Standalone mode requires Mode4Processor and TelegramHandler")
    print("⚠️  Use Mode4Processor.start_proactive_engine() in production")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🤖 MCP Proactive Engine")
    print("=" * 50)
    print("This worker runs in the background and sends proactive suggestions.")
    print("Note: Standalone mode is for testing only.")
    print("In production, start via Mode4Processor.start_proactive_engine()")
    print("Press Ctrl+C to stop.")
    print()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Proactive Engine stopped")
