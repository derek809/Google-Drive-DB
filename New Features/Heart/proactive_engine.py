"""
PROACTIVE ENGINE
================

This module makes Mode4 feel PROACTIVE instead of just reactive.

WHAT IT DOES:
- Runs in background every 2 hours
- Checks each workspace item for triggers
- Sends smart suggestions to Telegram
- Doesn't spam (max 1 suggestion per item per day)

WHY THIS EXISTS:
You want Mode4 to remind you about:
- Emails that haven't been replied to in 3+ days
- Urgent items approaching end of day
- Drafts you created but never sent
- Patterns in your workflow (Thursday invoices, etc.)

HOW IT WORKS:
1. Gets all active workspace items
2. Checks time-based rules (3 days old? Urgent + late afternoon?)
3. Checks event-based rules (new reply? draft unsent?)
4. Checks pattern-based rules (learned from your habits)
5. Sends Telegram alert if rule matches
6. Logs suggestion to avoid spamming

BACKGROUND WORKER:
Run this as a separate process:
    python proactive_engine.py

Or integrate into your main bot with:
    asyncio.create_task(proactive_worker_loop())
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

# Your existing modules
from workspace_manager import (
    get_workspace_items,
    get_workspace_item_by_id,
    update_workspace_item,
    sync_workspace_with_gmail,
)
from db_manager import get_db_connection

# For sending Telegram alerts
# You'll need to adapt this to your telegram_handler.py
try:
    from telegram_handler import send_telegram_message
except ImportError:
    # Stub for testing
    async def send_telegram_message(text):
        print(f"[TELEGRAM] {text}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# How often to run proactive checks (in seconds)
CHECK_INTERVAL = 2 * 60 * 60  # 2 hours

# Max suggestions per item per day (prevent spam)
MAX_SUGGESTIONS_PER_DAY = 1

# Trigger thresholds
NO_REPLY_DAYS_THRESHOLD = 3      # Suggest follow-up after 3 days
URGENT_HOUR_START = 15           # 3pm
URGENT_HOUR_END = 17             # 5pm
DRAFT_UNSENT_DAYS_THRESHOLD = 2  # Remind if draft unsent for 2 days


# ============================================================================
# MAIN PROACTIVE WORKER
# ============================================================================

async def proactive_worker_loop():
    """
    Main background worker loop.
    
    Runs continuously, checking workspace every 2 hours.
    
    This should be started when Mode4 boots up and run forever.
    """
    logger.info("🤖 Proactive Engine started")
    
    while True:
        try:
            logger.info("🔍 Running proactive checks...")
            
            # First, sync with Gmail to catch new activity
            await sync_workspace()
            
            # Then run all proactive checks
            await run_all_checks()
            
            logger.info(f"✅ Check complete. Sleeping for {CHECK_INTERVAL/3600} hours...")
            
        except Exception as e:
            logger.error(f"❌ Proactive worker error: {e}")
        
        # Wait before next check
        await asyncio.sleep(CHECK_INTERVAL)


async def sync_workspace():
    """Sync with Gmail before checking triggers."""
    stats = sync_workspace_with_gmail()
    
    # Alert user about new activity
    if stats['added'] > 0:
        items = get_workspace_items()
        new_items = sorted(items, key=lambda x: x['added_to_workspace'], reverse=True)[:stats['added']]
        
        for item in new_items:
            await send_telegram_message(
                f"📥 New workspace item:\n"
                f"{item['subject']}\n"
                f"From: {item['from_name']}"
            )
    
    if stats['updated'] > 0:
        # New replies detected - alert immediately
        await alert_new_replies()


async def run_all_checks():
    """
    Run all proactive check rules.
    
    This is where the "intelligence" lives.
    Each check function looks for a specific trigger and suggests action.
    """
    items = get_workspace_items(status='active')
    
    if not items:
        logger.info("No active workspace items - nothing to check")
        return
    
    logger.info(f"Checking {len(items)} workspace items...")
    
    for item in items:
        # Skip if we already suggested something today
        if should_skip_suggestion(item):
            continue
        
        # Time-based checks
        await check_no_reply_followup(item)
        await check_urgent_eod(item)
        
        # Event-based checks
        await check_draft_unsent(item)
        
        # Pattern-based checks (future)
        # await check_weekly_patterns(item)


# ============================================================================
# TIME-BASED CHECKS
# ============================================================================

async def check_no_reply_followup(item: Dict):
    """
    RULE: No reply in 3+ days → suggest follow-up
    
    This is your most common use case:
    - You sent an email or waiting on someone
    - 3 days pass with no reply
    - Bot reminds you to follow up
    
    Example alert:
    "💬 Laura Clarke hasn't replied in 5 days. Follow up?"
    """
    days_old = item['days_old']
    
    if days_old >= NO_REPLY_DAYS_THRESHOLD:
        await suggest(
            item,
            suggestion_type='follow_up',
            message=(
                f"💬 {item['from_name']} hasn't replied in {days_old} days.\n"
                f"Subject: {item['subject']}\n\n"
                f"Want to send a follow-up?"
            )
        )


async def check_urgent_eod(item: Dict):
    """
    RULE: Urgent item + late afternoon (3-5pm) → remind before EOD
    
    You marked something urgent but haven't addressed it yet.
    Bot reminds you in the afternoon so you can tackle it before end of day.
    
    Example alert:
    "⏰ Urgent: Compliance call prep - tackle before EOD?"
    """
    if item['urgency'] != 'urgent':
        return
    
    hour = datetime.now().hour
    
    if URGENT_HOUR_START <= hour <= URGENT_HOUR_END:
        await suggest(
            item,
            suggestion_type='urgent_eod',
            message=(
                f"⏰ Urgent: {item['subject']}\n"
                f"From: {item['from_name']}\n\n"
                f"Tackle this before EOD?"
            )
        )


# ============================================================================
# EVENT-BASED CHECKS
# ============================================================================

async def check_draft_unsent(item: Dict):
    """
    RULE: Draft exists but not sent for 2+ days → remind to send
    
    You drafted a reply but forgot to send it.
    Bot reminds you after 2 days.
    
    Requires: item['related_draft_id'] to be set when draft created
    
    Example alert:
    "📧 You drafted a reply to Jason 2 days ago - ready to send?"
    """
    if not item.get('related_draft_id'):
        return
    
    # Check if draft is still pending (not sent)
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT created_at, status FROM draft_contexts 
        WHERE draft_id=?
    """, (item['related_draft_id'],))
    
    row = cursor.fetchone()
    db.close()
    
    if not row:
        return
    
    created_at, status = row
    
    if status != 'pending':  # Already sent or cancelled
        return
    
    # Check age
    draft_age = (datetime.now() - datetime.fromisoformat(created_at)).days
    
    if draft_age >= DRAFT_UNSENT_DAYS_THRESHOLD:
        await suggest(
            item,
            suggestion_type='draft_unsent',
            message=(
                f"📧 You drafted a reply to {item['from_name']} {draft_age} days ago.\n"
                f"Subject: {item['subject']}\n\n"
                f"Ready to send it?"
            )
        )


async def alert_new_replies():
    """
    RULE: New reply detected → alert immediately
    
    This is event-driven, not time-based.
    Someone replied to a workspace email - tell user right away.
    
    Example alert:
    "🔔 Jason replied to your invoice email!"
    """
    # Get items updated in last sync
    items = get_workspace_items()
    
    for item in items:
        # Check if last_gmail_activity is recent (within last 15 min)
        last_activity = datetime.fromisoformat(item['last_gmail_activity'])
        minutes_ago = (datetime.now() - last_activity).total_seconds() / 60
        
        if minutes_ago <= 15:  # Very recent activity
            # Check if we already alerted about this
            db = get_db_connection()
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT id FROM suggestion_log
                WHERE workspace_item_id=? 
                AND suggestion_type='new_reply'
                AND suggested_at > ?
            """, (item['id'], last_activity))
            
            already_alerted = cursor.fetchone() is not None
            db.close()
            
            if not already_alerted:
                await send_telegram_message(
                    f"🔔 {item['from_name']} replied!\n"
                    f"Subject: {item['subject']}\n\n"
                    f"Want to read it or mark as done?"
                )
                
                # Log this alert
                log_suggestion(item['id'], 'new_reply')


# ============================================================================
# PATTERN-BASED CHECKS (Future Enhancement)
# ============================================================================

async def check_weekly_patterns(item: Dict):
    """
    RULE: Learned patterns → suggest proactively
    
    This is FUTURE functionality - learns your habits over time.
    
    Examples:
    - "You usually invoice Jason on Thursdays - draft one now?"
    - "Compliance calls are Fridays at 2pm - prep materials?"
    - "You batch mandate reviews on Mondays - 3 ready to review"
    
    Implementation:
    1. Track when you complete certain types of tasks
    2. Find patterns (day of week, time of day, frequency)
    3. Suggest same action when pattern matches
    
    This requires at least 2-4 weeks of data to learn patterns.
    """
    # TODO: Implement pattern learning
    # For now, you can manually code common patterns:
    
    day_of_week = datetime.now().strftime('%A')
    hour = datetime.now().hour
    
    # Example: Thursday invoicing pattern
    if day_of_week == 'Thursday' and 9 <= hour <= 11:
        if 'invoice' in item['subject'].lower():
            await suggest(
                item,
                suggestion_type='pattern_invoice',
                message=(
                    f"📊 Pattern detected: You usually handle invoices Thursday mornings.\n"
                    f"Invoice from {item['from_name']} ready to process?"
                )
            )


# ============================================================================
# SUGGESTION MANAGEMENT
# ============================================================================

async def suggest(item: Dict, suggestion_type: str, message: str):
    """
    Send a suggestion to user via Telegram.
    
    Also logs the suggestion to prevent spam.
    
    Args:
        item: Workspace item dict
        suggestion_type: follow_up | urgent_eod | draft_unsent | etc.
        message: Text to send to user
    """
    logger.info(f"💡 Suggesting: {suggestion_type} for item {item['id']}")
    
    # Send to Telegram
    await send_telegram_message(message)
    
    # Update workspace item
    update_workspace_item(
        item['id'],
        last_bot_suggestion=datetime.now(),
        suggestion_count=item.get('suggestion_count', 0) + 1
    )
    
    # Log suggestion
    log_suggestion(item['id'], suggestion_type)


def should_skip_suggestion(item: Dict) -> bool:
    """
    Check if we should skip suggesting for this item.
    
    Prevents spam by enforcing:
    - Max 1 suggestion per item per day
    
    Returns True if we should skip (already suggested today)
    """
    last_suggestion = item.get('last_bot_suggestion')
    
    if not last_suggestion:
        return False  # Never suggested - go ahead
    
    last_time = datetime.fromisoformat(last_suggestion)
    hours_ago = (datetime.now() - last_time).total_seconds() / 3600
    
    if hours_ago < 24:
        logger.debug(f"Skipping item {item['id']} - suggested {hours_ago:.1f}h ago")
        return True
    
    return False


def log_suggestion(workspace_item_id: int, suggestion_type: str):
    """
    Log a suggestion to database.
    
    This helps track:
    - What suggestions we've made
    - How users respond to them
    - Effectiveness of different suggestion types
    """
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("""
        INSERT INTO suggestion_log (workspace_item_id, suggestion_type)
        VALUES (?, ?)
    """, (workspace_item_id, suggestion_type))
    
    db.commit()
    db.close()


def update_suggestion_response(suggestion_id: int, user_action: str):
    """
    Update how user responded to a suggestion.
    
    Called from Telegram handler when user:
    - Accepts: "yes" / clicks action button
    - Dismisses: "no" / "not now"
    - Ignores: no response for 24 hours
    
    user_action: 'accepted' | 'dismissed' | 'ignored'
    
    This data can train better suggestions in the future.
    """
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("""
        UPDATE suggestion_log
        SET user_action=?
        WHERE id=?
    """, (user_action, suggestion_id))
    
    db.commit()
    db.close()


# ============================================================================
# MORNING DIGEST
# ============================================================================

async def send_morning_digest():
    """
    Send morning summary at 7am.
    
    This is a special type of proactive message - runs once per day.
    
    Shows:
    - Urgent items for today
    - Items needing attention
    - Quick overview of workspace health
    
    Call this from a scheduled job (cron or asyncio scheduler)
    """
    logger.info("🌅 Generating morning digest...")
    
    items = get_workspace_items(status='active')
    
    if not items:
        await send_telegram_message(
            "🌅 Good morning! Your workspace is empty. Nice work! 🎉"
        )
        return
    
    # Group by urgency
    urgent = [i for i in items if i['urgency'] == 'urgent']
    normal = [i for i in items if i['urgency'] == 'normal']
    low = [i for i in items if i['urgency'] == 'low']
    
    # Build message
    lines = ["🌅 Good morning! Your MCP workspace:\n"]
    
    if urgent:
        lines.append("🔴 URGENT TODAY:")
        for item in urgent:
            lines.append(f"{item['id']}. {item['subject']} - {item['from_name']}")
            # Add suggestion if applicable
            if item['days_old'] >= 3:
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
    await send_telegram_message(message)


# ============================================================================
# SCHEDULED TASKS
# ============================================================================

async def schedule_morning_digest():
    """
    Schedule morning digest to run at 7am daily.
    
    This runs in its own async loop alongside the proactive worker.
    """
    logger.info("⏰ Morning digest scheduler started")
    
    while True:
        now = datetime.now()
        
        # Calculate time until next 7am
        target = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)  # Tomorrow's 7am
        
        seconds_until = (target - now).total_seconds()
        
        logger.info(f"Next morning digest in {seconds_until/3600:.1f} hours")
        await asyncio.sleep(seconds_until)
        
        # Send digest
        await send_morning_digest()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main():
    """
    Start all background workers.
    
    Run this to start the proactive engine:
        python proactive_engine.py
    
    Or integrate into your main bot startup.
    """
    logger.info("🚀 Starting Proactive Engine...")
    
    # Start both workers concurrently
    await asyncio.gather(
        proactive_worker_loop(),      # Check workspace every 2 hours
        schedule_morning_digest(),    # Send digest at 7am daily
    )


if __name__ == "__main__":
    """
    Run as standalone background worker.
    
    Usage:
        python proactive_engine.py
    
    Keep this running 24/7 (use systemd, supervisor, or screen/tmux)
    """
    print("🤖 MCP Proactive Engine")
    print("=" * 50)
    print("This worker runs in the background and sends proactive suggestions.")
    print("Press Ctrl+C to stop.")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Proactive Engine stopped")
