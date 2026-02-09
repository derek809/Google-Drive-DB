"""
Database Manager for Mode 4
Manages SQLite database for M1 MacBook (separate from work laptop's mcp_learning.db).

Usage:
    from db_manager import DatabaseManager, get_db

    # Using context manager (recommended)
    with get_db() as db:
        db.execute("INSERT INTO tasks (title) VALUES (?)", ("My task",))
        db.commit()

    # Or for simple operations
    db = DatabaseManager()
    db.add_to_queue(message_data)
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
import uuid


class DatabaseManager:
    """
    Central database manager for mode4.db.

    Handles:
    - Message queue for offline processing
    - Draft context storage for button callbacks
    - Tasks for todo_manager capability
    - Quick links for file_fetcher
    - Idea sessions for idea_bouncer
    """

    def __init__(self, db_path: str = None):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database. Defaults to ~/mode4/data/mode4.db
        """
        if db_path is None:
            # Default path on M1 MacBook
            base_dir = os.path.expanduser("~/mode4/data")
            os.makedirs(base_dir, exist_ok=True)
            db_path = os.path.join(base_dir, "mode4.db")

        self.db_path = db_path
        self._ensure_schema()

    @contextmanager
    def get_connection(self):
        """
        Get database connection with auto-close.

        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
                conn.commit()
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self):
        """Create all tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Message queue for offline processing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_message_id TEXT UNIQUE,
                    user_id INTEGER,
                    chat_id INTEGER,
                    message_text TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    processed_at TIMESTAMP,
                    draft_id TEXT,
                    gmail_draft_id TEXT,
                    error_message TEXT,
                    confidence_score REAL,
                    model_used TEXT,
                    llm_choice TEXT
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_queue_status
                ON message_queue(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_queue_received
                ON message_queue(received_at)
            """)

            # Draft context storage (for button callbacks)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS draft_contexts (
                    draft_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    chat_id INTEGER,
                    message_id INTEGER,
                    context_json TEXT,
                    draft_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_draft_status
                ON draft_contexts(status)
            """)

            # Tasks for todo_manager capability
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    deadline TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    notes TEXT
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON tasks(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_deadline
                ON tasks(deadline)
            """)

            # Migration: Add skill_slug reference to tasks table
            try:
                cursor.execute("ALTER TABLE tasks ADD COLUMN skill_slug TEXT REFERENCES skills(slug)")
                logger.info("Added skill_slug column to tasks table")
            except Exception:
                pass  # Column already exists

            # Quick links for file_fetcher
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quick_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    file_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP
                )
            """)

            # Idea sessions for idea_bouncer
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS idea_sessions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    idea TEXT NOT NULL,
                    questions_json TEXT,
                    answers_json TEXT,
                    gameplan TEXT,
                    use_claude INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            # Skills - finalized ideas with Master Doc + Sheets linkage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    slug TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    context TEXT,
                    status TEXT DEFAULT 'Pending',
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    action_items TEXT,
                    tags TEXT,
                    doc_position TEXT,
                    sheet_row_ids TEXT,
                    idea_session_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (idea_session_id) REFERENCES idea_sessions(id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_skills_user
                ON skills(user_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_skills_status
                ON skills(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_skills_type
                ON skills(type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_skills_created
                ON skills(created_at)
            """)

            # Workspace items for ProactiveEngine
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspace_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL UNIQUE,
                    subject TEXT NOT NULL,
                    from_name TEXT NOT NULL,
                    from_email TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    last_gmail_activity TEXT,
                    urgency TEXT DEFAULT 'normal',
                    status TEXT DEFAULT 'active',
                    days_old INTEGER DEFAULT 0,
                    related_draft_id TEXT,
                    last_bot_suggestion TEXT,
                    suggestion_count INTEGER DEFAULT 0,
                    chat_id INTEGER,
                    added_to_workspace TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workspace_status
                ON workspace_items(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workspace_urgency
                ON workspace_items(urgency)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workspace_days_old
                ON workspace_items(days_old)
            """)

            # Suggestion log for ProactiveEngine
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS suggestion_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_item_id INTEGER NOT NULL,
                    suggestion_type TEXT NOT NULL,
                    suggested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    user_action TEXT,
                    FOREIGN KEY (workspace_item_id) REFERENCES workspace_items(id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_suggestion_workspace
                ON suggestion_log(workspace_item_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_suggestion_type
                ON suggestion_log(suggestion_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_suggestion_date
                ON suggestion_log(suggested_at)
            """)

            # Migration tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS db_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name TEXT NOT NULL,
                    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Workflows for multi-step task chaining
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    workflow_type TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'idle',
                    context TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    step_history TEXT DEFAULT '[]'
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflows_user
                ON workflows(user_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflows_state
                ON workflows(state)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflows_updated
                ON workflows(updated_at)
            """)

            # Clarification state for multi-step flows (survives restart)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clarification_state (
                    user_id INTEGER PRIMARY KEY,
                    intent TEXT NOT NULL,
                    missing_fields TEXT NOT NULL,
                    collected_data TEXT DEFAULT '{}',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)

            conn.commit()

    # ==================
    # CLARIFICATION STATE
    # ==================

    def set_clarification(
        self,
        user_id: int,
        intent: str,
        fields: list,
        timeout_minutes: int = 5
    ):
        """
        Start a clarification flow for a user.

        Args:
            user_id: Telegram user ID
            intent: The intent being clarified (e.g., 'email_draft')
            fields: List of field names to collect (e.g., ['subject', 'message', 'recipient'])
            timeout_minutes: How long before the clarification expires
        """
        from datetime import datetime, timedelta
        expires_at = (datetime.now() + timedelta(minutes=timeout_minutes)).isoformat()

        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO clarification_state
                (user_id, intent, missing_fields, collected_data, started_at, expires_at)
                VALUES (?, ?, ?, '{}', ?, ?)
            """, (user_id, intent, json.dumps(fields), datetime.now().isoformat(), expires_at))
            conn.commit()

    def get_clarification(self, user_id: int) -> dict:
        """
        Get active clarification state for a user.

        Returns:
            Dict with 'intent', 'missing_fields', 'collected_data', or None if expired/not found
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT intent, missing_fields, collected_data, expires_at
                FROM clarification_state
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()

        if not row:
            return None

        # Check expiration
        expires_at = row['expires_at']
        if datetime.fromisoformat(expires_at) < datetime.now():
            self.clear_clarification(user_id)
            return None

        return {
            'intent': row['intent'],
            'missing_fields': json.loads(row['missing_fields']),
            'collected_data': json.loads(row['collected_data'])
        }

    def update_clarification(
        self,
        user_id: int,
        remaining_fields: list,
        collected_data: dict
    ):
        """
        Update clarification state with collected answer.

        Args:
            user_id: Telegram user ID
            remaining_fields: Updated list of fields still needed
            collected_data: Updated dict of collected answers
        """
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE clarification_state
                SET missing_fields = ?, collected_data = ?
                WHERE user_id = ?
            """, (json.dumps(remaining_fields), json.dumps(collected_data), user_id))
            conn.commit()

    def clear_clarification(self, user_id: int):
        """Clear clarification state for a user."""
        with self.get_connection() as conn:
            conn.execute(
                "DELETE FROM clarification_state WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

    # ==================
    # MESSAGE QUEUE
    # ==================

    def add_to_queue(
        self,
        telegram_message_id: str,
        user_id: int,
        chat_id: int,
        message_text: str,
        llm_choice: str = 'user_pending'
    ) -> int:
        """
        Add message to processing queue.

        Args:
            telegram_message_id: Unique Telegram message ID
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message_text: Message text
            llm_choice: 'ollama', 'claude', or 'user_pending'

        Returns:
            Queue entry ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO message_queue
                (telegram_message_id, user_id, chat_id, message_text, llm_choice)
                VALUES (?, ?, ?, ?, ?)
            """, (telegram_message_id, user_id, chat_id, message_text, llm_choice))
            conn.commit()
            return cursor.lastrowid

    def get_pending_messages(self, limit: int = 20) -> List[Dict]:
        """Get pending messages from queue."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM message_queue
                WHERE status = 'pending'
                ORDER BY received_at ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_queue_messages(self, limit: int = 20) -> List[Dict]:
        """Alias for get_pending_messages() for backward compatibility."""
        return self.get_pending_messages(limit)

    def get_queue_messages_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """Get queue messages by status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM message_queue
                WHERE status = ?
                ORDER BY received_at ASC
                LIMIT ?
            """, (status, limit))
            return [dict(row) for row in cursor.fetchall()]

    def initialize(self):
        """Initialize database (alias for _ensure_schema for backward compatibility)."""
        self._ensure_schema()

    def update_queue_status(
        self,
        queue_id: int,
        status: str,
        draft_id: str = None,
        gmail_draft_id: str = None,
        confidence_score: float = None,
        model_used: str = None,
        error_message: str = None
    ):
        """Update queue entry status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            updates = ["status = ?", "processed_at = ?"]
            values = [status, datetime.now()]

            if draft_id:
                updates.append("draft_id = ?")
                values.append(draft_id)
            if gmail_draft_id:
                updates.append("gmail_draft_id = ?")
                values.append(gmail_draft_id)
            if confidence_score is not None:
                updates.append("confidence_score = ?")
                values.append(confidence_score)
            if model_used:
                updates.append("model_used = ?")
                values.append(model_used)
            if error_message:
                updates.append("error_message = ?")
                values.append(error_message)

            values.append(queue_id)

            cursor.execute(f"""
                UPDATE message_queue
                SET {', '.join(updates)}
                WHERE id = ?
            """, values)
            conn.commit()

    # ==================
    # DRAFT CONTEXTS
    # ==================

    def store_draft_context(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        context: Dict,
        expires_minutes: int = 30
    ) -> str:
        """
        Store draft context for button callbacks.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message_id: Original message ID
            context: Context dict (will be JSON serialized)
            expires_minutes: How long to keep context

        Returns:
            draft_id (UUID)
        """
        draft_id = str(uuid.uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=expires_minutes)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO draft_contexts
                (draft_id, user_id, chat_id, message_id, context_json, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (draft_id, user_id, chat_id, message_id, json.dumps(context), expires_at))
            conn.commit()

        return draft_id

    def get_draft_context(self, draft_id: str) -> Optional[Dict]:
        """Get draft context by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM draft_contexts
                WHERE draft_id = ? AND status = 'active'
            """, (draft_id,))
            row = cursor.fetchone()

            if row:
                result = dict(row)
                result['context'] = json.loads(result.get('context_json', '{}'))
                if result.get('draft_json'):
                    result['draft'] = json.loads(result['draft_json'])
                return result
            return None

    def update_draft_context(
        self,
        draft_id: str,
        draft: Dict = None,
        status: str = None
    ):
        """Update draft context with generated draft."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            updates = []
            values = []

            if draft:
                updates.append("draft_json = ?")
                values.append(json.dumps(draft))
            if status:
                updates.append("status = ?")
                values.append(status)

            if updates:
                values.append(draft_id)
                cursor.execute(f"""
                    UPDATE draft_contexts
                    SET {', '.join(updates)}
                    WHERE draft_id = ?
                """, values)
                conn.commit()

    def cleanup_expired_contexts(self):
        """Delete expired draft contexts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM draft_contexts
                WHERE expires_at < ? OR status != 'active'
            """, (datetime.now(),))
            conn.commit()
            return cursor.rowcount

    # ==================
    # TASKS
    # ==================

    def add_task(
        self,
        title: str,
        priority: str = 'medium',
        deadline: datetime = None,
        notes: str = None,
        skill_slug: str = None
    ) -> int:
        """Add a new task."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (title, priority, deadline, notes, skill_slug)
                VALUES (?, ?, ?, ?, ?)
            """, (title, priority, deadline, notes, skill_slug))
            conn.commit()
            return cursor.lastrowid

    def get_pending_tasks(self, limit: int = 20) -> List[Dict]:
        """Get pending tasks ordered by priority and deadline."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM tasks
                WHERE status = 'pending'
                ORDER BY
                    CASE priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        ELSE 3
                    END,
                    deadline ASC NULLS LAST
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def complete_task(self, task_id: int):
        """Mark task as completed."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks
                SET status = 'completed', completed_at = ?
                WHERE id = ?
            """, (datetime.now(), task_id))
            conn.commit()

    def delete_task(self, task_id: int):
        """Delete a task."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()

    # ==================
    # QUICK LINKS
    # ==================

    def add_quick_link(self, name: str, url: str, file_type: str = None) -> int:
        """Add or update a quick link."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO quick_links (name, url, file_type)
                VALUES (?, ?, ?)
            """, (name, url, file_type))
            conn.commit()
            return cursor.lastrowid

    def get_quick_link(self, name: str) -> Optional[Dict]:
        """Get quick link by name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM quick_links WHERE name = ?
            """, (name,))
            row = cursor.fetchone()

            if row:
                # Update last used
                cursor.execute("""
                    UPDATE quick_links SET last_used = ? WHERE name = ?
                """, (datetime.now(), name))
                conn.commit()
                return dict(row)
            return None

    def list_quick_links(self) -> List[Dict]:
        """List all quick links."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM quick_links ORDER BY last_used DESC NULLS LAST
            """)
            return [dict(row) for row in cursor.fetchall()]

    # ==================
    # IDEA SESSIONS
    # ==================

    def create_idea_session(
        self,
        user_id: int,
        idea: str,
        use_claude: bool = False
    ) -> str:
        """Create a new idea session."""
        session_id = f"idea_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO idea_sessions
                (id, user_id, idea, use_claude, questions_json, answers_json)
                VALUES (?, ?, ?, ?, '[]', '[]')
            """, (session_id, user_id, idea, 1 if use_claude else 0))
            conn.commit()

        return session_id

    def get_idea_session(self, session_id: str) -> Optional[Dict]:
        """Get idea session by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM idea_sessions WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()

            if row:
                result = dict(row)
                result['questions'] = json.loads(result.get('questions_json', '[]'))
                result['answers'] = json.loads(result.get('answers_json', '[]'))
                return result
            return None

    def get_active_idea_session(self, user_id: int) -> Optional[Dict]:
        """Get user's active idea session."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM idea_sessions
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()

            if row:
                result = dict(row)
                result['questions'] = json.loads(result.get('questions_json', '[]'))
                result['answers'] = json.loads(result.get('answers_json', '[]'))
                return result
            return None

    def update_idea_session(
        self,
        session_id: str,
        questions: List[str] = None,
        answers: List[str] = None,
        gameplan: str = None,
        status: str = None
    ):
        """Update idea session."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            updates = []
            values = []

            if questions is not None:
                updates.append("questions_json = ?")
                values.append(json.dumps(questions))
            if answers is not None:
                updates.append("answers_json = ?")
                values.append(json.dumps(answers))
            if gameplan:
                updates.append("gameplan = ?")
                values.append(gameplan)
            if status:
                updates.append("status = ?")
                values.append(status)
                if status == 'completed':
                    updates.append("completed_at = ?")
                    values.append(datetime.now())

            if updates:
                values.append(session_id)
                cursor.execute(f"""
                    UPDATE idea_sessions
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, values)
                conn.commit()

    # ==================
    # SKILLS
    # ==================

    def create_skill(
        self,
        slug: str,
        user_id: int,
        skill_type: str,
        title: str,
        body: str,
        context: str = None,
        action_items: List[str] = None,
        tags: List[str] = None,
        doc_position: str = None,
        sheet_row_ids: List[str] = None,
        idea_session_id: str = None
    ) -> str:
        """
        Create a new skill record.

        Args:
            slug: Unique identifier (e.g., "idea_rr_onboarding_20250205_1430")
            user_id: Telegram user ID
            skill_type: Type (Task, Email Draft, Note, Brainstorm)
            title: Short title
            body: Full body content
            context: Optional context tag
            action_items: List of action items
            tags: List of tags
            doc_position: Reference position in Master Doc
            sheet_row_ids: List of Google Sheets row IDs
            idea_session_id: Link to original idea session

        Returns:
            The slug of the created skill
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO skills
                (slug, user_id, type, title, body, context, action_items, tags,
                 doc_position, sheet_row_ids, idea_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                slug, user_id, skill_type, title, body, context,
                json.dumps(action_items) if action_items else None,
                json.dumps(tags) if tags else None,
                doc_position,
                json.dumps(sheet_row_ids) if sheet_row_ids else None,
                idea_session_id
            ))
            conn.commit()
            return slug

    def get_skill(self, slug: str) -> Optional[Dict]:
        """Get a skill by slug."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skills WHERE slug = ?", (slug,))
            row = cursor.fetchone()

            if row:
                result = dict(row)
                # Parse JSON fields
                if result.get('action_items'):
                    result['action_items'] = json.loads(result['action_items'])
                if result.get('tags'):
                    result['tags'] = json.loads(result['tags'])
                if result.get('sheet_row_ids'):
                    result['sheet_row_ids'] = json.loads(result['sheet_row_ids'])
                return result
            return None

    def list_skills(
        self,
        user_id: int = None,
        status: str = None,
        skill_type: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        List skills with optional filters.

        Args:
            user_id: Filter by user (optional)
            status: Filter by status (optional)
            skill_type: Filter by type (optional)
            limit: Max results

        Returns:
            List of skill dicts
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM skills WHERE 1=1"
            params = []

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            if skill_type:
                query += " AND type = ?"
                params.append(skill_type)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('action_items'):
                    result['action_items'] = json.loads(result['action_items'])
                if result.get('tags'):
                    result['tags'] = json.loads(result['tags'])
                if result.get('sheet_row_ids'):
                    result['sheet_row_ids'] = json.loads(result['sheet_row_ids'])
                results.append(result)
            return results

    def update_skill(
        self,
        slug: str,
        status: str = None,
        sheet_row_ids: List[str] = None,
        doc_position: str = None
    ):
        """Update a skill's status or references."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            updates = ["updated_at = ?"]
            values = [datetime.now()]

            if status:
                updates.append("status = ?")
                values.append(status)
            if sheet_row_ids is not None:
                updates.append("sheet_row_ids = ?")
                values.append(json.dumps(sheet_row_ids))
            if doc_position:
                updates.append("doc_position = ?")
                values.append(doc_position)

            values.append(slug)
            cursor.execute(f"""
                UPDATE skills
                SET {', '.join(updates)}
                WHERE slug = ?
            """, values)
            conn.commit()

    def search_skills(self, query: str, user_id: int = None, limit: int = 20) -> List[Dict]:
        """
        Search skills by keyword in title, body, or tags.

        Args:
            query: Search term
            user_id: Optional user filter
            limit: Max results

        Returns:
            List of matching skills
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            search_term = f"%{query}%"
            sql = """
                SELECT * FROM skills
                WHERE (title LIKE ? OR body LIKE ? OR tags LIKE ? OR slug LIKE ?)
            """
            params = [search_term, search_term, search_term, search_term]

            if user_id:
                sql += " AND user_id = ?"
                params.append(user_id)

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('action_items'):
                    result['action_items'] = json.loads(result['action_items'])
                if result.get('tags'):
                    result['tags'] = json.loads(result['tags'])
                results.append(result)
            return results

    def delete_skill(self, slug: str):
        """Delete a skill by slug."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM skills WHERE slug = ?", (slug,))
            conn.commit()


# ==================
# CONVENIENCE FUNCTION
# ==================

_db_instance = None

def get_db() -> DatabaseManager:
    """
    Get singleton database manager instance.

    Usage:
        db = get_db()
        db.add_task("My task")
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance


# ==================
# TESTING
# ==================

def test_database():
    """Test database operations."""
    print("Testing Database Manager...")
    print("=" * 60)

    # Use temp database for testing
    import tempfile
    db_path = os.path.join(tempfile.gettempdir(), "mode4_test.db")

    db = DatabaseManager(db_path)

    # Test tasks
    print("\nTesting tasks...")
    task_id = db.add_task("Test task", priority="high")
    print(f"  Added task ID: {task_id}")

    tasks = db.get_pending_tasks()
    print(f"  Pending tasks: {len(tasks)}")

    db.complete_task(task_id)
    tasks = db.get_pending_tasks()
    print(f"  After completion: {len(tasks)}")

    # Test draft contexts
    print("\nTesting draft contexts...")
    draft_id = db.store_draft_context(
        user_id=123,
        chat_id=456,
        message_id=789,
        context={'email_reference': 'Test', 'instruction': 'Draft reply'}
    )
    print(f"  Stored draft ID: {draft_id}")

    context = db.get_draft_context(draft_id)
    print(f"  Retrieved context: {context is not None}")

    # Test queue
    print("\nTesting message queue...")
    queue_id = db.add_to_queue(
        telegram_message_id="test_123",
        user_id=123,
        chat_id=456,
        message_text="Draft invoice for Jason"
    )
    print(f"  Added to queue ID: {queue_id}")

    pending = db.get_pending_messages()
    print(f"  Pending messages: {len(pending)}")

    db.update_queue_status(queue_id, 'completed', model_used='ollama')
    pending = db.get_pending_messages()
    print(f"  After processing: {len(pending)}")

    # Test quick links
    print("\nTesting quick links...")
    db.add_quick_link("w9", "https://drive.google.com/file/xxx", "pdf")
    link = db.get_quick_link("w9")
    print(f"  Retrieved link: {link['url'][:30]}...")

    # Test idea sessions
    print("\nTesting idea sessions...")
    session_id = db.create_idea_session(user_id=123, idea="Build a mobile app")
    print(f"  Created session: {session_id}")

    db.update_idea_session(
        session_id,
        questions=["What problem does it solve?"],
        answers=["Helps track expenses"]
    )

    session = db.get_idea_session(session_id)
    print(f"  Questions: {len(session['questions'])}")
    print(f"  Answers: {len(session['answers'])}")

    # Cleanup
    os.remove(db_path)

    print("\n" + "=" * 60)
    print("Database manager test complete!")


if __name__ == "__main__":
    test_database()
