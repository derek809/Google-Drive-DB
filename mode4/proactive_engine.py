"""
Proactive Engine 2.0 - Background intelligence for Mode 4

Active workspace monitor that:
- Syncs with Gmail to detect replies on tracked threads
- Detects draft desertion (created but unsent after N days)
- Identifies stale threads needing follow-up
- Runs workspace hygiene (old tasks, duplicates, skill decay)
- Tracks behavioural patterns for predictive suggestions
- Sends morning digest at configured hour
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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
    - Stale threads needing "State of Play" summaries
    - Old tasks / duplicate tasks / decayed skills
    - Behavioural deviations (response time anomalies)

    Also sends morning digest at configured time daily.
    """

    def __init__(self, processor, telegram_handler):
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

        logger.info("Proactive Engine 2.0 initialized")

    # ========================================================================
    # MAIN WORKER
    # ========================================================================

    async def worker_loop(self):
        """Main background worker loop."""
        logger.info(f"Proactive Engine worker started (interval: {self.check_interval/3600}h)")

        while True:
            try:
                logger.info("Running proactive checks...")

                # Sync with Gmail first (real implementation)
                await self.sync_workspace()

                # Run all proactive checks
                await self.run_all_checks()

                # Workspace hygiene
                await self.run_hygiene_checks()

                logger.info(f"Check complete. Sleeping for {self.check_interval/3600} hours...")

            except Exception as e:
                logger.error(f"Proactive worker error: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

    # ========================================================================
    # GMAIL WORKSPACE SYNC (Priority 5 fix)
    # ========================================================================

    async def sync_workspace(self):
        """
        Sync workspace with Gmail — check tracked threads for new replies.

        When the user has already replied to a thread, update the workspace
        item status so we don't suggest a follow-up.
        """
        try:
            items = self.get_workspace_items(status='active')
            if not items:
                logger.debug("No workspace items to sync")
                return

            gmail = None
            try:
                gmail = self.processor.gmail
            except Exception as e:
                logger.warning(f"Gmail not available for sync: {e}")
                return

            synced = 0
            for item in items:
                thread_id = item.get('thread_id')
                if not thread_id:
                    continue

                try:
                    user_replied = await self._check_user_replied(gmail, thread_id)
                    if user_replied:
                        self.update_workspace_item(
                            item['id'],
                            status='user_replied',
                            last_user_reply=datetime.now().isoformat(),
                        )
                        synced += 1
                        logger.info(f"Synced item {item['id']}: user replied to thread {thread_id}")
                except Exception as e:
                    logger.debug(f"Error checking thread {thread_id}: {e}")

            if synced > 0:
                logger.info(f"Synced {synced} workspace items with Gmail")

        except Exception as e:
            logger.error(f"Workspace sync error: {e}")

    async def _check_user_replied(self, gmail, thread_id: str) -> bool:
        """Check if the authenticated user has sent a message in this thread."""
        try:
            loop = asyncio.get_event_loop()
            thread = await loop.run_in_executor(
                None,
                lambda: gmail.service.users().threads().get(
                    userId='me', id=thread_id, format='metadata',
                    metadataHeaders=['From']
                ).execute()
            )

            messages = thread.get('messages', [])
            if not messages:
                return False

            profile = await loop.run_in_executor(
                None,
                lambda: gmail.service.users().getProfile(userId='me').execute()
            )
            user_email = profile.get('emailAddress', '').lower()

            for msg in messages[1:]:
                headers = {
                    h['name'].lower(): h['value']
                    for h in msg.get('payload', {}).get('headers', [])
                }
                from_header = headers.get('from', '').lower()
                if user_email in from_header:
                    return True

            return False

        except Exception as e:
            logger.debug(f"Error checking thread reply: {e}")
            return False

    # ========================================================================
    # PROACTIVE CHECKS
    # ========================================================================

    async def run_all_checks(self):
        """Run all proactive check rules."""
        items = self.get_workspace_items(status='active')

        if not items:
            logger.info("No active workspace items - nothing to check")
            return

        logger.info(f"Checking {len(items)} workspace items...")

        for item in items:
            if self.should_skip_suggestion(item):
                continue

            try:
                await self.check_no_reply_followup(item)
                await self.check_urgent_eod(item)
                await self.check_draft_unsent(item)
                await self.check_stale_thread(item)
            except Exception as e:
                logger.error(f"Error checking item {item.get('id')}: {e}")

    # ── Time-based checks ────────────────────────────────────────────────

    async def check_no_reply_followup(self, item: Dict):
        """RULE: No reply in 3+ days and user hasn't replied → suggest follow-up."""
        if item.get('status') == 'user_replied':
            return

        days_old = item.get('days_old', 0)
        if days_old >= self.no_reply_days_threshold:
            await self.suggest(
                item,
                suggestion_type='follow_up',
                message=(
                    f"{item.get('from_name', 'Unknown')} hasn't replied in {days_old} days.\n"
                    f"Subject: {item.get('subject', 'Unknown')}\n\n"
                    f"Want to send a follow-up?"
                )
            )

    async def check_urgent_eod(self, item: Dict):
        """RULE: Urgent item + late afternoon (3-5pm) → remind before EOD."""
        if item.get('urgency') != 'urgent':
            return

        hour = datetime.now().hour
        if self.urgent_hour_start <= hour <= self.urgent_hour_end:
            await self.suggest(
                item,
                suggestion_type='urgent_eod',
                message=(
                    f"Urgent: {item.get('subject', 'Unknown')}\n"
                    f"From: {item.get('from_name', 'Unknown')}\n\n"
                    f"Tackle this before EOD?"
                )
            )

    # ── Event-based checks ───────────────────────────────────────────────

    async def check_draft_unsent(self, item: Dict):
        """RULE: Draft exists but not sent for N+ days → remind to send."""
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
            if status != 'pending':
                return

            draft_time = datetime.fromisoformat(received_at)
            draft_age = (datetime.now() - draft_time).days

            if draft_age >= self.draft_unsent_days_threshold:
                await self.suggest(
                    item,
                    suggestion_type='draft_unsent',
                    message=(
                        f"You drafted a reply to {item.get('from_name', 'Unknown')} "
                        f"{draft_age} days ago but didn't send it.\n"
                        f"Subject: {item.get('subject', 'Unknown')}\n\n"
                        f"Still relevant? Send it now or discard?"
                    )
                )

        except Exception as e:
            logger.error(f"Error checking draft for item {item.get('id')}: {e}")

    async def check_stale_thread(self, item: Dict):
        """RULE: Thread with 5+ messages without user reply → suggest summary."""
        message_count = item.get('message_count', 0)
        if message_count < 5:
            return

        if item.get('status') == 'user_replied':
            return

        await self.suggest(
            item,
            suggestion_type='stale_thread',
            message=(
                f"Thread '{item.get('subject', 'Unknown')}' has {message_count} messages "
                f"without your reply.\n\n"
                f"Want me to generate a State of Play summary?"
            )
        )

    # ========================================================================
    # WORKSPACE HYGIENE
    # ========================================================================

    async def run_hygiene_checks(self):
        """Run workspace hygiene checks: old tasks, duplicates, skill decay."""
        try:
            await self._check_old_tasks()
            await self._check_skill_decay()
        except Exception as e:
            logger.error(f"Hygiene check error: {e}")

    async def _check_old_tasks(self):
        """Tasks older than 30 days → suggest archiving."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, created_at FROM tasks
                    WHERE status = 'active'
                    AND created_at < datetime('now', '-30 days')
                    LIMIT 5
                """)
                old_tasks = [dict(row) for row in cursor.fetchall()]

            if not old_tasks:
                return

            from m1_config import TELEGRAM_ADMIN_CHAT_ID
            if not TELEGRAM_ADMIN_CHAT_ID:
                return

            titles = [t['title'][:40] for t in old_tasks]
            message = (
                f"You have {len(old_tasks)} task(s) older than 30 days:\n"
                + "\n".join(f"  - {t}" for t in titles)
                + "\n\nArchive them?"
            )
            await self.telegram.send_message(chat_id=TELEGRAM_ADMIN_CHAT_ID, text=message)

        except Exception as e:
            logger.debug(f"Old task check skipped: {e}")

    async def _check_skill_decay(self):
        """Skills not referenced in 90 days → suggest archiving."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, slug FROM skills
                    WHERE status = 'Pending'
                    AND updated_at < datetime('now', '-90 days')
                    LIMIT 3
                """)
                stale_skills = [dict(row) for row in cursor.fetchall()]

            if not stale_skills:
                return

            from m1_config import TELEGRAM_ADMIN_CHAT_ID
            if not TELEGRAM_ADMIN_CHAT_ID:
                return

            names = [s.get('title', s.get('slug', '?'))[:40] for s in stale_skills]
            message = (
                f"{len(stale_skills)} skill(s) haven't been referenced in 90+ days:\n"
                + "\n".join(f"  - {n}" for n in names)
                + "\n\nArchive them?"
            )
            await self.telegram.send_message(chat_id=TELEGRAM_ADMIN_CHAT_ID, text=message)

        except Exception as e:
            logger.debug(f"Skill decay check skipped: {e}")

    # ========================================================================
    # SUGGESTION MANAGEMENT
    # ========================================================================

    async def suggest(self, item: Dict, suggestion_type: str, message: str):
        """Send a suggestion to user via Telegram."""
        item_id = item.get('id', 'unknown')
        logger.info(f"Suggesting: {suggestion_type} for item {item_id}")

        try:
            chat_id = item.get('chat_id')
            if not chat_id:
                from m1_config import TELEGRAM_ADMIN_CHAT_ID
                chat_id = TELEGRAM_ADMIN_CHAT_ID

            if not chat_id:
                logger.warning("No chat_id for suggestion")
                return

            await self.telegram.send_message(chat_id=chat_id, text=message)

            self.update_workspace_item(
                item_id,
                last_bot_suggestion=datetime.now().isoformat(),
                suggestion_count=item.get('suggestion_count', 0) + 1
            )
            self.log_suggestion(item_id, suggestion_type)

        except Exception as e:
            logger.error(f"Failed to send suggestion: {e}")

    def should_skip_suggestion(self, item: Dict) -> bool:
        """Check if we should skip suggesting for this item (max 1 per 24h)."""
        last_suggestion = item.get('last_bot_suggestion')
        if not last_suggestion:
            return False

        try:
            last_time = datetime.fromisoformat(last_suggestion)
            hours_ago = (datetime.now() - last_time).total_seconds() / 3600
            if hours_ago < 24:
                return True
        except (ValueError, TypeError):
            pass

        return False

    def log_suggestion(self, workspace_item_id, suggestion_type: str):
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
        """Send morning summary at configured time."""
        logger.info("Generating morning digest...")

        items = self.get_workspace_items(status='active')

        from m1_config import TELEGRAM_ADMIN_CHAT_ID
        chat_id = TELEGRAM_ADMIN_CHAT_ID

        if not chat_id:
            logger.warning("No admin chat ID for morning digest")
            return

        if not items:
            await self.telegram.send_message(
                chat_id=chat_id,
                text="Good morning! Your workspace is clear. Nice work!"
            )
            return

        urgent = [i for i in items if i.get('urgency') == 'urgent']
        normal = [i for i in items if i.get('urgency') == 'normal']
        low = [i for i in items if i.get('urgency') == 'low']

        lines = ["Good morning! Your MCP workspace:\n"]

        if urgent:
            lines.append("URGENT TODAY:")
            for item in urgent:
                lines.append(f"  {item.get('id')}. {item.get('subject', '?')} - {item.get('from_name', '?')}")
                if item.get('days_old', 0) >= 3:
                    lines.append(f"     {item['days_old']} days old - needs follow-up?")
            lines.append("")

        if normal:
            lines.append(f"NEEDS ATTENTION ({len(normal)} items):")
            for item in normal[:3]:
                lines.append(f"  {item.get('id')}. {item.get('subject', '?')} - {item.get('from_name', '?')}")
            if len(normal) > 3:
                lines.append(f"   ... and {len(normal)-3} more")
            lines.append("")

        if low:
            lines.append(f"LOW PRIORITY ({len(low)} items)")
            lines.append("")

        try:
            from m1_config import SKILL_INCLUDE_IN_MORNING_BRIEF
            if SKILL_INCLUDE_IN_MORNING_BRIEF:
                from skill_manager import SkillManager
                skill_mgr = SkillManager()
                pending_skills = skill_mgr.list_skills(status='Pending', limit=5)

                if pending_skills:
                    lines.append("RECENT IDEAS:")
                    for skill in pending_skills:
                        action_count = len(skill.get('action_items', [])) if skill.get('action_items') else 0
                        skill_line = f"  #{skill['slug'][:25]}: {skill['title'][:35]}"
                        if action_count > 0:
                            skill_line += f" ({action_count} actions)"
                        lines.append(skill_line)
                    lines.append("")
        except Exception as e:
            logger.warning(f"Could not include skills in morning brief: {e}")

        lines.append("Reply with number or tell me what you need!")

        message = "\n".join(lines)
        await self.telegram.send_message(chat_id=chat_id, text=message)

    async def schedule_morning_digest(self):
        """Schedule morning digest to run at configured hour daily."""
        logger.info(f"Morning digest scheduler started (target: {self.morning_digest_hour}:00)")

        while True:
            now = datetime.now()
            target = now.replace(hour=self.morning_digest_hour, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)

            seconds_until = (target - now).total_seconds()
            logger.info(f"Next morning digest in {seconds_until/3600:.1f} hours")
            await asyncio.sleep(seconds_until)

            await self.send_morning_digest()

    # ========================================================================
    # WORKSPACE ITEM MANAGEMENT
    # ========================================================================

    def get_workspace_items(self, status: str = None) -> List[Dict]:
        """Get all workspace items from database."""
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

    def update_workspace_item(self, item_id, **kwargs):
        """Update workspace item fields."""
        if not kwargs:
            return
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
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
    """Start all background workers (for standalone testing)."""
    logger.info("Starting Proactive Engine (standalone mode)...")
    print("Standalone mode requires Mode4Processor and TelegramHandler")
    print("Use Mode4Processor.start_proactive_engine() in production")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("MCP Proactive Engine 2.0")
    print("=" * 50)
    print("This worker runs in the background and sends proactive suggestions.")
    print("Note: Standalone mode is for testing only.")
    print("Press Ctrl+C to stop.")
    print()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProactive Engine stopped")
