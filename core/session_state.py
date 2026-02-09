"""
Session State Manager for Mode 4 Action Registry.

Manages conversation state for multi-turn interactions:
- AWAITING_SELECTION: Bot asked "Which task?" and expects a selection
- AWAITING_CONFIRMATION: Bot asked "Are you sure?" and expects yes/no
- AWAITING_INPUT: Bot needs additional info before proceeding

Also provides short-term memory for "Current Subject" tracking,
enabling pronoun resolution ("it", "that", "this").
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SessionState:
    """Manages conversation state for multi-turn interactions and context memory."""

    def __init__(self, db_manager):
        self.db = db_manager
        self._ensure_table()

    def _ensure_table(self):
        """Create session_state table if it doesn't exist."""
        with self.db.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_state (
                    user_id INTEGER PRIMARY KEY,
                    state TEXT NOT NULL,
                    awaiting_type TEXT,
                    pending_action TEXT,
                    context_data TEXT,
                    expires_at TEXT
                )
                """
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Awaiting state management
    # -------------------------------------------------------------------------

    def set_awaiting(
        self,
        user_id: int,
        awaiting_type: str,
        pending_action: str,
        context_data: Dict[str, Any],
        timeout_minutes: int = 30,
    ):
        """Mark user as awaiting input for a specific action."""
        expires_at = (
            datetime.now() + timedelta(minutes=timeout_minutes)
        ).isoformat()

        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO session_state
                (user_id, state, awaiting_type, pending_action, context_data, expires_at)
                VALUES (?, 'awaiting', ?, ?, ?, ?)
                """,
                (
                    user_id,
                    awaiting_type,
                    pending_action,
                    json.dumps(context_data, default=str),
                    expires_at,
                ),
            )
            conn.commit()

    def get_awaiting(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get current awaiting state for user."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT awaiting_type, pending_action, context_data, expires_at
                FROM session_state
                WHERE user_id = ? AND state = 'awaiting'
                """,
                (user_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        awaiting_type = row["awaiting_type"]
        pending_action = row["pending_action"]
        context_json = row["context_data"]
        expires_at = row["expires_at"]

        # Check expiration
        if datetime.fromisoformat(expires_at) < datetime.now():
            self.clear_awaiting(user_id)
            return None

        return {
            "type": awaiting_type,
            "action": pending_action,
            "context": json.loads(context_json) if context_json else {},
        }

    def clear_awaiting(self, user_id: int):
        """Clear awaiting state."""
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM session_state WHERE user_id = ?", (user_id,)
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Reference storage (numbered lists, last-viewed items)
    # -------------------------------------------------------------------------

    def store_reference(self, user_id: int, ref_type: str, data: Any):
        """
        Store numbered references (tasks, emails, skills) for quick access.
        Enables commands like "reply to #2" or "draft from skill #3".
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT context_data FROM session_state WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            context = (
                json.loads(row["context_data"])
                if row and row["context_data"]
                else {}
            )

            context[f"last_{ref_type}"] = data
            context[f"{ref_type}_timestamp"] = datetime.now().isoformat()

            conn.execute(
                """
                INSERT OR REPLACE INTO session_state
                (user_id, state, context_data, expires_at)
                VALUES (?, 'active', ?, ?)
                """,
                (
                    user_id,
                    json.dumps(context, default=str),
                    (datetime.now() + timedelta(minutes=30)).isoformat(),
                ),
            )
            conn.commit()

    def get_reference(self, user_id: int, ref_type: str) -> Optional[Any]:
        """Retrieve stored references."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT context_data FROM session_state WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

        if not row or not row["context_data"]:
            return None

        context = json.loads(row["context_data"])

        # Check timestamp (30 min expiry)
        timestamp_key = f"{ref_type}_timestamp"
        if timestamp_key in context:
            stored_time = datetime.fromisoformat(context[timestamp_key])
            if datetime.now() - stored_time > timedelta(minutes=30):
                return None

        return context.get(f"last_{ref_type}")

    # -------------------------------------------------------------------------
    # Current Subject tracking (for "it" resolution)
    # -------------------------------------------------------------------------

    def store_current_subject(
        self,
        user_id: int,
        subject_type: str,
        subject_id: Any,
        subject_data: Dict[str, Any],
    ):
        """
        Store the "Current Active Entity" for "it" resolution.
        Examples: last email found, last task created, last draft generated.
        """
        self.store_reference(
            user_id,
            f"current_{subject_type}",
            {"id": subject_id, "type": subject_type, "data": subject_data},
        )

    def get_current_subject(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the most recent "Current Active Entity" for pronoun resolution.
        Returns dict: {"id": ..., "type": "email"|"task"|"draft"|..., "data": {...}}
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT context_data FROM session_state WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

        if not row or not row["context_data"]:
            return None

        context = json.loads(row["context_data"])

        # Find the most recent "current_*" key
        current_keys = [k for k in context if k.startswith("last_current_")]
        if not current_keys:
            return None

        most_recent = None
        most_recent_time = None

        for key in current_keys:
            # Corresponding timestamp key
            base_ref_type = key.replace("last_", "", 1)
            timestamp_key = f"{base_ref_type}_timestamp"
            if timestamp_key in context:
                try:
                    stored_time = datetime.fromisoformat(
                        context[timestamp_key]
                    )
                except (ValueError, TypeError):
                    continue

                if datetime.now() - stored_time > timedelta(minutes=30):
                    continue

                if most_recent_time is None or stored_time > most_recent_time:
                    most_recent_time = stored_time
                    most_recent = context[key]

        return most_recent
