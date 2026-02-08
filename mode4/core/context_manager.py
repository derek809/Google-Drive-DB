"""
Context Manager for Mode 4 Action Registry.

Implements the "Context-Aware Routing" feature to solve the "it" problem:
- Tracks the "Current Subject" of conversation
- Stores last message_id, thread_id, draft_id for 30 minutes
- Automatically injects context when user says "it", "that", "this"

Also handles multi-turn entity resolution:
- Entity Tracking: Store "George" and "W9" as active entities
- Pronoun Resolution: "Email it to Sarah" maps "it" to the W9 from previous step

Enhanced with:
- Pronoun Resolution Matrix: maps pronouns to subjects based on recency,
  syntactic role, and semantic compatibility.
- Multiple concurrent subjects: "the email" + "the task" can coexist.
- Conversation topic stack: "actually, about that other thing..." pops context.
- Implicit context injection: "the big one" → search metadata for "big".
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Semantic compatibility rules ─────────────────────────────────────────────
# Maps action verbs to the subject types they are compatible with.
_VERB_SUBJECT_COMPAT = {
    "complete":  {"task"},
    "mark":      {"task"},
    "finish":    {"task"},
    "done":      {"task"},
    "delete":    {"task"},
    "remove":    {"task"},
    "send":      {"email", "draft"},
    "forward":   {"email"},
    "reply":     {"email"},
    "respond":   {"email"},
    "draft":     {"email"},
    "finalize":  {"skill"},
    "archive":   {"task", "skill", "email"},
    "open":      {"email", "skill", "sheet"},
    "edit":      {"draft", "skill", "sheet"},
}


class ContextManager:
    """
    Manages conversational context for natural pronoun resolution.
    Implements the "Context-Aware Routing" feature with enhanced
    pronoun resolution matrix and conversation topic stack.
    """

    def __init__(self, session_state):
        self.session = session_state

        # Pronouns and references to watch for
        self.pronouns = ["it", "that", "this", "them", "those", "the one"]
        self.relative_refs = [
            "last one",
            "previous",
            "earlier",
            "recent",
        ]

        # In-memory topic stack per user (LIFO)
        self._topic_stacks: Dict[int, List[Dict[str, Any]]] = {}

    # ── Main injection entry point ───────────────────────────────────────

    def inject_context_if_needed(
        self,
        user_id: int,
        user_text: str,
        current_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check if user text contains pronouns/relative references.
        If so, inject the "Current Subject" from session state.

        Enhanced: uses semantic compatibility and topic stack.
        """
        text_lower = user_text.lower()

        # Check for topic-switch phrases
        if self._detect_topic_switch(text_lower):
            self._pop_topic(user_id)

        # Check if any pronouns/references are present
        has_reference = any(
            pronoun in text_lower
            for pronoun in self.pronouns + self.relative_refs
        )

        if not has_reference:
            # Still try implicit context: "the big one", "the mandate one"
            return self._try_implicit_injection(user_id, user_text, current_params)

        # Determine action verb for semantic filtering
        action_verb = self._extract_action_verb(text_lower)
        compatible_types = _VERB_SUBJECT_COMPAT.get(action_verb)

        # Get current subject from session (type-filtered if possible)
        current_subject = self._get_best_subject(user_id, compatible_types)

        if not current_subject:
            return current_params

        # Inject appropriate parameters based on subject type
        subject_type = current_subject.get("type")
        subject_id = current_subject.get("id")

        if subject_type == "email":
            if not current_params.get("recipient_or_thread"):
                current_params["recipient_or_thread"] = subject_id
                current_params["_context_injected"] = True
                current_params["_context_source"] = "last_email"

        elif subject_type == "task":
            if not current_params.get("task_id"):
                current_params["task_id"] = subject_id
                current_params["_context_injected"] = True
                current_params["_context_source"] = "last_task"

        elif subject_type == "draft":
            if not current_params.get("draft_id"):
                current_params["draft_id"] = subject_id
                current_params["_context_injected"] = True
                current_params["_context_source"] = "last_draft"

        elif subject_type == "skill":
            if not current_params.get("slug"):
                current_params["slug"] = subject_id
                current_params["_context_injected"] = True
                current_params["_context_source"] = "last_skill"

        elif subject_type == "sheet":
            if not current_params.get("sheet_id"):
                current_params["sheet_id"] = subject_id
                current_params["_context_injected"] = True
                current_params["_context_source"] = "last_sheet"

        if current_params.get("_context_injected"):
            logger.info(
                "Context injected for user %d: %s -> %s",
                user_id,
                subject_type,
                subject_id,
            )

        return current_params

    # ── Post-action context update ───────────────────────────────────────

    def update_context_after_action(
        self,
        user_id: int,
        action_name: str,
        params: Dict[str, Any],
        result: Any,
    ):
        """
        After an action executes, update the "Current Subject" for future reference.
        Also pushes to the topic stack.
        """
        result_dict = result if isinstance(result, dict) else {}

        subject_type = None
        subject_id = None
        subject_data = None

        if action_name in ("email_search", "email_draft"):
            entity_id = result_dict.get("thread_id") or result_dict.get("message_id")
            if entity_id:
                subject_type, subject_id = "email", entity_id
                subject_data = result_dict

        elif action_name in ("todo_add", "todo_complete"):
            if "task_id" in params:
                subject_type, subject_id = "task", params["task_id"]
                subject_data = params

        elif action_name == "email_send":
            if "draft_id" in params:
                subject_type, subject_id = "draft", params["draft_id"]
                subject_data = result_dict

        elif action_name in ("skill_create", "skill_finalize"):
            slug = result_dict.get("slug") or params.get("slug")
            if slug:
                subject_type, subject_id = "skill", slug
                subject_data = result_dict or params

        elif action_name in ("sheet_create", "sheet_sync"):
            sid = result_dict.get("sheet_id") or params.get("sheet_id")
            if sid:
                subject_type, subject_id = "sheet", sid
                subject_data = result_dict or params

        if subject_type and subject_id:
            self.session.store_current_subject(
                user_id,
                subject_type=subject_type,
                subject_id=subject_id,
                subject_data=subject_data or {},
            )
            self._push_topic(user_id, subject_type, subject_id, subject_data or {})

    # ── Pronoun resolution helpers ───────────────────────────────────────

    def _get_best_subject(
        self, user_id: int, compatible_types: Optional[set] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most-recent subject that is semantically compatible.

        If *compatible_types* is None, falls back to the most-recent subject
        of any type (pure recency).
        """
        subject = self.session.get_current_subject(user_id)
        if not subject:
            return None

        # If no type filter, return whatever is most recent
        if not compatible_types:
            return subject

        # Check compatibility
        if subject.get("type") in compatible_types:
            return subject

        # Type mismatch – try topic stack for a compatible entry
        stack = self._topic_stacks.get(user_id, [])
        for entry in reversed(stack):
            if entry.get("type") in compatible_types:
                return entry

        return None

    @staticmethod
    def _extract_action_verb(text_lower: str) -> Optional[str]:
        """Extract the primary action verb from user text."""
        for verb in _VERB_SUBJECT_COMPAT:
            if verb in text_lower:
                return verb
        return None

    # ── Topic stack management ───────────────────────────────────────────

    def _push_topic(self, user_id: int, subject_type: str, subject_id: Any, data: Dict):
        if user_id not in self._topic_stacks:
            self._topic_stacks[user_id] = []
        stack = self._topic_stacks[user_id]
        stack.append({
            "type": subject_type,
            "id": subject_id,
            "data": data,
            "timestamp": time.time(),
        })
        # Keep stack bounded
        if len(stack) > 20:
            self._topic_stacks[user_id] = stack[-20:]

    def _pop_topic(self, user_id: int) -> Optional[Dict]:
        stack = self._topic_stacks.get(user_id, [])
        if len(stack) > 1:
            stack.pop()  # remove current
            previous = stack[-1]
            # Re-store as current subject
            self.session.store_current_subject(
                user_id,
                subject_type=previous["type"],
                subject_id=previous["id"],
                subject_data=previous.get("data", {}),
            )
            logger.info("Topic popped for user %d -> %s:%s", user_id, previous["type"], previous["id"])
            return previous
        return None

    @staticmethod
    def _detect_topic_switch(text_lower: str) -> bool:
        """Detect phrases like 'actually about that other thing'."""
        switch_phrases = [
            "actually about",
            "about that other",
            "back to the",
            "going back to",
            "the other thing",
            "never mind that",
            "forget that",
        ]
        return any(phrase in text_lower for phrase in switch_phrases)

    # ── Implicit context injection ───────────────────────────────────────

    def _try_implicit_injection(
        self,
        user_id: int,
        user_text: str,
        current_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle phrases like "the big one" or "the mandate one" by searching
        stored entity metadata for keyword matches.
        """
        m = re.search(r"the\s+(\w+)\s+one", user_text, re.IGNORECASE)
        if not m:
            return current_params

        keyword = m.group(1).lower()

        # Search topic stack for matching keyword in data
        stack = self._topic_stacks.get(user_id, [])
        for entry in reversed(stack):
            data = entry.get("data", {})
            searchable = json.dumps(data).lower()
            if keyword in searchable:
                subject_type = entry["type"]
                subject_id = entry["id"]
                if subject_type == "task" and not current_params.get("task_id"):
                    current_params["task_id"] = subject_id
                    current_params["_context_injected"] = True
                    current_params["_context_source"] = f"implicit_keyword:{keyword}"
                elif subject_type == "email" and not current_params.get("recipient_or_thread"):
                    current_params["recipient_or_thread"] = subject_id
                    current_params["_context_injected"] = True
                    current_params["_context_source"] = f"implicit_keyword:{keyword}"
                break

        return current_params
