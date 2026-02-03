"""
MCP WORKSPACE MANAGER
=====================

This is the CORE module for the MCP Workspace System.

WHAT IT DOES:
- Manages your curated 5-10 "mcp" labeled emails in Gmail
- Syncs Gmail labels with local database
- Tracks workspace items (active, done, snoozed)
- Provides interface for Telegram bot to query/update workspace

WHY THIS EXISTS:
You don't need help managing ALL emails - just the 5-10 you've marked important.
This module treats those emails as a "workspace" that needs to be cleared.

HOW IT WORKS:
1. You label emails "mcp" in Gmail (manually)
2. This module syncs every 15 min and detects new labels
3. Stores metadata in local database
4. Telegram bot queries this to show you status
5. When you mark done, email moves to "mcp done" label

DEPENDENCIES:
- gmail_integration.py (your existing Gmail API wrapper)
- db_manager.py (SQLite database)
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

# Import your existing modules
# These should already exist from your Mode4 system
try:
    from gmail_integration import (
        get_gmail_service,
        get_label_id,
        get_threads_with_label,
        get_thread_details,
        add_label_to_thread,
        remove_label_from_thread,
    )
    from db_manager import get_db_connection
except ImportError:
    # Fallback for testing - you'll need to implement these
    logging.warning("Gmail/DB modules not found - using stubs")
    def get_gmail_service(): return None
    def get_label_id(gmail, name): return None
    def get_threads_with_label(gmail, label_id): return []
    def get_thread_details(gmail, thread_id): return {}
    def add_label_to_thread(gmail, thread_id, label_id): pass
    def remove_label_from_thread(gmail, thread_id, label_id): pass
    def get_db_connection(): return sqlite3.connect(':memory:')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_workspace_db():
    """
    Initialize the workspace_items table if it doesn't exist.
    
    This table stores all emails that are in your "mcp" workspace.
    Each row represents ONE email thread you need to act on.
    
    Call this once when setting up Mode4 for the first time.
    """
    db = get_db_connection()
    cursor = db.cursor()
    
    # Main workspace tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspace_items (
            -- Primary key
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Gmail identifiers (unique per thread)
            gmail_thread_id TEXT UNIQUE NOT NULL,
            gmail_message_id TEXT,  -- Latest message ID in thread
            
            -- Email metadata (what shows in your inbox)
            subject TEXT,
            from_email TEXT,        -- "jason@example.com"
            from_name TEXT,         -- "Jason Smith"
            snippet TEXT,           -- First ~200 chars preview
            
            -- Status tracking
            status TEXT DEFAULT 'active',  -- active | done | snoozed
            urgency TEXT DEFAULT 'normal', -- urgent | normal | low
            
            -- Timestamps (helps with proactive suggestions)
            added_to_workspace TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_gmail_activity TIMESTAMP,  -- Last time Gmail had activity
            last_bot_suggestion TIMESTAMP,  -- Last time bot suggested action
            completed_at TIMESTAMP,
            snoozed_until TIMESTAMP,
            
            -- Relationships to other Mode4 features
            related_task_id INTEGER,        -- Link to tasks table
            related_draft_id TEXT,          -- Link to draft_contexts
            
            -- Bot intelligence tracking
            bot_notes TEXT,                 -- "Waiting on Jason reply", etc.
            suggestion_count INTEGER DEFAULT 0,  -- How many times bot suggested
            
            FOREIGN KEY (related_task_id) REFERENCES tasks(id)
        )
    """)
    
    # Indexes for fast queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_workspace_status 
        ON workspace_items(status)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_workspace_thread 
        ON workspace_items(gmail_thread_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_workspace_urgency 
        ON workspace_items(urgency, status)
    """)
    
    db.commit()
    db.close()
    
    logger.info("✅ Workspace database initialized")


# ============================================================================
# GMAIL SYNC (The Heart of the System)
# ============================================================================

def sync_workspace_with_gmail():
    """
    Sync your local workspace database with Gmail's "mcp" label.
    
    This is the CORE function that runs every 15 minutes.
    
    WHAT IT DOES:
    1. Gets all Gmail threads with "mcp" label
    2. Compares with local database
    3. Adds new items (you labeled something new)
    4. Removes items (you unlabeled or moved to "mcp done")
    5. Updates existing items (new replies detected)
    
    RETURNS:
    Dict with sync stats: {
        'added': 2,      # New items added to workspace
        'removed': 1,    # Items marked done
        'updated': 3,    # Items with new activity
        'total': 6       # Total active workspace items
    }
    """
    logger.info("🔄 Starting workspace sync with Gmail...")
    
    stats = {
        'added': 0,
        'removed': 0,
        'updated': 0,
        'total': 0
    }
    
    try:
        # Get Gmail service
        gmail = get_gmail_service()
        if not gmail:
            logger.error("❌ Failed to get Gmail service")
            return stats
        
        # Get the "mcp" label ID
        mcp_label_id = get_label_id(gmail, 'mcp')
        if not mcp_label_id:
            logger.error("❌ 'mcp' label not found in Gmail. Please create it first.")
            return stats
        
        # Get all current threads with "mcp" label from Gmail
        gmail_threads = get_threads_with_label(gmail, mcp_label_id)
        gmail_thread_ids = set(gmail_threads)
        
        logger.info(f"📧 Found {len(gmail_threads)} threads with 'mcp' label in Gmail")
        
        # Get all active workspace items from database
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            SELECT gmail_thread_id FROM workspace_items 
            WHERE status='active'
        """)
        db_threads = {row[0] for row in cursor.fetchall()}
        
        logger.info(f"💾 Found {len(db_threads)} active items in local database")
        
        # STEP 1: Find NEW items (in Gmail but not in DB)
        # These are emails you just labeled "mcp"
        new_thread_ids = gmail_thread_ids - db_threads
        for thread_id in new_thread_ids:
            if add_to_workspace(gmail, thread_id, cursor):
                stats['added'] += 1
        
        # STEP 2: Find REMOVED items (in DB but not in Gmail)
        # These are emails you unlabeled or moved to "mcp done"
        removed_thread_ids = db_threads - gmail_thread_ids
        for thread_id in removed_thread_ids:
            if mark_workspace_done(thread_id, "removed_from_label", cursor):
                stats['removed'] += 1
        
        # STEP 3: Update EXISTING items (check for new activity)
        # These are emails still in both places - check if replies came in
        existing_thread_ids = db_threads & gmail_thread_ids
        for thread_id in existing_thread_ids:
            if check_for_updates(gmail, thread_id, cursor):
                stats['updated'] += 1
        
        # Commit all changes
        db.commit()
        
        # Get final count
        cursor.execute("SELECT COUNT(*) FROM workspace_items WHERE status='active'")
        stats['total'] = cursor.fetchone()[0]
        
        db.close()
        
        logger.info(f"✅ Sync complete: +{stats['added']} -{stats['removed']} ~{stats['updated']} = {stats['total']} total")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        return stats


def add_to_workspace(gmail, thread_id: str, cursor) -> bool:
    """
    Add a NEW email thread to workspace.
    
    Called when you label an email "mcp" in Gmail.
    
    WHAT IT DOES:
    1. Fetches thread details from Gmail
    2. Extracts metadata (subject, from, snippet)
    3. Detects urgency based on keywords
    4. Saves to database
    5. Returns True if successful
    
    URGENCY DETECTION:
    - Looks for keywords: "urgent", "asap", "today", "compliance", "finra"
    - You can manually override later with /urgency command
    """
    try:
        logger.info(f"➕ Adding new workspace item: {thread_id}")
        
        # Get thread details from Gmail
        thread = get_thread_details(gmail, thread_id)
        if not thread:
            logger.error(f"❌ Could not fetch thread {thread_id}")
            return False
        
        # Extract latest message in thread
        messages = thread.get('messages', [])
        if not messages:
            logger.error(f"❌ Thread {thread_id} has no messages")
            return False
        
        latest_message = messages[-1]  # Most recent message
        message_id = latest_message['id']
        
        # Parse email headers
        headers = {h['name']: h['value'] 
                  for h in latest_message['payload']['headers']}
        
        subject = headers.get('Subject', '(No Subject)')
        from_field = headers.get('From', '')
        
        # Extract name from "Name <email@example.com>" format
        from_name = extract_name_from_email(from_field)
        from_email = extract_email_from_field(from_field)
        
        # Get snippet (preview text)
        snippet = latest_message.get('snippet', '')[:200]
        
        # Detect urgency (simple keyword matching)
        urgency = detect_urgency(subject, snippet)
        
        # Get timestamp of latest activity
        gmail_timestamp = int(latest_message['internalDate']) / 1000
        last_activity = datetime.fromtimestamp(gmail_timestamp)
        
        # Insert into database
        cursor.execute("""
            INSERT INTO workspace_items (
                gmail_thread_id, gmail_message_id,
                subject, from_email, from_name, snippet,
                urgency, last_gmail_activity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            thread_id, message_id,
            subject, from_email, from_name, snippet,
            urgency, last_activity
        ))
        
        logger.info(f"✅ Added: {subject} (from {from_name})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to add {thread_id}: {e}")
        return False


def check_for_updates(gmail, thread_id: str, cursor) -> bool:
    """
    Check if an existing workspace item has new activity.
    
    Called during sync for items already in workspace.
    
    WHAT IT DOES:
    1. Compares Gmail's latest message time with our stored time
    2. If newer → updates database
    3. Returns True if update found (triggers alert to you)
    
    This is how you get notified when someone replies to a workspace email.
    """
    try:
        # Get our stored timestamp
        cursor.execute("""
            SELECT last_gmail_activity, subject, from_name 
            FROM workspace_items 
            WHERE gmail_thread_id=?
        """, (thread_id,))
        
        row = cursor.fetchone()
        if not row:
            return False
        
        stored_activity, subject, from_name = row
        stored_time = datetime.fromisoformat(stored_activity)
        
        # Get latest message from Gmail
        thread = get_thread_details(gmail, thread_id)
        if not thread or 'messages' not in thread:
            return False
        
        latest_message = thread['messages'][-1]
        gmail_timestamp = int(latest_message['internalDate']) / 1000
        gmail_time = datetime.fromtimestamp(gmail_timestamp)
        
        # New activity detected?
        if gmail_time > stored_time:
            logger.info(f"🔔 New activity on: {subject}")
            
            # Update database
            cursor.execute("""
                UPDATE workspace_items 
                SET last_gmail_activity=?, gmail_message_id=?
                WHERE gmail_thread_id=?
            """, (gmail_time, latest_message['id'], thread_id))
            
            # This will trigger an alert in Telegram
            # (handled by proactive_engine.py)
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Failed to check updates for {thread_id}: {e}")
        return False


def mark_workspace_done(
    thread_id: str, 
    reason: str = "user_marked_done",
    cursor = None
) -> bool:
    """
    Mark a workspace item as DONE.
    
    Called when:
    1. You say "/done <id>" in Telegram
    2. You remove "mcp" label in Gmail
    3. Bot detects email moved to "mcp done"
    
    WHAT IT DOES:
    1. Updates status to 'done' in database
    2. Sets completed_at timestamp
    3. Moves email to "mcp done" label in Gmail
    4. Returns True if successful
    
    The email stays in database for history/stats but won't show in active workspace.
    """
    try:
        logger.info(f"✅ Marking done: {thread_id} (reason: {reason})")
        
        close_db = False
        if cursor is None:
            db = get_db_connection()
            cursor = db.cursor()
            close_db = True
        
        # Update status
        cursor.execute("""
            UPDATE workspace_items
            SET status='done', completed_at=?
            WHERE gmail_thread_id=? AND status='active'
        """, (datetime.now(), thread_id))
        
        if cursor.rowcount == 0:
            logger.warning(f"⚠️ Thread {thread_id} not found or already done")
            return False
        
        # Move to "mcp done" label in Gmail
        if reason == "user_marked_done":
            gmail = get_gmail_service()
            if gmail:
                mcp_label = get_label_id(gmail, 'mcp')
                done_label = get_label_id(gmail, 'mcp done')
                
                if mcp_label:
                    remove_label_from_thread(gmail, thread_id, mcp_label)
                if done_label:
                    add_label_to_thread(gmail, thread_id, done_label)
        
        if close_db:
            db.commit()
            db.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to mark done {thread_id}: {e}")
        return False


# ============================================================================
# QUERY FUNCTIONS (Used by Telegram Bot)
# ============================================================================

def get_workspace_items(
    status: str = 'active',
    urgency: Optional[str] = None,
    keyword: Optional[str] = None
) -> List[Dict]:
    """
    Get workspace items matching filters.
    
    Used by Telegram bot to show you your workspace.
    
    EXAMPLES:
    - get_workspace_items() → all active items
    - get_workspace_items(urgency='urgent') → only urgent items
    - get_workspace_items(keyword='jason') → items mentioning jason
    
    RETURNS:
    List of dicts with all item details:
    [
        {
            'id': 1,
            'subject': 'Invoice request',
            'from_name': 'Jason',
            'urgency': 'normal',
            'days_old': 2,
            ...
        },
        ...
    ]
    """
    db = get_db_connection()
    cursor = db.cursor()
    
    # Build query with filters
    query = "SELECT * FROM workspace_items WHERE status=?"
    params = [status]
    
    if urgency:
        query += " AND urgency=?"
        params.append(urgency)
    
    if keyword:
        query += " AND (subject LIKE ? OR from_name LIKE ? OR from_email LIKE ?)"
        keyword_pattern = f"%{keyword}%"
        params.extend([keyword_pattern, keyword_pattern, keyword_pattern])
    
    # Order by urgency first, then by age
    query += " ORDER BY CASE urgency WHEN 'urgent' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, last_gmail_activity DESC"
    
    cursor.execute(query, params)
    
    # Convert rows to dicts
    columns = [desc[0] for desc in cursor.description]
    items = []
    
    for row in cursor.fetchall():
        item = dict(zip(columns, row))
        
        # Add computed fields
        last_activity = datetime.fromisoformat(item['last_gmail_activity'])
        item['days_old'] = (datetime.now() - last_activity).days
        item['hours_old'] = (datetime.now() - last_activity).total_seconds() / 3600
        
        items.append(item)
    
    db.close()
    return items


def get_workspace_item_by_id(item_id: int) -> Optional[Dict]:
    """Get a single workspace item by ID."""
    items = get_workspace_items()
    for item in items:
        if item['id'] == item_id:
            return item
    return None


def get_workspace_item_by_thread(thread_id: str) -> Optional[Dict]:
    """Get a single workspace item by Gmail thread ID."""
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM workspace_items WHERE gmail_thread_id=?", (thread_id,))
    row = cursor.fetchone()
    
    if not row:
        db.close()
        return None
    
    columns = [desc[0] for desc in cursor.description]
    item = dict(zip(columns, row))
    
    db.close()
    return item


def update_workspace_item(item_id: int, **kwargs):
    """
    Update workspace item fields.
    
    EXAMPLES:
    - update_workspace_item(1, urgency='urgent')
    - update_workspace_item(2, bot_notes='Waiting on Jason')
    - update_workspace_item(3, snoozed_until=datetime(...))
    """
    db = get_db_connection()
    cursor = db.cursor()
    
    # Build UPDATE query dynamically
    fields = []
    values = []
    
    for key, value in kwargs.items():
        fields.append(f"{key}=?")
        values.append(value)
    
    if not fields:
        db.close()
        return
    
    values.append(item_id)
    
    query = f"UPDATE workspace_items SET {', '.join(fields)} WHERE id=?"
    cursor.execute(query, values)
    
    db.commit()
    db.close()
    
    logger.info(f"✅ Updated workspace item {item_id}: {kwargs}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_name_from_email(from_field: str) -> str:
    """
    Extract name from "Name <email@example.com>" format.
    
    Examples:
    - "Jason Smith <jason@example.com>" → "Jason Smith"
    - "jason@example.com" → "jason"
    """
    if '<' in from_field:
        return from_field.split('<')[0].strip().strip('"')
    return from_field.split('@')[0]


def extract_email_from_field(from_field: str) -> str:
    """
    Extract email from "Name <email@example.com>" format.
    
    Examples:
    - "Jason Smith <jason@example.com>" → "jason@example.com"
    - "jason@example.com" → "jason@example.com"
    """
    if '<' in from_field:
        return from_field.split('<')[1].rstrip('>')
    return from_field


def detect_urgency(subject: str, snippet: str) -> str:
    """
    Auto-detect urgency based on keywords.
    
    Returns: 'urgent' | 'normal' | 'low'
    
    URGENT KEYWORDS:
    - urgent, asap, today, now, immediately
    - compliance, finra, audit (your work context)
    - deadline, due today
    
    LOW KEYWORDS:
    - fyi, for your information, no rush
    
    Default: normal
    """
    text = (subject + ' ' + snippet).lower()
    
    # Check urgent keywords
    urgent_keywords = [
        'urgent', 'asap', 'today', 'now', 'immediately',
        'compliance', 'finra', 'audit', 'regulatory',
        'deadline', 'due today', 'eod', 'end of day'
    ]
    
    if any(kw in text for kw in urgent_keywords):
        return 'urgent'
    
    # Check low priority keywords
    low_keywords = ['fyi', 'for your information', 'no rush', 'when you can']
    
    if any(kw in text for kw in low_keywords):
        return 'low'
    
    return 'normal'


def format_workspace_summary(items: List[Dict]) -> str:
    """
    Format workspace items for Telegram display.
    
    Used in morning digest and /workspace command.
    
    Returns nice formatted text like:
    
    🔴 URGENT:
    1. Compliance call prep - George (today)
    
    🟡 ACTIVE:
    2. Invoice request - Jason (2 days ago)
    3. Mandate review - Chris D (5 hours ago)
    """
    if not items:
        return "✅ Your workspace is empty! Nice work."
    
    # Group by urgency
    urgent = [i for i in items if i['urgency'] == 'urgent']
    normal = [i for i in items if i['urgency'] == 'normal']
    low = [i for i in items if i['urgency'] == 'low']
    
    lines = []
    
    if urgent:
        lines.append("🔴 URGENT:")
        for item in urgent:
            age = format_age(item['days_old'], item['hours_old'])
            lines.append(f"{item['id']}. {item['subject']} - {item['from_name']} ({age})")
        lines.append("")
    
    if normal:
        lines.append("🟡 ACTIVE:")
        for item in normal:
            age = format_age(item['days_old'], item['hours_old'])
            lines.append(f"{item['id']}. {item['subject']} - {item['from_name']} ({age})")
        lines.append("")
    
    if low:
        lines.append("🟢 LOW PRIORITY:")
        for item in low:
            age = format_age(item['days_old'], item['hours_old'])
            lines.append(f"{item['id']}. {item['subject']} - {item['from_name']} ({age})")
    
    return "\n".join(lines)


def format_age(days: int, hours: float) -> str:
    """Format time ago in human-readable way."""
    if days == 0:
        if hours < 1:
            return "just now"
        return f"{int(hours)} hours ago"
    elif days == 1:
        return "yesterday"
    else:
        return f"{days} days ago"


# ============================================================================
# MAIN EXECUTION (For Testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test the workspace manager.
    
    Run this directly to:
    1. Initialize database
    2. Test sync with Gmail
    3. Display current workspace
    """
    print("🚀 MCP Workspace Manager - Test Mode")
    print("=" * 50)
    
    # Initialize database
    print("\n1. Initializing database...")
    init_workspace_db()
    
    # Test sync
    print("\n2. Syncing with Gmail...")
    stats = sync_workspace_with_gmail()
    print(f"   Added: {stats['added']}")
    print(f"   Removed: {stats['removed']}")
    print(f"   Updated: {stats['updated']}")
    print(f"   Total: {stats['total']}")
    
    # Display workspace
    print("\n3. Current workspace:")
    items = get_workspace_items()
    print(format_workspace_summary(items))
    
    print("\n✅ Test complete!")
