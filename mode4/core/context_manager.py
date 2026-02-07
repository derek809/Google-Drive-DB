"""
Context Manager for Mode 4 Action Registry.

Implements the "Context-Aware Routing" feature to solve the "it" problem:
- Tracks the "Current Subject" of conversation
- Stores last message_id, thread_id, draft_id for 30 minutes
- Automatically injects context when user says "it", "that", "this"

Also handles multi-turn entity resolution:
- Entity Tracking: Store "George" and "W9" as active entities
- Pronoun Resolution: "Email it to Sarah" maps "it" to the W9 from previous step
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Manages conversational context for natural pronoun resolution.
    Implements the "Context-Aware Routing" feature.
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

    def inject_context_if_needed(
        self,
        user_id: int,
        user_text: str,
        current_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check if user text contains pronouns/relative references.
        If so, inject the "Current Subject" from session state.
        """
        text_lower = user_text.lower()

        # Check if any pronouns/references are present
        has_reference = any(
            pronoun in text_lower
            for pronoun in self.pronouns + self.relative_refs
        )

        if not has_reference:
            return current_params

        # Get current subject from session
        current_subject = self.session.get_current_subject(user_id)

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

        if current_params.get("_context_injected"):
            logger.info(
                "Context injected for user %d: %s -> %s",
                user_id,
                subject_type,
                subject_id,
            )

        return current_params

    def update_context_after_action(
        self,
        user_id: int,
        action_name: str,
        params: Dict[str, Any],
        result: Any,
    ):
        """
        After an action executes, update the "Current Subject" for future reference.
        """
        result_dict = result if isinstance(result, dict) else {}

        if action_name in ("email_search", "email_draft"):
            entity_id = result_dict.get("thread_id") or result_dict.get(
                "message_id"
            )
            if entity_id:
                self.session.store_current_subject(
                    user_id,
                    subject_type="email",
                    subject_id=entity_id,
                    subject_data=result_dict,
                )

        elif action_name in ("todo_add", "todo_complete"):
            if "task_id" in params:
                self.session.store_current_subject(
                    user_id,
                    subject_type="task",
                    subject_id=params["task_id"],
                    subject_data=params,
                )

        elif action_name == "email_send":
            if "draft_id" in params:
                self.session.store_current_subject(
                    user_id,
                    subject_type="draft",
                    subject_id=params["draft_id"],
                    subject_data=result_dict,
                )

        elif action_name in ("skill_create", "skill_finalize"):
            slug = result_dict.get("slug") or params.get("slug")
            if slug:
                self.session.store_current_subject(
                    user_id,
                    subject_type="skill",
                    subject_id=slug,
                    subject_data=result_dict or params,
                )
