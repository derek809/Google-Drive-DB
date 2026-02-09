"""
Core Action Registry for Mode 4.

Defines formal contracts (ActionSchema) for every executable action in the system.
Each action specifies required/optional parameters, context needs, risk level,
fallback strategies, and deterministic extraction patterns.

Risk Levels:
    LOW    - Reversible actions (TODO_COMPLETE, TODO_LIST)
    MEDIUM - Reviewable before commit (EMAIL_DRAFT, SKILL_CREATE)
    HIGH   - Irreversible actions (EMAIL_SEND, TODO_DELETE)
"""

from enum import Enum
from typing import Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Fallback for environments without pydantic
    from dataclasses import dataclass, field as _field

    class _BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _Field:
        @staticmethod
        def __call__(**kwargs):
            return kwargs.get("default_factory", lambda: kwargs.get("default"))()

    BaseModel = _BaseModel  # type: ignore[misc]

    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionSchema(BaseModel):
    """Formal contract for an executable action."""

    intent: str  # Maps to Intent enum value
    required_params: List[str]
    optional_params: List[str] = Field(default_factory=list)
    context_needed: List[str] = Field(default_factory=list)
    risk_level: RiskLevel
    fallback_strategy: str  # "ask", "fuzzy_match_then_ask", "always_confirm", "smart_suggest"
    description: str
    deterministic_patterns: List[str] = Field(default_factory=list)
    confirmation_template: Optional[str] = None
    context_linker_enabled: bool = False
    multi_channel_output: bool = False


# =============================================================================
# Complete Action Registry
# =============================================================================

ACTIONS: Dict[str, ActionSchema] = {
    # =========================================================================
    # TODO ACTIONS
    # =========================================================================
    "todo_complete": ActionSchema(
        intent="TODO_COMPLETE",
        required_params=["task_id"],
        optional_params=[],
        context_needed=["active_tasks"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="fuzzy_match_then_ask",
        description="Mark a task as complete and archive it",
        deterministic_patterns=[
            r"#(\d+)",
            r"task\s+(\d+)",
            r"number\s+(\d+)",
            r"the\s+(\d+)(?:st|nd|rd|th)",
        ],
        confirmation_template="Mark task #{task_id} '{task_title}' as complete?",
        multi_channel_output=True,
    ),
    "todo_add": ActionSchema(
        intent="TODO_ADD",
        required_params=["title"],
        optional_params=["category", "priority"],
        context_needed=["existing_categories", "recent_tasks"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Create a new task",
        deterministic_patterns=[
            r"(?:add|create|new)\s+task[:\s]+(.+)",
            r"(?:todo|task)[:\s]+(.+)",
        ],
        confirmation_template=None,
    ),
    "todo_delete": ActionSchema(
        intent="TODO_DELETE",
        required_params=["task_id"],
        optional_params=[],
        context_needed=["active_tasks"],
        risk_level=RiskLevel.HIGH,
        fallback_strategy="always_confirm",
        description="Permanently delete a task",
        deterministic_patterns=[
            r"delete\s+#?(\d+)",
            r"remove\s+task\s+(\d+)",
        ],
        confirmation_template=(
            "Permanently delete task #{task_id} '{task_title}'? This cannot be undone."
        ),
    ),
    "todo_list": ActionSchema(
        intent="TODO_LIST",
        required_params=[],
        optional_params=["filter_category", "filter_priority"],
        context_needed=["active_tasks"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="List all active tasks",
        deterministic_patterns=[
            r"(?:show|list|what are)\s+(?:my\s+)?tasks",
            r"what\s+do\s+i\s+have\s+to\s+do",
        ],
    ),
    # =========================================================================
    # EMAIL ACTIONS
    # =========================================================================
    "email_draft": ActionSchema(
        intent="EMAIL_DRAFT",
        required_params=["recipient_or_thread"],
        optional_params=["subject", "tone", "model_preference"],
        context_needed=[
            "recent_emails",
            "last_search_results",
            "writing_patterns",
            "persona_config",
        ],
        risk_level=RiskLevel.MEDIUM,
        fallback_strategy="fuzzy_match_then_ask",
        description="Generate an email draft",
        deterministic_patterns=[
            r"draft.*(?:to|for)\s+(\w+)",
            r"reply.*#(\d+)",
            r"respond.*(?:to|about)\s+(.+)",
        ],
        confirmation_template="Draft email to {recipient} about '{subject}'?",
        context_linker_enabled=True,
    ),
    "email_send": ActionSchema(
        intent="EMAIL_SEND",
        required_params=["draft_id"],
        optional_params=[],
        context_needed=["active_drafts"],
        risk_level=RiskLevel.HIGH,
        fallback_strategy="always_confirm",
        description="Send a composed email draft",
        deterministic_patterns=[
            r"send\s+draft\s+#?(\d+)",
            r"send\s+(?:the\s+)?email",
        ],
        confirmation_template=(
            "Send email to {recipient} with subject '{subject}'? Cannot be recalled."
        ),
        multi_channel_output=True,
    ),
    "email_search": ActionSchema(
        intent="EMAIL_SEARCH",
        required_params=["query"],
        optional_params=["sender", "date_range", "has_attachment"],
        context_needed=[],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Search Gmail for specific emails",
        deterministic_patterns=[
            r"find.*email.*(?:from|about)\s+(.+)",
            r"search.*(?:for|about)\s+(.+)",
        ],
    ),
    "email_synthesize": ActionSchema(
        intent="EMAIL_SYNTHESIZE",
        required_params=["thread_id_or_query"],
        optional_params=["synthesis_type"],
        context_needed=["thread_history"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Generate thread synthesis or State of Play summary",
        deterministic_patterns=[
            r"(?:summarize|synthesize)\s+(?:thread|email)",
            r"state\s+of\s+play",
        ],
    ),
    # =========================================================================
    # SKILL ACTIONS
    # =========================================================================
    "skill_create": ActionSchema(
        intent="SKILL_CREATE",
        required_params=["idea_text"],
        optional_params=["category"],
        context_needed=["existing_skills", "recent_brainstorms"],
        risk_level=RiskLevel.MEDIUM,
        fallback_strategy="smart_suggest",
        description="Create a new skill from a brainstorm",
        deterministic_patterns=[
            r"create\s+skill[:\s]+(.+)",
            r"save\s+(?:this\s+)?(?:as\s+)?skill",
        ],
    ),
    "skill_finalize": ActionSchema(
        intent="SKILL_FINALIZE",
        required_params=["slug"],
        optional_params=[],
        context_needed=["pending_skills"],
        risk_level=RiskLevel.MEDIUM,
        fallback_strategy="fuzzy_match_then_ask",
        description="Finalize and archive a skill to Master Doc",
        deterministic_patterns=[
            r"finalize\s+(\w+)",
            r"process.*(?:idea\s+)?inbox",
        ],
        context_linker_enabled=True,
    ),
    "skill_list": ActionSchema(
        intent="SKILL_LIST",
        required_params=[],
        optional_params=["filter_status"],
        context_needed=["existing_skills", "pending_skills"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="List skills/brainstorms with numbered references",
        deterministic_patterns=[
            r"(?:show|list)\s+(?:my\s+)?(?:skills|brainstorms)",
            r"what\s+(?:skills|brainstorms)\s+do\s+i\s+have",
        ],
    ),
    "skill_search": ActionSchema(
        intent="SKILL_SEARCH",
        required_params=["query"],
        optional_params=[],
        context_needed=["existing_skills"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Search skills by keyword or category",
    ),
    "skill_synthesize": ActionSchema(
        intent="SKILL_SYNTHESIZE",
        required_params=["skill_ids"],
        optional_params=["output_format"],
        context_needed=["existing_skills", "recent_brainstorms"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Synthesize multiple brainstorms/skills into single State of Play report",
    ),
    # =========================================================================
    # PROACTIVE ACTIONS
    # =========================================================================
    "digest_generate": ActionSchema(
        intent="DIGEST_GENERATE",
        required_params=[],
        optional_params=["timeframe"],
        context_needed=["recent_threads", "unsent_drafts", "pending_tasks"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Generate a morning digest of important updates",
    ),
    "reminder_set": ActionSchema(
        intent="REMINDER_SET",
        required_params=["task_reference", "delay_hours"],
        optional_params=[],
        context_needed=["active_tasks", "recent_emails"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="fuzzy_match_then_ask",
        description="Set a follow-up reminder",
    ),
    "draft_nudge": ActionSchema(
        intent="DRAFT_NUDGE",
        required_params=["draft_id"],
        optional_params=["nudge_message"],
        context_needed=["active_drafts"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Send gentle nudge about unsent draft (Draft Desertion feature)",
        deterministic_patterns=[
            r"remind.*(?:about\s+)?draft",
            r"nudge.*draft",
        ],
    ),
    "thread_monitor": ActionSchema(
        intent="THREAD_MONITOR",
        required_params=["thread_id"],
        optional_params=["trigger_condition"],
        context_needed=["thread_history"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Monitor email thread for auto-trigger conditions (Event-Based Proactivity)",
    ),
    # =========================================================================
    # UNIVERSAL TOOL ACTIONS
    # =========================================================================
    "data_structure": ActionSchema(
        intent="DATA_STRUCTURE",
        required_params=["unstructured_text", "target_schema"],
        optional_params=["llm_preference"],
        context_needed=[],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Universal Data Structurer: Convert unstructured text to structured JSON",
    ),
    "sheet_sync": ActionSchema(
        intent="SHEET_SYNC",
        required_params=[
            "sheet_id",
            "search_column",
            "search_value",
            "update_column",
            "update_value",
        ],
        optional_params=["create_if_missing"],
        context_needed=["connected_sheets"],
        risk_level=RiskLevel.MEDIUM,
        fallback_strategy="always_confirm",
        description="Universal Lookup & Update: Find row X by value Y and update column Z",
        context_linker_enabled=True,
    ),
    "doc_generate": ActionSchema(
        intent="DOC_GENERATE",
        required_params=["doc_type", "content_source"],
        optional_params=["template", "title"],
        context_needed=["persona_config", "recent_context"],
        risk_level=RiskLevel.MEDIUM,
        fallback_strategy="smart_suggest",
        description="Universal Document Engine: Generate formatted standalone Google Doc",
        context_linker_enabled=True,
    ),
    "workflow_condition": ActionSchema(
        intent="WORKFLOW_CONDITION",
        required_params=["condition", "true_action", "false_action"],
        optional_params=["context_variable"],
        context_needed=["workflow_state"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Decision Gate: If/Then logic for conditional workflows",
    ),
    "context_link": ActionSchema(
        intent="CONTEXT_LINK",
        required_params=["source_resource", "target_resource"],
        optional_params=["link_type"],
        context_needed=["active_resources"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Universal Context Linker: Link resources across platforms automatically",
        context_linker_enabled=True,
    ),
    # =========================================================================
    # SYSTEM / META ACTIONS
    # =========================================================================
    "status": ActionSchema(
        intent="INFO_STATUS",
        required_params=[],
        optional_params=[],
        context_needed=["system_health"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Show system status and health",
    ),
    "unread": ActionSchema(
        intent="EMAIL_UNREAD",
        required_params=[],
        optional_params=["limit"],
        context_needed=[],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Show actionable list of unread emails with context memory",
        deterministic_patterns=[
            r"(?:show|list)\s+unread",
            r"what.*unread\s+emails",
        ],
    ),
    "learning_negative": ActionSchema(
        intent="LEARNING_NEGATIVE",
        required_params=["rejected_item_id", "rejection_reason"],
        optional_params=["improvement_suggestion"],
        context_needed=["recent_generations"],
        risk_level=RiskLevel.LOW,
        fallback_strategy="smart_suggest",
        description="Learn from rejections: Track why user canceled/rejected AI output",
    ),
}


def get_action_schema(intent: str) -> Optional[ActionSchema]:
    """Get action schema by intent name."""
    for _action_name, schema in ACTIONS.items():
        if schema.intent == intent:
            return schema
    return None


def get_action_name(intent: str) -> Optional[str]:
    """Get action name (key) by intent."""
    for action_name, schema in ACTIONS.items():
        if schema.intent == intent:
            return action_name
    return None
