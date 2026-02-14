"""
Safety Interceptor for Mode 4.

Risk-based safety layer that sits between the ActionValidator and actual execution.

- Intercepts RiskLevel.HIGH actions (like email_send) and downgrades them to safe
  equivalents (email_send -> create_draft with [BOT DRAFT] tag).
- Provides a decorator for async action handlers.
- Raises SafetyViolationError for blocked actions that have no safe redirect.

Works WITH the existing ActionValidator (core/InputOutput/action_validator.py),
not replacing it:
    ActionValidator  = clarification / confirmation logic
    SafetyInterceptor = risk-based action mutation

Usage:
    from core.Infrastructure.safety_interceptor import (
        RiskAwareActionValidator,
        SafetyViolationError,
        risk_based_safety_interceptor,
    )

    validator = RiskAwareActionValidator()
    action, params, redirected, msg = validator.validate_and_maybe_redirect(
        "email_send", {"to": "a@b.com", "subject": "Hi"}, user_confirmed=False
    )
    # action == "email_draft", params["subject"] == "[BOT DRAFT] Hi", redirected == True
"""

import functools
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from core.Infrastructure.actions import ACTIONS, RiskLevel

logger = logging.getLogger(__name__)


# ── Exceptions ───────────────────────────────────────────────────────────────

class SafetyViolationError(Exception):
    """Raised when an action violates safety constraints and cannot proceed."""

    def __init__(self, action: str, reason: str, suggestion: str = ""):
        self.action = action
        self.reason = reason
        self.suggestion = suggestion
        super().__init__(f"Safety violation on '{action}': {reason}")


# ── Validator ────────────────────────────────────────────────────────────────

class RiskAwareActionValidator:
    """
    Validates actions against risk policies before execution.

    Policy:
      - RiskLevel.HIGH + service == GMAIL send -> silently redirect to draft
        with [BOT DRAFT] subject prefix.
      - RiskLevel.HIGH + no redirect mapping + not confirmed -> raise error.
      - Everything else passes through unchanged.
    """

    # Actions that get silently redirected to safe alternatives
    REDIRECT_MAP: Dict[str, str] = {
        "email_send": "email_draft",  # sends become drafts
    }

    def validate_and_maybe_redirect(
        self,
        action_name: str,
        params: Dict[str, Any],
        user_confirmed: bool = False,
    ) -> Tuple[str, Dict[str, Any], bool, str]:
        """
        Check action risk and potentially redirect.

        Args:
            action_name: Registry key (e.g. "email_send")
            params: Action parameters dict
            user_confirmed: Whether the user explicitly confirmed this action

        Returns:
            (final_action_name, final_params, was_redirected, message)

        Raises:
            SafetyViolationError: If HIGH risk, no redirect available, and
                                  not user-confirmed.
        """
        schema = ACTIONS.get(action_name)
        if schema is None:
            return (action_name, params, False, "")

        if schema.risk_level != RiskLevel.HIGH:
            return (action_name, params, False, "")

        # HIGH risk but user explicitly confirmed -> allow through
        if user_confirmed:
            logger.info("User confirmed HIGH risk action: %s", action_name)
            return (action_name, params, False, "User confirmed HIGH risk action")

        # Check redirect map
        redirect_to = self.REDIRECT_MAP.get(action_name)
        if redirect_to:
            new_params = dict(params)

            # Prepend [BOT DRAFT] to subject if present
            if "subject" in new_params:
                subj = new_params["subject"]
                if not subj.startswith("[BOT DRAFT]"):
                    new_params["subject"] = f"[BOT DRAFT] {subj}"

            new_params["_safety_intercepted"] = True
            new_params["_original_request"] = action_name

            logger.warning(
                "SAFETY INTERCEPT: %s -> %s (user=%s, subject=%s)",
                action_name,
                redirect_to,
                new_params.get("to", "unknown"),
                new_params.get("subject", "N/A")[:50],
            )

            return (
                redirect_to,
                new_params,
                True,
                f"Redirected to '{redirect_to}' for safety. "
                f"Original action '{action_name}' requires explicit confirmation.",
            )

        # HIGH risk, no redirect, not confirmed -> block
        suggestion = ""
        if schema.confirmation_template:
            suggestion = f"Ask user to confirm: '{schema.confirmation_template}'"
        elif schema.description:
            suggestion = f"Ask user to confirm: '{schema.description}'"

        raise SafetyViolationError(
            action=action_name,
            reason="Action has risk_level=HIGH and was not user-confirmed",
            suggestion=suggestion,
        )


# ── Decorator ────────────────────────────────────────────────────────────────

def risk_based_safety_interceptor(func: Callable) -> Callable:
    """
    Decorator for async action handler functions.

    Wraps the handler to check risk level before execution.
    If the action is HIGH risk and unconfirmed, either redirects or raises.

    Usage::

        @risk_based_safety_interceptor
        async def execute_action(action_name, params, context):
            ...
    """

    @functools.wraps(func)
    async def wrapper(
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        **kwargs,
    ):
        validator = RiskAwareActionValidator()
        user_confirmed = context.get("user_confirmed", False)

        final_action, final_params, was_redirected, message = (
            validator.validate_and_maybe_redirect(action_name, params, user_confirmed)
        )

        if was_redirected:
            context["safety_redirect_message"] = message

        return await func(final_action, final_params, context, **kwargs)

    return wrapper
