"""
Topic Stack Memory for Mode 4.

Manages conversational topic stacks per user in SQLite:
- Tracks active topic (what the user is currently talking about)
- Logs topic transitions (when conversation shifts)
- Trims old context to keep token budgets manageable
- Provides data for the Learning Loop to analyze topic effectiveness

Uses DatabaseManager adapter methods (execute/fetchone/fetchall)
so callers don't need to manage connections directly.

Usage:
    from core.Infrastructure.db_manager import get_db
    from core.Inference.topic_stack_memory import TopicStackMemory

    db = get_db()
    memory = TopicStackMemory(db)

    # Push new topic
    memory.push_topic(user_id=123, topic="email_draft", context={"recipient": "John"})

    # Get current topic
    current = memory.get_active_topic(user_id=123)

    # Record transition
    memory.record_transition(user_id=123, from_topic="email_draft",
                             to_topic="todo_add", trigger="add task")
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TopicStackMemory:
    """
    Per-user topic stack with automatic context management.

    Stores topic state in the topic_stacks, context_trims, and
    topic_transitions tables (created by db_manager._ensure_schema).
    """

    MAX_STACK_DEPTH = 5       # Max active topics per user
    TRIM_THRESHOLD = 20       # Trim context after this many messages per topic

    def __init__(self, db_manager):
        """
        Args:
            db_manager: DatabaseManager instance (must have execute/fetchone/fetchall).
        """
        self.db = db_manager

    # ── Push / Pop ───────────────────────────────────────────────────────

    def push_topic(
        self,
        user_id: int,
        topic: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Push a new topic onto the user's stack.

        If the stack exceeds MAX_STACK_DEPTH, the oldest active topic
        is archived automatically.

        Returns:
            The id of the newly created topic_stacks row.
        """
        context_json = json.dumps(context or {})

        # Archive oldest if stack is full
        active = self.db.fetchall(
            "SELECT id FROM topic_stacks WHERE user_id = ? AND status = 'active' "
            "ORDER BY last_active DESC",
            (user_id,),
        )
        if len(active) >= self.MAX_STACK_DEPTH:
            oldest_id = active[-1]["id"]
            self.db.execute(
                "UPDATE topic_stacks SET status = 'archived' WHERE id = ?",
                (oldest_id,),
            )
            logger.debug("Archived topic stack %d for user %d (stack full)", oldest_id, user_id)

        # Insert new topic
        self.db.execute(
            "INSERT INTO topic_stacks (user_id, topic, context_json) VALUES (?, ?, ?)",
            (user_id, topic, context_json),
        )

        # Retrieve the inserted row id
        row = self.db.fetchone(
            "SELECT id FROM topic_stacks WHERE user_id = ? AND topic = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, topic),
        )
        topic_id = row["id"] if row else 0
        logger.info("Pushed topic '%s' (id=%d) for user %d", topic, topic_id, user_id)
        return topic_id

    # ── Queries ──────────────────────────────────────────────────────────

    def get_active_topic(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get the most recent active topic for a user, or None."""
        row = self.db.fetchone(
            "SELECT * FROM topic_stacks WHERE user_id = ? AND status = 'active' "
            "ORDER BY last_active DESC LIMIT 1",
            (user_id,),
        )
        if row:
            row["context"] = json.loads(row.get("context_json", "{}"))
        return row

    def get_topic_stack(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all active topics for a user, most recent first."""
        rows = self.db.fetchall(
            "SELECT * FROM topic_stacks WHERE user_id = ? AND status = 'active' "
            "ORDER BY last_active DESC",
            (user_id,),
        )
        for row in rows:
            row["context"] = json.loads(row.get("context_json", "{}"))
        return rows

    # ── Updates ──────────────────────────────────────────────────────────

    def update_topic_context(self, topic_id: int, context: Dict[str, Any]):
        """Update the context dict and bump last_active + message_count."""
        self.db.execute(
            "UPDATE topic_stacks SET context_json = ?, last_active = ?, "
            "message_count = message_count + 1 WHERE id = ?",
            (json.dumps(context), datetime.now().isoformat(), topic_id),
        )

    def deactivate_topic(self, topic_id: int):
        """Archive a single topic."""
        self.db.execute(
            "UPDATE topic_stacks SET status = 'archived' WHERE id = ?",
            (topic_id,),
        )

    # ── Transitions ──────────────────────────────────────────────────────

    def record_transition(
        self,
        user_id: int,
        from_topic: Optional[str],
        to_topic: str,
        trigger: str = "",
    ):
        """Record a topic transition for Learning Loop analysis."""
        self.db.execute(
            "INSERT INTO topic_transitions "
            "(user_id, from_topic, to_topic, trigger_message) "
            "VALUES (?, ?, ?, ?)",
            (user_id, from_topic, to_topic, trigger),
        )
        logger.debug(
            "Topic transition for user %d: %s -> %s (trigger: %s)",
            user_id, from_topic, to_topic, trigger,
        )

    # ── Context Trimming ─────────────────────────────────────────────────

    def trim_context(
        self,
        user_id: int,
        topic_id: int,
        reason: str = "auto_trim",
    ):
        """
        Trim old messages from a topic's context to stay within token budget.

        Keeps the 5 most recent messages and archives the rest to the
        context_trims table so the Learning Loop can still see them.
        """
        row = self.db.fetchone(
            "SELECT context_json, message_count FROM topic_stacks WHERE id = ?",
            (topic_id,),
        )
        if not row or row["message_count"] < self.TRIM_THRESHOLD:
            return

        context = json.loads(row.get("context_json", "{}"))
        messages = context.get("messages", [])

        if len(messages) <= 5:
            return

        # Split: archive old, keep recent
        trimmed = messages[:-5]
        context["messages"] = messages[-5:]

        # Store trimmed content for Learning Loop
        self.db.execute(
            "INSERT INTO context_trims "
            "(user_id, topic_stack_id, trimmed_messages, reason) "
            "VALUES (?, ?, ?, ?)",
            (user_id, topic_id, json.dumps(trimmed), reason),
        )

        # Update topic with trimmed context
        self.db.execute(
            "UPDATE topic_stacks SET context_json = ?, message_count = ? WHERE id = ?",
            (json.dumps(context), len(context["messages"]), topic_id),
        )

        logger.info(
            "Trimmed %d messages from topic %d for user %d",
            len(trimmed), topic_id, user_id,
        )

    # ── Learning Loop Data ───────────────────────────────────────────────

    def get_learning_data(self, user_id: int) -> Dict[str, Any]:
        """
        Provide data for learning_loop.py to analyze topic effectiveness.

        Returns:
            Dict with 'transitions', 'context_trims', 'active_stack_depth'.
        """
        transitions = self.db.fetchall(
            "SELECT * FROM topic_transitions WHERE user_id = ? "
            "ORDER BY transitioned_at DESC LIMIT 50",
            (user_id,),
        )

        trims = self.db.fetchall(
            "SELECT * FROM context_trims WHERE user_id = ? "
            "ORDER BY trimmed_at DESC LIMIT 20",
            (user_id,),
        )

        active = self.db.fetchall(
            "SELECT id FROM topic_stacks WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )

        return {
            "transitions": transitions,
            "context_trims": trims,
            "active_stack_depth": len(active),
        }
