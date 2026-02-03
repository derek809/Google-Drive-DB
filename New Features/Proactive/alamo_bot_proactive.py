#!/usr/bin/env python3
"""
ALAMO BOT PROACTIVE LAYER
=========================

This module extends Alamo Bot with proactive intelligence.
While Alamo Bot handles reactive conversations (user sends message → bot responds),
this layer initiates conversations (bot detects trigger → bot suggests action).

INTEGRATION WITH ALAMO BOT:
- Uses same brain structure (/brain/operations_assistant)
- Shares Telegram bot instance
- Reads from same workspace/database
- Follows same deterministic decision rules

HOW IT WORKS:
1. Runs as background worker (asyncio loop every 2 hours)
2. Checks workspace items against trigger rules
3. Scores suggestions for relevance
4. Sends alerts via Telegram (if score > threshold)
5. Logs suggestions to prevent spam
6. Learns from user responses to improve future suggestions

USAGE:
    # Option 1: Standalone background worker
    python alamo_bot_proactive.py
    
    # Option 2: Integrated with main Alamo Bot
    from alamo_bot_proactive import start_proactive_engine
    asyncio.create_task(start_proactive_engine(bot_instance))
"""

import asyncio
import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class ProactiveConfig:
    """Configuration for proactive engine"""
    
    BRAIN_PATH = Path("brain/operations_assistant")
    CHECK_INTERVAL = 2 * 60 * 60  # 2 hours in seconds
    
    # Thresholds
    NO_REPLY_DAYS = 3
    DRAFT_UNSENT_DAYS = 2
    URGENT_HOUR_START = 15  # 3pm
    URGENT_HOUR_END = 17    # 5pm
    
    # Spam prevention
    MAX_SUGGESTIONS_PER_DAY = 1
    MIN_CONFIDENCE_SCORE = 0.65
    
    # Quiet hours (no alerts)
    QUIET_HOURS = {
        'enabled': True,
        'weekday_start': 19,  # 7pm
        'weekday_end': 7,     # 7am
        'weekend_all_day': True
    }
    
    # Morning digest
    MORNING_DIGEST_HOUR = 7
    MORNING_DIGEST_MINUTE = 0


# =============================================================================
# TRIGGER RULES ENGINE
# =============================================================================

class ProactiveTrigger:
    """Base class for all proactive triggers"""
    
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category  # 'time_based' | 'event_based' | 'pattern_based'
    
    def should_trigger(self, item: Dict, context: Dict) -> Tuple[bool, float, str]:
        """
        Check if trigger condition is met.
        
        Returns:
            (should_alert, confidence_score, message)
        """
        raise NotImplementedError


class NoReplyFollowupTrigger(ProactiveTrigger):
    """Trigger when email hasn't been replied to in N days"""
    
    def __init__(self, threshold_days: int = 3):
        super().__init__("no_reply_followup", "time_based")
        self.threshold_days = threshold_days
    
    def should_trigger(self, item: Dict, context: Dict) -> Tuple[bool, float, str]:
        days_old = item.get('days_old', 0)
        
        if days_old < self.threshold_days:
            return False, 0.0, ""
        
        # Calculate confidence based on:
        # - How overdue (more days = higher confidence)
        # - Sender importance (VIP sender = boost confidence)
        # - Thread activity (multiple prior messages = boost)
        
        confidence = min(0.5 + (days_old - self.threshold_days) * 0.1, 0.95)
        
        # Boost for important contacts
        if item.get('sender_type') == 'vip':
            confidence += 0.15
        
        # Boost if there were prior replies (active thread going cold)
        if item.get('reply_count', 0) > 2:
            confidence += 0.1
        
        confidence = min(confidence, 0.98)
        
        message = (
            f"💬 {item['from_name']} hasn't replied in {days_old} days\n\n"
            f"Subject: {item['subject']}\n"
            f"Last sent: {item.get('last_action_date', 'Unknown')}\n\n"
            f"Want to send a follow-up?"
        )
        
        return True, confidence, message


class UrgentEndOfDayTrigger(ProactiveTrigger):
    """Trigger for urgent items in late afternoon"""
    
    def __init__(self, start_hour: int = 15, end_hour: int = 17):
        super().__init__("urgent_eod", "time_based")
        self.start_hour = start_hour
        self.end_hour = end_hour
    
    def should_trigger(self, item: Dict, context: Dict) -> Tuple[bool, float, str]:
        # Only trigger for urgent items
        if item.get('urgency') != 'urgent':
            return False, 0.0, ""
        
        # Only trigger in afternoon window
        current_hour = datetime.now().hour
        if not (self.start_hour <= current_hour <= self.end_hour):
            return False, 0.0, ""
        
        # Don't trigger on weekends
        if datetime.now().weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False, 0.0, ""
        
        # Higher confidence if item is very close to deadline
        deadline = item.get('deadline')
        confidence = 0.7
        
        if deadline:
            try:
                deadline_dt = datetime.fromisoformat(deadline)
                hours_until = (deadline_dt - datetime.now()).total_seconds() / 3600
                
                if hours_until < 4:  # Less than 4 hours
                    confidence = 0.95
                elif hours_until < 24:  # Less than 1 day
                    confidence = 0.85
            except:
                pass
        
        message = (
            f"⏰ URGENT: {item['subject']}\n\n"
            f"From: {item['from_name']}\n"
        )
        
        if deadline:
            message += f"Deadline: {deadline}\n\n"
        
        message += "Tackle this before end of day?"
        
        return True, confidence, message


class DraftUnsentTrigger(ProactiveTrigger):
    """Trigger when draft reply exists but wasn't sent"""
    
    def __init__(self, threshold_days: int = 2):
        super().__init__("draft_unsent", "event_based")
        self.threshold_days = threshold_days
    
    def should_trigger(self, item: Dict, context: Dict) -> Tuple[bool, float, str]:
        draft_id = item.get('related_draft_id')
        if not draft_id:
            return False, 0.0, ""
        
        # Check draft status
        draft_info = context.get('draft_info', {}).get(draft_id)
        if not draft_info:
            return False, 0.0, ""
        
        if draft_info.get('status') != 'pending':
            return False, 0.0, ""
        
        # Check age
        created_at = datetime.fromisoformat(draft_info['created_at'])
        days_old = (datetime.now() - created_at).days
        
        if days_old < self.threshold_days:
            return False, 0.0, ""
        
        confidence = 0.8  # High confidence - user clearly intended to reply
        
        message = (
            f"📧 You drafted a reply to {item['from_name']} {days_old} days ago\n\n"
            f"Subject: {item['subject']}\n"
            f"Draft: {draft_info.get('preview', 'No preview')[:100]}...\n\n"
            f"Ready to send?"
        )
        
        return True, confidence, message


class NewReplyReceivedTrigger(ProactiveTrigger):
    """Trigger immediately when new reply is received"""
    
    def __init__(self):
        super().__init__("new_reply", "event_based")
    
    def should_trigger(self, item: Dict, context: Dict) -> Tuple[bool, float, str]:
        # Only trigger if this is a new update (detected in current sync)
        if not item.get('is_new_update'):
            return False, 0.0, ""
        
        confidence = 0.9  # High confidence - user wants to know about replies
        
        message = (
            f"📥 New reply from {item['from_name']}\n\n"
            f"Subject: {item['subject']}\n"
            f"Preview: {item.get('preview', 'No preview')[:150]}...\n\n"
            f"Reply now or mark as read?"
        )
        
        return True, confidence, message


class PatternDetectionTrigger(ProactiveTrigger):
    """Trigger based on learned workflow patterns"""
    
    def __init__(self, patterns: List[Dict]):
        super().__init__("pattern_match", "pattern_based")
        self.patterns = patterns
    
    def should_trigger(self, item: Dict, context: Dict) -> Tuple[bool, float, str]:
        current_day = datetime.now().strftime('%A')
        current_hour = datetime.now().hour
        
        for pattern in self.patterns:
            # Check if pattern matches current context
            if pattern['day_of_week'] != current_day:
                continue
            
            hour_range = pattern['time_range'].split('-')
            start_hour = int(hour_range[0].split(':')[0])
            end_hour = int(hour_range[1].split(':')[0])
            
            if not (start_hour <= current_hour <= end_hour):
                continue
            
            # Check if item matches pattern task type
            if pattern['task_type'] not in item.get('tags', []):
                continue
            
            # Pattern matched!
            confidence = pattern['confidence']
            
            message = (
                f"📊 Pattern detected: {pattern['pattern_id']}\n\n"
                f"You usually {pattern['description']} on {current_day}s "
                f"around this time.\n\n"
                f"Ready to {pattern['suggested_action']}?\n\n"
                f"Item: {item['subject']}"
            )
            
            return True, confidence, message
        
        return False, 0.0, ""


# =============================================================================
# CONFIDENCE SCORER
# =============================================================================

class ConfidenceScorer:
    """
    Scores suggestion relevance to decide if it should be sent.
    
    Prevents spam by filtering low-confidence suggestions.
    """
    
    @staticmethod
    def calculate_score(
        base_confidence: float,
        item: Dict,
        user_history: Dict
    ) -> float:
        """
        Calculate final confidence score.
        
        Factors:
        - Base confidence from trigger (40%)
        - Item urgency level (30%)
        - Historical user acceptance rate for this trigger type (20%)
        - Business impact score (10%)
        """
        
        # Start with base confidence from trigger
        score = base_confidence * 0.4
        
        # Urgency boost
        urgency_scores = {'urgent': 1.0, 'normal': 0.6, 'low': 0.3}
        urgency_score = urgency_scores.get(item.get('urgency', 'normal'), 0.6)
        score += urgency_score * 0.3
        
        # Historical acceptance rate
        trigger_type = item.get('_trigger_type', 'unknown')
        acceptance_rate = user_history.get('acceptance_rates', {}).get(
            trigger_type, 0.5  # Default 50% if no history
        )
        score += acceptance_rate * 0.2
        
        # Business impact (VIP sender, high-value task, etc.)
        impact_score = 0.5
        if item.get('sender_type') == 'vip':
            impact_score += 0.3
        if 'compliance' in item.get('tags', []):
            impact_score += 0.2
        score += impact_score * 0.1
        
        return min(score, 1.0)


# =============================================================================
# SPAM FILTER
# =============================================================================

class SpamFilter:
    """Prevents overwhelming user with too many suggestions"""
    
    def __init__(self, config: ProactiveConfig):
        self.config = config
        self.suggestion_log = []  # In production, load from database
    
    def should_allow(self, item: Dict) -> bool:
        """Check if we should send suggestion for this item"""
        
        # Rule 1: Max 1 suggestion per item per day
        last_suggestion = item.get('last_bot_suggestion')
        if last_suggestion:
            last_time = datetime.fromisoformat(last_suggestion)
            hours_ago = (datetime.now() - last_time).total_seconds() / 3600
            
            if hours_ago < 24:
                logger.debug(
                    f"Skipping item {item['id']} - "
                    f"suggested {hours_ago:.1f}h ago"
                )
                return False
        
        # Rule 2: Respect quiet hours
        if self._is_quiet_hours():
            logger.debug("Quiet hours - deferring suggestion")
            return False
        
        # Rule 3: Don't spam same trigger type
        # (Allow max 3 of same type per day)
        trigger_type = item.get('_trigger_type', 'unknown')
        today_count = sum(
            1 for s in self.suggestion_log
            if s['type'] == trigger_type and
            (datetime.now() - datetime.fromisoformat(s['timestamp'])).days == 0
        )
        
        if today_count >= 3:
            logger.debug(f"Max daily suggestions reached for {trigger_type}")
            return False
        
        return True
    
    def _is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours"""
        if not self.config.QUIET_HOURS['enabled']:
            return False
        
        now = datetime.now()
        
        # Weekend check
        if now.weekday() >= 5 and self.config.QUIET_HOURS['weekend_all_day']:
            return True
        
        # Weekday night hours
        hour = now.hour
        start = self.config.QUIET_HOURS['weekday_start']
        end = self.config.QUIET_HOURS['weekday_end']
        
        if start > end:  # Crosses midnight
            return hour >= start or hour < end
        else:
            return start <= hour < end


# =============================================================================
# PROACTIVE ENGINE
# =============================================================================

class ProactiveEngine:
    """Main proactive intelligence engine"""
    
    def __init__(self, config: ProactiveConfig, telegram_bot):
        self.config = config
        self.bot = telegram_bot
        self.scorer = ConfidenceScorer()
        self.spam_filter = SpamFilter(config)
        
        # Initialize triggers
        self.triggers = self._load_triggers()
        
        # Load user history for scoring
        self.user_history = self._load_user_history()
    
    def _load_triggers(self) -> List[ProactiveTrigger]:
        """Load all trigger instances"""
        triggers = [
            NoReplyFollowupTrigger(self.config.NO_REPLY_DAYS),
            UrgentEndOfDayTrigger(
                self.config.URGENT_HOUR_START,
                self.config.URGENT_HOUR_END
            ),
            DraftUnsentTrigger(self.config.DRAFT_UNSENT_DAYS),
            NewReplyReceivedTrigger(),
        ]
        
        # Load pattern-based triggers from brain
        try:
            pattern_file = self.config.BRAIN_PATH / "pattern_learning.json"
            if pattern_file.exists():
                with open(pattern_file) as f:
                    data = json.load(f)
                    patterns = data.get('learned_patterns', [])
                    if patterns:
                        triggers.append(PatternDetectionTrigger(patterns))
        except Exception as e:
            logger.warning(f"Could not load patterns: {e}")
        
        return triggers
    
    def _load_user_history(self) -> Dict:
        """Load user interaction history for scoring"""
        # In production, load from database
        # For now, return defaults
        return {
            'acceptance_rates': {
                'no_reply_followup': 0.75,
                'urgent_eod': 0.65,
                'draft_unsent': 0.85,
                'new_reply': 0.90,
                'pattern_match': 0.70,
            }
        }
    
    async def check_all_items(self, workspace_items: List[Dict]):
        """
        Check all workspace items against trigger rules.
        Send suggestions for matched items.
        """
        logger.info(f"Checking {len(workspace_items)} workspace items...")
        
        context = {
            'draft_info': self._get_draft_info(),
            'current_time': datetime.now(),
        }
        
        suggestions_sent = 0
        
        for item in workspace_items:
            # Skip if spam filter blocks
            if not self.spam_filter.should_allow(item):
                continue
            
            # Check each trigger
            for trigger in self.triggers:
                should_alert, confidence, message = trigger.should_trigger(
                    item, context
                )
                
                if not should_alert:
                    continue
                
                # Add trigger type to item for scoring
                item['_trigger_type'] = trigger.name
                
                # Calculate final confidence score
                final_score = self.scorer.calculate_score(
                    confidence, item, self.user_history
                )
                
                logger.info(
                    f"Trigger '{trigger.name}' matched for item {item['id']} "
                    f"(confidence: {final_score:.2f})"
                )
                
                # Send suggestion if score meets threshold
                if final_score >= self.config.MIN_CONFIDENCE_SCORE:
                    await self._send_suggestion(
                        item, trigger.name, message, final_score
                    )
                    suggestions_sent += 1
                    
                    # Only one suggestion per item per check cycle
                    break
        
        logger.info(f"✅ Sent {suggestions_sent} proactive suggestions")
    
    async def _send_suggestion(
        self,
        item: Dict,
        trigger_type: str,
        message: str,
        confidence: float
    ):
        """Send proactive suggestion to user via Telegram"""
        
        # Format message with metadata
        full_message = f"{message}\n\n"
        full_message += f"_Confidence: {confidence*100:.0f}% | Item #{item['id']}_"
        
        # Send via Telegram bot
        try:
            await self.bot.send_message(full_message)
            logger.info(f"📤 Sent suggestion for item {item['id']}")
            
            # Log suggestion
            self._log_suggestion(item['id'], trigger_type, confidence)
            
            # Update item's last suggestion timestamp
            self._update_item_suggestion_time(item['id'])
            
        except Exception as e:
            logger.error(f"Failed to send suggestion: {e}")
    
    def _get_draft_info(self) -> Dict:
        """Get information about pending drafts"""
        # In production, query from database
        return {}
    
    def _log_suggestion(self, item_id: int, trigger_type: str, confidence: float):
        """Log suggestion to database"""
        self.spam_filter.suggestion_log.append({
            'item_id': item_id,
            'type': trigger_type,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat(),
            'user_action': None  # Updated when user responds
        })
    
    def _update_item_suggestion_time(self, item_id: int):
        """Update workspace item with latest suggestion timestamp"""
        # In production, update database
        pass


# =============================================================================
# MORNING DIGEST
# =============================================================================

async def send_morning_digest(bot, workspace_items: List[Dict]):
    """
    Send comprehensive morning summary.
    
    Provides overview of day's priorities.
    """
    logger.info("🌅 Generating morning digest...")
    
    if not workspace_items:
        await bot.send_message(
            "🌅 Good morning! Your workspace is empty. Nice work! 🎉"
        )
        return
    
    # Group by urgency
    urgent = [i for i in workspace_items if i.get('urgency') == 'urgent']
    normal = [i for i in workspace_items if i.get('urgency') == 'normal']
    low = [i for i in workspace_items if i.get('urgency') == 'low']
    
    # Build message
    lines = ["🌅 *Good morning!* Your MCP workspace:\n"]
    
    if urgent:
        lines.append("🔴 *URGENT TODAY*:")
        for item in urgent[:3]:  # Top 3
            lines.append(f"{item['id']}. {item['subject']}")
            lines.append(f"   From: {item['from_name']}")
            
            # Add context
            if item.get('days_old', 0) >= 3:
                lines.append(f"   ⚠️ {item['days_old']} days old - needs follow-up")
            
            deadline = item.get('deadline')
            if deadline:
                lines.append(f"   ⏰ Deadline: {deadline}")
        
        if len(urgent) > 3:
            lines.append(f"   ... and {len(urgent)-3} more urgent items\n")
        else:
            lines.append("")
    
    if normal:
        lines.append(f"🟡 *NEEDS ATTENTION* ({len(normal)} items):")
        for item in normal[:3]:
            lines.append(f"{item['id']}. {item['subject']} - {item['from_name']}")
        if len(normal) > 3:
            lines.append(f"   ... and {len(normal)-3} more")
        lines.append("")
    
    if low:
        lines.append(f"🟢 *LOW PRIORITY* ({len(low)} items)\n")
    
    lines.append("_Reply with number or tell me what you need!_")
    
    message = "\n".join(lines)
    await bot.send_message(message)


# =============================================================================
# BACKGROUND WORKERS
# =============================================================================

async def proactive_worker_loop(bot, config: ProactiveConfig):
    """
    Main background worker loop.
    
    Checks workspace periodically and sends proactive suggestions.
    """
    logger.info("🤖 Proactive worker started")
    
    engine = ProactiveEngine(config, bot)
    
    while True:
        try:
            logger.info("🔍 Running proactive checks...")
            
            # Get workspace items
            # In production, integrate with your workspace_manager
            workspace_items = []  # Replace with actual fetch
            
            # Run checks
            await engine.check_all_items(workspace_items)
            
            logger.info(
                f"✅ Check complete. Sleeping for "
                f"{config.CHECK_INTERVAL/3600:.1f} hours..."
            )
            
        except Exception as e:
            logger.error(f"❌ Proactive worker error: {e}")
        
        await asyncio.sleep(config.CHECK_INTERVAL)


async def morning_digest_scheduler(bot, config: ProactiveConfig):
    """Schedule morning digest to run at configured time"""
    logger.info("⏰ Morning digest scheduler started")
    
    while True:
        now = datetime.now()
        
        # Calculate time until next digest
        target = now.replace(
            hour=config.MORNING_DIGEST_HOUR,
            minute=config.MORNING_DIGEST_MINUTE,
            second=0,
            microsecond=0
        )
        
        if now >= target:
            target += timedelta(days=1)
        
        seconds_until = (target - now).total_seconds()
        
        logger.info(f"Next morning digest in {seconds_until/3600:.1f} hours")
        await asyncio.sleep(seconds_until)
        
        # Send digest
        workspace_items = []  # Replace with actual fetch
        await send_morning_digest(bot, workspace_items)


# =============================================================================
# INTEGRATION FUNCTIONS
# =============================================================================

async def start_proactive_engine(bot, config: Optional[ProactiveConfig] = None):
    """
    Start proactive engine with morning digest.
    
    Call this from your main Alamo Bot initialization:
    
        async def main():
            bot = AlamoBot()
            
            # Start reactive bot
            app = Application.builder().token(TOKEN).build()
            app.add_handler(MessageHandler(filters.TEXT, bot.handle_message))
            
            # Start proactive engine
            asyncio.create_task(start_proactive_engine(bot))
            
            # Run both together
            app.run_polling()
    """
    if config is None:
        config = ProactiveConfig()
    
    logger.info("🚀 Starting Proactive Engine...")
    
    await asyncio.gather(
        proactive_worker_loop(bot, config),
        morning_digest_scheduler(bot, config),
    )


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    """
    Run proactive engine as standalone worker.
    
    Usage:
        python alamo_bot_proactive.py
    
    Keep this running 24/7 using systemd, supervisor, or screen/tmux
    """
    
    print("🤖 Alamo Bot Proactive Engine")
    print("=" * 60)
    print("This worker runs in the background and sends proactive")
    print("suggestions based on your workspace activity.")
    print()
    print("Press Ctrl+C to stop.")
    print()
    
    # Create stub bot for testing
    class StubBot:
        async def send_message(self, text):
            print(f"\n[TELEGRAM] {text}\n")
    
    try:
        asyncio.run(start_proactive_engine(StubBot()))
    except KeyboardInterrupt:
        print("\n👋 Proactive Engine stopped")
