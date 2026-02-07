"""
Action Validator for Mode 4 Action Registry.

Decides whether an action can execute immediately or needs clarification:
1. Missing required parameters  -> ask for them
2. Low confidence               -> confirm interpretation
3. High risk                    -> always confirm
4. Ambiguous match              -> offer choices
5. All clear                    -> execute
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from core.actions import ACTIONS, ActionSchema, RiskLevel

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of action validation."""

    def __init__(
        self,
        can_execute: bool,
        clarification_needed: Optional[str] = None,
        clarification_type: Optional[str] = None,
        suggested_params: Optional[Dict[str, Any]] = None,
        options: Optional[List[Dict[str, Any]]] = None,
    ):
        self.can_execute = can_execute
        self.clarification_needed = clarification_needed
        # Types: "missing_params", "low_confidence", "high_risk", "ambiguous"
        self.clarification_type = clarification_type
        self.suggested_params = suggested_params or {}
        self.options = options or []


class ActionValidator:
    """Validates whether an action can be executed or needs clarification."""

    def __init__(self, db_manager=None, todo_manager=None):
        self.db = db_manager
        self.todo = todo_manager

    def validate(
        self,
        action_name: str,
        params: Dict[str, Any],
        missing_fields: List[str],
        confidence: float,
        context: Dict[str, Any],
    ) -> ValidationResult:
        """
        Decide if we can execute or need clarification.

        Priority order:
        1. Missing required parameters -> ask for them
        2. Low confidence -> confirm interpretation
        3. High risk -> always confirm
        4. Ambiguous match -> offer choices
        5. All clear -> execute
        """
        action_def = ACTIONS[action_name]

        # 1. Check for missing required parameters
        if missing_fields:
            clarification = self._generate_missing_params_question(
                action_name, missing_fields, context
            )
            return ValidationResult(
                can_execute=False,
                clarification_needed=clarification,
                clarification_type="missing_params",
            )

        # 2. Check confidence threshold
        if confidence < 0.70:
            clarification = self._generate_confirmation_question(
                action_name, params, context
            )
            return ValidationResult(
                can_execute=False,
                clarification_needed=clarification,
                clarification_type="low_confidence",
                suggested_params=params,
            )

        # 3. High-risk actions always need explicit confirmation
        if action_def.risk_level == RiskLevel.HIGH:
            clarification = self._generate_risk_warning(
                action_name, params, context
            )
            return ValidationResult(
                can_execute=False,
                clarification_needed=clarification,
                clarification_type="high_risk",
                suggested_params=params,
            )

        # 4. Check for ambiguous matches (multiple valid options)
        ambiguity_check = self._check_ambiguity(action_name, params, context)
        if ambiguity_check:
            options, clarification = ambiguity_check
            return ValidationResult(
                can_execute=False,
                clarification_needed=clarification,
                clarification_type="ambiguous",
                options=options,
            )

        # 5. All validations passed
        return ValidationResult(can_execute=True)

    # -------------------------------------------------------------------------
    # Missing-parameter questions
    # -------------------------------------------------------------------------

    def _generate_missing_params_question(
        self,
        action_name: str,
        missing_fields: List[str],
        context: Dict[str, Any],
    ) -> str:
        """Generate natural language question for missing parameters."""

        if "task_id" in missing_fields:
            active_tasks = context.get("active_tasks", [])
            if not active_tasks:
                return "You don't have any active tasks. Want to create one?"

            task_list = "\n".join(
                f"  {i}. {task.get('title', 'Untitled')}"
                + (
                    f" [{task.get('category', 'General')}]"
                    if task.get("category")
                    else ""
                )
                for i, task in enumerate(active_tasks, 1)
            )
            return (
                f"Which task did you complete?\n{task_list}\n\n"
                "You can say the number or describe it."
            )

        if "recipient_or_thread" in missing_fields:
            recent_emails = context.get("recent_emails", [])
            if recent_emails:
                email_list = "\n".join(
                    f"  {i}. {email.get('sender', 'Unknown')} - "
                    f"{email.get('subject', 'No subject')}"
                    for i, email in enumerate(recent_emails[:5], 1)
                )
                return (
                    f"Who should I draft this email to?\n{email_list}\n\n"
                    "Or tell me a name."
                )
            return "Who should I send this email to?"

        if "idea_text" in missing_fields:
            return "What's your idea? Tell me what you're thinking about."

        if "query" in missing_fields:
            return "What would you like me to search for?"

        if "slug" in missing_fields:
            pending_skills = context.get("pending_skills", [])
            if pending_skills:
                skill_list = "\n".join(
                    f"  {i}. {skill.get('slug', 'Unknown')} - "
                    f"{skill.get('title', 'No title')}"
                    for i, skill in enumerate(pending_skills, 1)
                )
                return (
                    f"Which skill should I finalize?\n{skill_list}\n\n"
                    "You can say the number or slug."
                )
            return "Which skill should I process? (Provide the slug or describe it)"

        if "draft_id" in missing_fields:
            active_drafts = context.get("active_drafts", [])
            if active_drafts:
                draft_list = "\n".join(
                    f"  {i}. To {d.get('recipient', '?')} - "
                    f"{d.get('subject', 'No subject')}"
                    for i, d in enumerate(active_drafts[:5], 1)
                )
                return (
                    f"Which draft should I send?\n{draft_list}\n\n"
                    "Say the number or describe it."
                )
            return "Which draft would you like to send?"

        # Generic fallback
        readable_fields = ", ".join(missing_fields)
        return f"I need more information: {readable_fields}"

    # -------------------------------------------------------------------------
    # Confirmation / risk warnings
    # -------------------------------------------------------------------------

    def _generate_confirmation_question(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Generate confirmation for low-confidence extractions."""
        action_def = ACTIONS[action_name]

        if action_def.confirmation_template:
            enriched_params = self._enrich_params_for_display(
                action_name, params, context
            )
            try:
                return action_def.confirmation_template.format(**enriched_params)
            except KeyError:
                pass

        summary = self._summarize_action(action_name, params, context)
        return f"Just to confirm: {summary}?"

    def _generate_risk_warning(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Generate warning message for high-risk actions."""
        action_def = ACTIONS[action_name]

        if action_def.confirmation_template:
            enriched_params = self._enrich_params_for_display(
                action_name, params, context
            )
            try:
                return action_def.confirmation_template.format(**enriched_params)
            except KeyError:
                pass

        summary = self._summarize_action(action_name, params, context)
        return f"{summary} This action cannot be undone. Confirm?"

    # -------------------------------------------------------------------------
    # Ambiguity detection
    # -------------------------------------------------------------------------

    def _check_ambiguity(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[Tuple[List[Dict[str, Any]], str]]:
        """Check if extracted parameters match multiple valid options."""

        if action_name in ("todo_complete", "todo_delete"):
            task_id = params.get("task_id")
            if task_id and isinstance(task_id, list):
                options = [
                    {"task_id": t["id"], "title": t["title"]} for t in task_id
                ]
                task_list = "\n".join(
                    f"  {i}. {task['title']}"
                    for i, task in enumerate(task_id, 1)
                )
                clarification = (
                    f"I found multiple matching tasks:\n{task_list}\n\n"
                    "Which one did you mean?"
                )
                return (options, clarification)

        if action_name == "email_draft":
            recipient = params.get("recipient_or_thread")
            if recipient and isinstance(recipient, list):
                options = [
                    {"thread_id": e["id"], "subject": e["subject"]}
                    for e in recipient
                ]
                email_list = "\n".join(
                    f"  {i}. {e.get('sender', 'Unknown')} - "
                    f"{e.get('subject', 'No subject')}"
                    for i, e in enumerate(recipient, 1)
                )
                clarification = (
                    f"I found multiple matching emails:\n{email_list}\n\n"
                    "Which thread should I reply to?"
                )
                return (options, clarification)

        return None

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _summarize_action(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Create human-readable summary of what's about to happen."""

        if action_name == "todo_complete":
            task_id = params.get("task_id")
            active_tasks = context.get("active_tasks", [])
            task = next(
                (t for t in active_tasks if t.get("id") == task_id), None
            )
            task_title = task["title"] if task else f"task #{task_id}"
            return f"mark '{task_title}' as complete"

        if action_name == "todo_delete":
            task_id = params.get("task_id")
            active_tasks = context.get("active_tasks", [])
            task = next(
                (t for t in active_tasks if t.get("id") == task_id), None
            )
            task_title = task["title"] if task else f"task #{task_id}"
            return f"permanently delete '{task_title}'"

        if action_name == "email_send":
            draft_id = params.get("draft_id")
            return f"send draft #{draft_id}"

        if action_name == "email_draft":
            recipient = params.get("recipient_or_thread", "Unknown")
            return f"draft email to {recipient}"

        if action_name == "skill_finalize":
            slug = params.get("slug", "Unknown")
            return f"finalize skill '{slug}' and archive to Master Doc"

        action_def = ACTIONS[action_name]
        return action_def.description

    def _enrich_params_for_display(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add human-readable fields to params for template formatting."""
        enriched = dict(params)

        if "task_id" in params:
            active_tasks = context.get("active_tasks", [])
            task = next(
                (t for t in active_tasks if t.get("id") == params["task_id"]),
                None,
            )
            if task:
                enriched["task_title"] = task.get("title", "Unknown")
                enriched["task_category"] = task.get("category", "General")

        if "draft_id" in params or "thread_id" in params:
            enriched.setdefault("subject", "Email")
            enriched.setdefault("recipient", "Unknown")

        if "slug" in params:
            pending_skills = context.get("pending_skills", [])
            skill = next(
                (
                    s
                    for s in pending_skills
                    if s.get("slug") == params["slug"]
                ),
                None,
            )
            if skill:
                enriched["skill_title"] = skill.get("title", "Unknown")

        return enriched
