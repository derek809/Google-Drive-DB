"""
CONVERSATION MEMORY
===================

This module enables NATURAL conversation flow by remembering context.

WHY THIS EXISTS:
Without memory, every message is isolated:
    You: "Draft invoice to Jason"
    Bot: [creates draft]
    You: "Make it shorter"
    Bot: "Make what shorter?" ❌

With memory:
    You: "Draft invoice to Jason"
    Bot: [creates draft, REMEMBERS draft_id]
    You: "Make it shorter"
    Bot: [revises SAME draft] ✅

WHAT IT TRACKS:
- Last draft you created
- Last workspace item you mentioned
- Last person you talked about
- Last email thread you referenced
- Last file you accessed
- Last action you took

HOW IT WORKS:
1. Every time you do something, bot calls memory.remember()
2. Context expires after 10 min of inactivity (TTL)
3. When you say "it" / "that" / "this", bot calls memory.resolve()
4. Bot gets the right context and acts on it

EXAMPLES:

Example 1: Draft Flow
    memory.remember(user_id, last_draft_id="draft_123")
    [10 min later]
    resolve_reference(user_id, "send it")
    → Returns: {'type': 'draft', 'id': 'draft_123'}

Example 2: Workspace Flow
    memory.remember(user_id, last_workspace_item_id=42)
    [5 min later]
    resolve_reference(user_id, "mark done")
    → Returns: {'type': 'workspace_item', 'id': 42}

Example 3: Multi-turn
    You: "Draft to Jason about the invoice"
    memory.remember(last_draft_id=X, last_person="Jason", last_topic="invoice")
    
    You: "Add Tom to CC"
    resolve → knows which draft
    
    You: "Actually make it shorter"
    resolve → still same draft
    
    You: "Perfect send it"
    resolve → sends draft X
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from db_manager import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ConversationContext:
    """
    Represents what the bot remembers about recent conversation.
    
    All fields are optional - only set what's relevant.
    """
    # Draft context
    last_draft_id: Optional[str] = None
    
    # Workspace context
    last_workspace_item_id: Optional[int] = None
    last_email_thread_id: Optional[str] = None
    
    # People context
    last_mentioned_person: Optional[str] = None
    last_mentioned_email: Optional[str] = None
    
    # Action context
    last_action: Optional[str] = None  # "drafted_email", "sent_email", etc.
    last_action_target: Optional[str] = None  # Who/what was the action about
    
    # File context
    last_file_id: Optional[str] = None
    last_file_name: Optional[str] = None
    
    # Topic context
    last_topic: Optional[str] = None  # "invoice", "mandate", etc.
    
    # Timestamps
    created_at: datetime = None
    updated_at: datetime = None
    expires_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if self.expires_at is None:
            self.expires_at = datetime.now() + timedelta(minutes=10)


# ============================================================================
# MEMORY MANAGER
# ============================================================================

class ConversationMemory:
    """
    Manages conversation context for each user.
    
    Stores context in database with TTL (Time To Live).
    Automatically cleans up expired contexts.
    """
    
    def __init__(self):
        """Initialize the conversation memory system."""
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Create conversation_memory table if needed."""
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                
                -- Context fields
                last_draft_id TEXT,
                last_workspace_item_id INTEGER,
                last_email_thread_id TEXT,
                last_mentioned_person TEXT,
                last_mentioned_email TEXT,
                last_action TEXT,
                last_action_target TEXT,
                last_file_id TEXT,
                last_file_name TEXT,
                last_topic TEXT,
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                
                FOREIGN KEY (last_workspace_item_id) 
                    REFERENCES workspace_items(id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_user 
            ON conversation_memory(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_expires 
            ON conversation_memory(expires_at)
        """)
        
        db.commit()
        db.close()
    
    def remember(self, user_id: int, **kwargs):
        """
        Store context for a user.
        
        Usage:
            memory.remember(user_id, last_draft_id="draft_123")
            memory.remember(user_id, 
                           last_draft_id="draft_123",
                           last_person="Jason",
                           last_action="drafted_email")
        
        Args:
            user_id: Telegram user ID
            **kwargs: Any context fields to remember
        
        This MERGES with existing context (doesn't overwrite everything).
        """
        # Clean up expired contexts first
        self._cleanup_expired()
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if context exists for this user
        cursor.execute("""
            SELECT id FROM conversation_memory 
            WHERE user_id=? AND expires_at > ?
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id, datetime.now()))
        
        row = cursor.fetchone()
        
        if row:
            # UPDATE existing context (merge)
            context_id = row[0]
            
            # Build update query dynamically
            fields = ["updated_at=?", "expires_at=?"]
            values = [datetime.now(), datetime.now() + timedelta(minutes=10)]
            
            for key, value in kwargs.items():
                if key.startswith('last_'):
                    fields.append(f"{key}=?")
                    values.append(value)
            
            values.append(context_id)
            
            query = f"""
                UPDATE conversation_memory 
                SET {', '.join(fields)}
                WHERE id=?
            """
            cursor.execute(query, values)
            
            logger.debug(f"Updated context for user {user_id}: {kwargs}")
        
        else:
            # INSERT new context
            context = ConversationContext(**kwargs)
            
            cursor.execute("""
                INSERT INTO conversation_memory (
                    user_id,
                    last_draft_id, last_workspace_item_id, last_email_thread_id,
                    last_mentioned_person, last_mentioned_email,
                    last_action, last_action_target,
                    last_file_id, last_file_name, last_topic,
                    created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                context.last_draft_id, context.last_workspace_item_id, 
                context.last_email_thread_id,
                context.last_mentioned_person, context.last_mentioned_email,
                context.last_action, context.last_action_target,
                context.last_file_id, context.last_file_name, context.last_topic,
                context.created_at, context.updated_at, context.expires_at
            ))
            
            logger.debug(f"Created context for user {user_id}: {kwargs}")
        
        db.commit()
        db.close()
    
    def recall(self, user_id: int) -> Optional[ConversationContext]:
        """
        Get current context for a user.
        
        Returns None if:
        - No context exists
        - Context has expired (>10 min old)
        
        Usage:
            context = memory.recall(user_id)
            if context:
                draft_id = context.last_draft_id
        """
        self._cleanup_expired()
        
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT * FROM conversation_memory
            WHERE user_id=? AND expires_at > ?
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id, datetime.now()))
        
        row = cursor.fetchone()
        db.close()
        
        if not row:
            return None
        
        # Convert row to ConversationContext
        columns = [
            'id', 'user_id',
            'last_draft_id', 'last_workspace_item_id', 'last_email_thread_id',
            'last_mentioned_person', 'last_mentioned_email',
            'last_action', 'last_action_target',
            'last_file_id', 'last_file_name', 'last_topic',
            'created_at', 'updated_at', 'expires_at'
        ]
        
        data = dict(zip(columns, row))
        
        # Remove non-dataclass fields
        data.pop('id')
        data.pop('user_id')
        
        # Convert timestamps
        for key in ['created_at', 'updated_at', 'expires_at']:
            if data[key]:
                data[key] = datetime.fromisoformat(data[key])
        
        return ConversationContext(**data)
    
    def forget(self, user_id: int):
        """
        Clear context for a user.
        
        Use when:
        - User says "forget that" / "start over"
        - Starting a new conversation topic
        - Context is no longer relevant
        """
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            DELETE FROM conversation_memory WHERE user_id=?
        """, (user_id,))
        
        db.commit()
        db.close()
        
        logger.info(f"Cleared context for user {user_id}")
    
    def _cleanup_expired(self):
        """Remove expired contexts from database."""
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            DELETE FROM conversation_memory 
            WHERE expires_at < ?
        """, (datetime.now(),))
        
        if cursor.rowcount > 0:
            logger.debug(f"Cleaned up {cursor.rowcount} expired contexts")
        
        db.commit()
        db.close()
    
    def resolve_reference(self, user_id: int, message: str) -> Optional[Dict[str, Any]]:
        """
        Resolve pronouns/references in user message.
        
        This is the MAGIC function that makes natural language work.
        
        Detects phrases like:
        - "send it" → resolves to last_draft_id
        - "mark done" → resolves to last_workspace_item_id
        - "make it shorter" → resolves to last_draft_id for editing
        - "add Tom to it" → resolves to last_draft_id
        - "what's the status" → resolves to last_workspace_item_id
        
        Returns:
            Dict with 'type' and 'id' if resolved:
            {'type': 'draft', 'id': 'draft_123'}
            {'type': 'workspace_item', 'id': 42}
            
            None if no reference found or context expired
        
        Usage in telegram_handler.py:
            reference = memory.resolve_reference(user_id, message)
            if reference and reference['type'] == 'draft':
                await send_draft(reference['id'])
        """
        context = self.recall(user_id)
        if not context:
            return None
        
        message_lower = message.lower().strip()
        
        # ========================================
        # DRAFT REFERENCES
        # ========================================
        
        # "send it" / "send that" / "approve it"
        send_patterns = [
            'send it', 'send that', 'send this',
            'approve it', 'approve that',
            'looks good send', 'ok send', 'perfect send'
        ]
        if any(p in message_lower for p in send_patterns):
            if context.last_draft_id:
                return {
                    'type': 'draft_send',
                    'id': context.last_draft_id
                }
        
        # "make it shorter" / "revise it" / "edit it" / "change it"
        edit_patterns = [
            'make it', 'revise it', 'edit it', 'change it',
            'shorten it', 'make that', 'fix it'
        ]
        if any(p in message_lower for p in edit_patterns):
            if context.last_draft_id:
                return {
                    'type': 'draft_edit',
                    'id': context.last_draft_id,
                    'instruction': message  # Pass full message for edit context
                }
        
        # "add X to it" / "cc X on it"
        add_patterns = ['add', 'cc', 'bcc', 'include']
        if any(p in message_lower for p in add_patterns) and ' to it' in message_lower:
            if context.last_draft_id:
                return {
                    'type': 'draft_modify',
                    'id': context.last_draft_id,
                    'instruction': message
                }
        
        # ========================================
        # WORKSPACE ITEM REFERENCES
        # ========================================
        
        # "mark done" / "mark it done" / "done" / "complete"
        done_patterns = [
            'mark done', 'mark it done', 'mark as done',
            'complete it', 'completed', 'finished',
            message_lower == 'done'  # Exact match
        ]
        if any(p if isinstance(p, bool) else p in message_lower for p in done_patterns):
            if context.last_workspace_item_id:
                return {
                    'type': 'workspace_done',
                    'id': context.last_workspace_item_id
                }
        
        # "what's the status" / "check on it" / "any update"
        status_patterns = [
            'status', 'check on it', 'any update', 'what happened',
            'did they reply'
        ]
        if any(p in message_lower for p in status_patterns):
            if context.last_workspace_item_id:
                return {
                    'type': 'workspace_status',
                    'id': context.last_workspace_item_id
                }
        
        # "snooze it" / "remind me later"
        snooze_patterns = ['snooze', 'remind me later', 'not now', 'later']
        if any(p in message_lower for p in snooze_patterns):
            if context.last_workspace_item_id:
                return {
                    'type': 'workspace_snooze',
                    'id': context.last_workspace_item_id
                }
        
        # ========================================
        # PERSON REFERENCES
        # ========================================
        
        # "email them" / "send to them" / "reply to them"
        person_patterns = ['email them', 'send to them', 'reply to them', 'message them']
        if any(p in message_lower for p in person_patterns):
            if context.last_mentioned_person and context.last_mentioned_email:
                return {
                    'type': 'person',
                    'name': context.last_mentioned_person,
                    'email': context.last_mentioned_email
                }
        
        # ========================================
        # FILE REFERENCES
        # ========================================
        
        # "open it" / "download it" / "show me that file"
        file_patterns = ['open it', 'download it', 'show me that', 'get that file']
        if any(p in message_lower for p in file_patterns):
            if context.last_file_id:
                return {
                    'type': 'file',
                    'id': context.last_file_id,
                    'name': context.last_file_name
                }
        
        # No reference resolved
        return None


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Single global instance for entire bot
memory = ConversationMemory()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_person_from_message(message: str) -> Optional[tuple[str, str]]:
    """
    Extract person name/email from message.
    
    Examples:
    - "draft to jason@example.com" → ("jason", "jason@example.com")
    - "email Jason Smith" → ("Jason Smith", None)
    - "reply to laura clarke" → ("laura clarke", None)
    
    Returns: (name, email) or None
    """
    # Simple email extraction
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, message)
    
    if emails:
        email = emails[0]
        name = email.split('@')[0]
        return (name, email)
    
    # Name extraction (after "to" / "from")
    patterns = [
        r'to ([A-Z][a-z]+ [A-Z][a-z]+)',  # "to Jason Smith"
        r'from ([A-Z][a-z]+ [A-Z][a-z]+)',  # "from Laura Clarke"
        r'email ([A-Z][a-z]+ [A-Z][a-z]+)',  # "email Tom Jones"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            name = match.group(1)
            return (name, None)
    
    return None


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    """
    Test conversation memory.
    
    Run this to see how memory works:
        python conversation_memory.py
    """
    print("🧠 Conversation Memory - Test Mode")
    print("=" * 50)
    
    user_id = 12345  # Test user
    
    # Scenario 1: Draft flow
    print("\n📝 Scenario 1: Draft Flow")
    print("-" * 30)
    
    print("User: 'Draft invoice to Jason'")
    memory.remember(user_id, 
                   last_draft_id="draft_abc123",
                   last_mentioned_person="Jason",
                   last_action="drafted_email")
    
    print("User: 'Make it shorter'")
    ref = memory.resolve_reference(user_id, "make it shorter")
    print(f"→ Resolved: {ref}")
    assert ref['type'] == 'draft_edit'
    assert ref['id'] == 'draft_abc123'
    
    print("User: 'Perfect send it'")
    ref = memory.resolve_reference(user_id, "perfect send it")
    print(f"→ Resolved: {ref}")
    assert ref['type'] == 'draft_send'
    
    # Scenario 2: Workspace flow
    print("\n✅ Scenario 2: Workspace Flow")
    print("-" * 30)
    
    print("User: 'Show workspace'")
    memory.remember(user_id, last_workspace_item_id=42)
    
    print("User: 'Mark done'")
    ref = memory.resolve_reference(user_id, "mark done")
    print(f"→ Resolved: {ref}")
    assert ref['type'] == 'workspace_done'
    assert ref['id'] == 42
    
    # Scenario 3: Context expiration
    print("\n⏰ Scenario 3: Context Expiration")
    print("-" * 30)
    
    print("Setting context to expire in 1 second...")
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE conversation_memory 
        SET expires_at=?
        WHERE user_id=?
    """, (datetime.now() + timedelta(seconds=1), user_id))
    db.commit()
    db.close()
    
    import time
    time.sleep(2)
    
    print("User: 'Send it' (after expiration)")
    ref = memory.resolve_reference(user_id, "send it")
    print(f"→ Resolved: {ref}")
    assert ref is None, "Context should have expired"
    
    print("\n✅ All tests passed!")
