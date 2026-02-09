"""
Conversation Flow State Machine for Mode 4.

Replaces ad-hoc boolean ``awaiting_*`` flags with a formal state machine.
Every state transition is persisted to SQLite for crash recovery, and the
machine supports per-user / per-chat-thread parallelism.

States:
    IDLE                   – Ready for a new intent.
    AWAITING_CLARIFICATION – Multiple options presented; waiting for selection.
    AWAITING_CONFIRMATION  – High-risk action pending; waiting for yes/no.
    AWAITING_INPUT         – Missing required parameter; waiting for free text.
    EXECUTING              – Action in progress (show typing indicator).
    ERROR_RECOVERY         – Something failed; offering retry / cancel / help.
    MULTI_STEP             – Workflow in progress (chained actions).
"""

import json
import logging
import time
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    IDLE = "idle"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_INPUT = "awaiting_input"
    EXECUTING = "executing"
    ERROR_RECOVERY = "error_recovery"
    MULTI_STEP = "multi_step"


# ── Allowed transitions ─────────────────────────────────────────────────────

_TRANSITIONS = {
    ConversationState.IDLE: {
        "clarify",       # → AWAITING_CLARIFICATION
        "confirm",       # → AWAITING_CONFIRMATION
        "request_input", # → AWAITING_INPUT
        "execute",       # → EXECUTING
        "start_workflow", # → MULTI_STEP
    },
    ConversationState.AWAITING_CLARIFICATION: {
        "select",   # → EXECUTING
        "cancel",   # → IDLE
        "timeout",  # → IDLE
        "error",    # → ERROR_RECOVERY
    },
    ConversationState.AWAITING_CONFIRMATION: {
        "confirm",  # → EXECUTING
        "cancel",   # → IDLE
        "timeout",  # → IDLE
        "error",    # → ERROR_RECOVERY
    },
    ConversationState.AWAITING_INPUT: {
        "receive_input",  # → EXECUTING
        "cancel",         # → IDLE
        "timeout",        # → IDLE
        "error",          # → ERROR_RECOVERY
    },
    ConversationState.EXECUTING: {
        "complete",  # → IDLE
        "error",     # → ERROR_RECOVERY
        "next_step", # → MULTI_STEP
    },
    ConversationState.ERROR_RECOVERY: {
        "retry",    # → EXECUTING
        "cancel",   # → IDLE
        "timeout",  # → IDLE
    },
    ConversationState.MULTI_STEP: {
        "next_step",    # → MULTI_STEP (loop)
        "execute",      # → EXECUTING
        "complete",     # → IDLE
        "cancel",       # → IDLE
        "error",        # → ERROR_RECOVERY
        "clarify",      # → AWAITING_CLARIFICATION
        "confirm",      # → AWAITING_CONFIRMATION
        "request_input", # → AWAITING_INPUT
    },
}

_TRANSITION_TARGET = {
    "clarify":       ConversationState.AWAITING_CLARIFICATION,
    "confirm":       ConversationState.AWAITING_CONFIRMATION,
    "request_input": ConversationState.AWAITING_INPUT,
    "select":        ConversationState.EXECUTING,
    "receive_input": ConversationState.EXECUTING,
    "execute":       ConversationState.EXECUTING,
    "complete":      ConversationState.IDLE,
    "cancel":        ConversationState.IDLE,
    "timeout":       ConversationState.IDLE,
    "error":         ConversationState.ERROR_RECOVERY,
    "retry":         ConversationState.EXECUTING,
    "start_workflow": ConversationState.MULTI_STEP,
    "next_step":     ConversationState.MULTI_STEP,
}

# Default timeout for awaiting states (seconds)
DEFAULT_TIMEOUT = 5 * 60  # 5 minutes


class ConversationStateMachine:
    """
    Per-user state machine backed by SQLite.

    Usage::

        sm = ConversationStateMachine(db_manager)

        sm.transition(user_id, "clarify", data={
            "options": [...],
            "pending_action": "todo_complete",
        })

        current = sm.get_state(user_id)
        # current == {"state": "awaiting_clarification", "data": {...}}

        sm.transition(user_id, "select", data={"selected_index": 0})
    """

    TABLE = "conversation_state_machine"

    def __init__(self, db_manager):
        self.db = db_manager
        self._ensure_table()

    def _ensure_table(self):
        with self.db.get_connection() as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE} (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER DEFAULT 0,
                    state TEXT NOT NULL DEFAULT 'idle',
                    event_data TEXT DEFAULT '{{}}',
                    pending_action TEXT,
                    workflow_steps TEXT,
                    workflow_index INTEGER DEFAULT 0,
                    updated_at REAL NOT NULL,
                    expires_at REAL,
                    PRIMARY KEY (user_id, chat_id)
                )
            """)
            conn.commit()

    # ── state access ─────────────────────────────────────────────────────

    def get_state(
        self, user_id: int, chat_id: int = 0
    ) -> Dict[str, Any]:
        """Return current state + metadata for a user/chat pair."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.TABLE} WHERE user_id=? AND chat_id=?",
                (user_id, chat_id),
            ).fetchone()

        if not row:
            return {"state": ConversationState.IDLE.value, "data": {}}

        state_str = row["state"]
        data = json.loads(row["event_data"]) if row["event_data"] else {}
        expires_at = row["expires_at"]

        # Auto-expire
        if expires_at and time.time() > expires_at:
            self._set_state(user_id, chat_id, ConversationState.IDLE, {})
            return {"state": ConversationState.IDLE.value, "data": {}}

        return {
            "state": state_str,
            "data": data,
            "pending_action": row["pending_action"],
            "workflow_steps": json.loads(row["workflow_steps"]) if row["workflow_steps"] else None,
            "workflow_index": row["workflow_index"],
        }

    def get_state_enum(self, user_id: int, chat_id: int = 0) -> ConversationState:
        info = self.get_state(user_id, chat_id)
        try:
            return ConversationState(info["state"])
        except ValueError:
            return ConversationState.IDLE

    # ── transitions ──────────────────────────────────────────────────────

    def transition(
        self,
        user_id: int,
        event: str,
        chat_id: int = 0,
        data: Optional[Dict[str, Any]] = None,
        pending_action: Optional[str] = None,
        workflow_steps: Optional[list] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT,
    ) -> ConversationState:
        """
        Attempt a state transition triggered by *event*.

        Raises ValueError if the transition is not allowed from the current state.

        Returns:
            The new ConversationState after transition.
        """
        current = self.get_state_enum(user_id, chat_id)

        allowed = _TRANSITIONS.get(current, set())
        if event not in allowed:
            logger.warning(
                "Invalid transition: %s -[%s]-> ? (allowed: %s)",
                current.value, event, allowed,
            )
            # Graceful fallback: force to IDLE on invalid transition
            if event in ("cancel", "timeout"):
                new_state = ConversationState.IDLE
            else:
                raise ValueError(
                    f"Cannot fire '{event}' from state '{current.value}'. "
                    f"Allowed events: {allowed}"
                )
        else:
            new_state = _TRANSITION_TARGET.get(event, ConversationState.IDLE)

        expires = None
        if new_state in (
            ConversationState.AWAITING_CLARIFICATION,
            ConversationState.AWAITING_CONFIRMATION,
            ConversationState.AWAITING_INPUT,
        ):
            expires = time.time() + timeout_seconds

        self._set_state(
            user_id, chat_id, new_state,
            data or {},
            pending_action=pending_action,
            workflow_steps=workflow_steps,
            expires_at=expires,
        )

        logger.info(
            "State transition: user=%d chat=%d  %s -[%s]-> %s",
            user_id, chat_id, current.value, event, new_state.value,
        )
        return new_state

    def reset(self, user_id: int, chat_id: int = 0):
        """Force-reset to IDLE (e.g. user says "start over")."""
        self._set_state(user_id, chat_id, ConversationState.IDLE, {})
        logger.info("State reset: user=%d chat=%d -> IDLE", user_id, chat_id)

    # ── convenience queries ──────────────────────────────────────────────

    def is_awaiting(self, user_id: int, chat_id: int = 0) -> bool:
        """True if user is in any AWAITING_* state."""
        s = self.get_state_enum(user_id, chat_id)
        return s in (
            ConversationState.AWAITING_CLARIFICATION,
            ConversationState.AWAITING_CONFIRMATION,
            ConversationState.AWAITING_INPUT,
        )

    def is_idle(self, user_id: int, chat_id: int = 0) -> bool:
        return self.get_state_enum(user_id, chat_id) == ConversationState.IDLE

    # ── internal persistence ─────────────────────────────────────────────

    def _set_state(
        self,
        user_id: int,
        chat_id: int,
        state: ConversationState,
        data: Dict[str, Any],
        pending_action: Optional[str] = None,
        workflow_steps: Optional[list] = None,
        expires_at: Optional[float] = None,
    ):
        with self.db.get_connection() as conn:
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {self.TABLE}
                (user_id, chat_id, state, event_data, pending_action,
                 workflow_steps, workflow_index, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    user_id,
                    chat_id,
                    state.value,
                    json.dumps(data, default=str),
                    pending_action,
                    json.dumps(workflow_steps) if workflow_steps else None,
                    time.time(),
                    expires_at,
                ),
            )
            conn.commit()

    # ── debug helper ─────────────────────────────────────────────────────

    def debug_info(self, user_id: int, chat_id: int = 0) -> str:
        """Return human-readable state info for /debug command."""
        info = self.get_state(user_id, chat_id)
        lines = [
            f"State: {info['state']}",
            f"Pending action: {info.get('pending_action', 'none')}",
            f"Data keys: {list(info.get('data', {}).keys())}",
        ]
        wf = info.get("workflow_steps")
        if wf:
            lines.append(f"Workflow: step {info.get('workflow_index', 0)+1}/{len(wf)}")
        return "\n".join(lines)
