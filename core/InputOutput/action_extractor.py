"""
Parameter Extractor for Mode 4 Action Registry.

Extracts action parameters from natural language using a hybrid approach:
1. Deterministic regex patterns (fast, high confidence)
2. LLM-based fuzzy extraction via Ollama or Claude (fallback)

Design decision: deterministic-first extraction minimises latency
while LLM fallback handles fuzzy references like "the mandate one".
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from core.actions import ACTIONS, ActionSchema

if TYPE_CHECKING:
    from ollama_client import OllamaClient
    from claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class ActionExtractor:
    """Extracts parameters from natural language using deterministic + LLM hybrid."""

    def __init__(
        self,
        ollama_client: "OllamaClient",
        claude_client: Optional["ClaudeClient"] = None,
    ):
        self.ollama = ollama_client
        self.claude = claude_client

    def extract_params(
        self,
        action_name: str,
        user_text: str,
        context: Dict[str, Any],
        use_claude_for_high_risk: bool = True,
    ) -> Tuple[Dict[str, Any], List[str], float, str]:
        """
        Extract parameters for an action from user text.

        Returns:
            (params_dict, missing_fields, confidence_score, reasoning)
        """
        action_def = ACTIONS[action_name]

        # 1. Try deterministic extraction first
        deterministic_result = self._try_deterministic_extraction(
            action_def, user_text, context
        )
        if deterministic_result:
            params, confidence, reasoning = deterministic_result
            missing = self._find_missing_required(action_def, params)
            return (params, missing, confidence, f"Deterministic: {reasoning}")

        # 2. Fall back to LLM extraction
        llm_to_use = self.ollama
        if (
            use_claude_for_high_risk
            and action_def.risk_level.value == "high"
            and self.claude
        ):
            llm_to_use = self.claude

        return self._llm_extraction(action_def, user_text, context, llm_to_use)

    # -------------------------------------------------------------------------
    # Deterministic extraction
    # -------------------------------------------------------------------------

    def _try_deterministic_extraction(
        self,
        action_def: ActionSchema,
        user_text: str,
        context: Dict[str, Any],
    ) -> Optional[Tuple[Dict[str, Any], float, str]]:
        """Attempt pattern-based extraction before LLM."""

        for pattern in action_def.deterministic_patterns:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                result = self._map_match_to_params(action_def, match, context)
                if result is not None:
                    return result

        return None

    def _map_match_to_params(
        self,
        action_def: ActionSchema,
        match: re.Match,
        context: Dict[str, Any],
    ) -> Optional[Tuple[Dict[str, Any], float, str]]:
        """Convert a regex match into typed parameters for the given action."""

        if action_def.intent in ("TODO_COMPLETE", "TODO_DELETE"):
            task_id = int(match.group(1))
            active_tasks = context.get("active_tasks", [])
            if any(
                t.get("id") == task_id or t.get("number") == task_id
                for t in active_tasks
            ):
                return (
                    {"task_id": task_id},
                    0.95,
                    f"Matched pattern -> task_id={task_id}",
                )
            # Still return the id even if we can't validate it against the
            # active list -- the validator will catch it.
            return (
                {"task_id": task_id},
                0.80,
                f"Matched pattern -> task_id={task_id} (not validated against context)",
            )

        if action_def.intent == "TODO_ADD":
            title = match.group(1).strip()
            priority = "normal"
            if any(
                word in title.lower() for word in ("urgent", "asap", "critical")
            ):
                priority = "high"
            return (
                {"title": title, "priority": priority},
                0.90,
                "Extracted task title from pattern",
            )

        if action_def.intent == "EMAIL_DRAFT":
            recipient = match.group(1).strip()
            return (
                {"recipient_or_thread": recipient},
                0.85,
                f"Extracted recipient '{recipient}'",
            )

        if action_def.intent == "EMAIL_SEARCH":
            query = match.group(1).strip()
            return (
                {"query": query},
                0.90,
                f"Extracted search query '{query}'",
            )

        if action_def.intent in ("TODO_LIST", "SKILL_LIST"):
            return ({}, 0.95, "Matched list command pattern")

        if action_def.intent == "EMAIL_UNREAD":
            return ({}, 0.95, "Matched unread command pattern")

        if action_def.intent == "EMAIL_SEND":
            try:
                draft_id = match.group(1)
                return (
                    {"draft_id": draft_id},
                    0.90,
                    f"Extracted draft_id '{draft_id}'",
                )
            except IndexError:
                # "send the email" variant — no captured group
                return ({}, 0.70, "Matched send pattern without explicit draft_id")

        # Generic fallback for any captured group
        try:
            captured = match.group(1).strip()
            first_required = (
                action_def.required_params[0]
                if action_def.required_params
                else None
            )
            if first_required:
                return (
                    {first_required: captured},
                    0.80,
                    f"Generic pattern match -> {first_required}='{captured}'",
                )
        except (IndexError, AttributeError):
            pass

        return None

    # -------------------------------------------------------------------------
    # LLM-based extraction
    # -------------------------------------------------------------------------

    def _llm_extraction(
        self,
        action_def: ActionSchema,
        user_text: str,
        context: Dict[str, Any],
        llm_client: Any,
    ) -> Tuple[Dict[str, Any], List[str], float, str]:
        """Use LLM for fuzzy parameter extraction."""

        context_str = self._build_context_string(action_def, context)

        persona_note = ""
        if "persona_config" in context:
            persona_note = (
                f"\n**User's Communication Style**: "
                f"{json.dumps(context['persona_config'], indent=2)}"
            )

        prompt = f"""Extract parameters from the user's message for this action.

**Action**: {action_def.description}
**Required parameters**: {action_def.required_params}
**Optional parameters**: {action_def.optional_params}

**User said**: "{user_text}"

**Available context**:
{context_str}{persona_note}

**Instructions**:
1. For fuzzy references like "the mandate one", use context to find the best match
2. If a required parameter cannot be determined, set it to null
3. Return confidence between 0.0 and 1.0
4. Provide brief reasoning
5. When matching tasks/emails, prefer recent items unless user specifies otherwise
6. Consider Derek's typical communication patterns when interpreting ambiguous requests

**Return ONLY valid JSON**:
{{
    "params": {{"param_name": "value"}},
    "missing": ["list", "of", "missing", "required", "params"],
    "confidence": 0.75,
    "reasoning": "brief explanation"
}}"""

        try:
            response = llm_client.generate(prompt)

            # Parse JSON (handle markdown code blocks)
            json_str = response.strip()
            if json_str.startswith("```"):
                json_match = re.search(
                    r"```(?:json)?\n(.*?)\n```", json_str, re.DOTALL
                )
                json_str = json_match.group(1) if json_match else response

            result = json.loads(json_str)

            return (
                result.get("params", {}),
                result.get("missing", action_def.required_params),
                float(result.get("confidence", 0.5)),
                result.get("reasoning", "LLM extraction"),
            )

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("LLM extraction failed: %s", e)
            return (
                {},
                list(action_def.required_params),
                0.0,
                f"LLM extraction failed: {e}",
            )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _build_context_string(
        self, action_def: ActionSchema, context: Dict[str, Any]
    ) -> str:
        """Format context for LLM prompt."""
        lines: List[str] = []
        for ctx_key in action_def.context_needed:
            if ctx_key in context and context[ctx_key]:
                lines.append(f"\n**{ctx_key}**:")

                data = context[ctx_key]
                if isinstance(data, list) and len(data) > 0:
                    for i, item in enumerate(data[:10], 1):
                        if isinstance(item, dict):
                            title = (
                                item.get("title")
                                or item.get("subject")
                                or item.get("name", "Unknown")
                            )
                            item_id = item.get("id", i)
                            lines.append(f"  {i}. [ID:{item_id}] {title}")
                        else:
                            lines.append(f"  {i}. {item}")
                else:
                    lines.append(f"  {json.dumps(data, indent=2)}")

        return "\n".join(lines) if lines else "(No context provided)"

    @staticmethod
    def _find_missing_required(
        action_def: ActionSchema, params: Dict[str, Any]
    ) -> List[str]:
        """Identify which required parameters are missing or null."""
        missing = []
        for req_param in action_def.required_params:
            if req_param not in params or params[req_param] is None:
                missing.append(req_param)
        return missing
