"""
Core Action Registry System for Mode 4.

Universal action registry that sits between intent detection and execution,
handling parameter extraction, ambiguity resolution, risk validation,
and context-aware execution across ALL capabilities simultaneously.
"""

from core.actions import (
    ACTIONS,
    ActionSchema,
    RiskLevel,
    get_action_schema,
    get_action_name,
)
from core.action_extractor import ActionExtractor
from core.action_validator import ActionValidator, ValidationResult
from core.session_state import SessionState
from core.context_manager import ContextManager
from core.notification_router import NotificationRouter
from core.update_stream import UpdateStream
from core.intent_tree import IntentClassifier, IntentResult, DecisionNode
from core.ambiguity_resolver import AmbiguityResolver, DisambiguationResult
from core.conversation_state import ConversationStateMachine, ConversationState
from core.observability import (
    StructuredLogger,
    PerformanceTracker,
    HealthChecker,
    CircuitBreaker,
)
from core.m1_model_router import M1ModelRouter
from core.safety_interceptor import (
    SafetyViolationError,
    RiskAwareActionValidator,
    risk_based_safety_interceptor,
)
from core.hybrid_intent_classifier import HybridIntentClassifier

__all__ = [
    "ACTIONS",
    "ActionSchema",
    "RiskLevel",
    "get_action_schema",
    "get_action_name",
    "ActionExtractor",
    "ActionValidator",
    "ValidationResult",
    "SessionState",
    "ContextManager",
    "NotificationRouter",
    "UpdateStream",
    "IntentClassifier",
    "IntentResult",
    "DecisionNode",
    "AmbiguityResolver",
    "DisambiguationResult",
    "ConversationStateMachine",
    "ConversationState",
    "StructuredLogger",
    "PerformanceTracker",
    "HealthChecker",
    "CircuitBreaker",
    "M1ModelRouter",
    "SafetyViolationError",
    "RiskAwareActionValidator",
    "risk_based_safety_interceptor",
    "HybridIntentClassifier",
]
