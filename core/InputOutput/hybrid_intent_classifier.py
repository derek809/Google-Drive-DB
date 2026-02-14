"""
Hybrid Intent Classifier for Mode 4.

Two-stage classification:
  Stage 1: HuggingFace transformer model for broad category detection (fast ML).
  Stage 2: Existing IntentClassifier (decision tree) for detailed routing +
           parameter extraction.

Falls back gracefully: if the HF model is unavailable (transformers/torch
not installed), the tree classifier is used alone -- which is the current
behaviour.

Returns the same IntentResult namedtuple as the existing intent_tree.py
for drop-in compatibility.

Usage:
    from core.InputOutput.hybrid_intent_classifier import HybridIntentClassifier

    classifier = HybridIntentClassifier()
    result = classifier.classify("draft an email to John", context={})
    # result.category == "email_action"
    # result.confidence == 0.92
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── HuggingFace pipeline (optional) ─────────────────────────────────────────

_HF_CLASSIFIER = None
_HF_AVAILABLE = False

try:
    from transformers import pipeline as hf_pipeline

    _HF_CLASSIFIER = hf_pipeline(
        "text-classification",
        model="Falconsai/intent_classification",
        device=-1,  # CPU by default; change to 0 for MPS/GPU
    )
    _HF_AVAILABLE = True
    logger.info("HuggingFace intent classifier loaded (Falconsai)")
except Exception as e:
    logger.info("HuggingFace model unavailable (tree-only mode): %s", e)

# ── Import existing tree classifier ─────────────────────────────────────────

from core.InputOutput.intent_tree import IntentClassifier, IntentResult


# ── Label mapping: HF output -> our tree action categories ──────────────────

_HF_LABEL_MAP: Dict[str, str] = {
    # Falconsai/intent_classification labels (varies by model version)
    "send_email": "email_action",
    "email": "email_action",
    "calendar": "workflow_action",
    "todo": "todo_add",
    "reminder": "todo_add",
    "greeting": "casual",
    "weather": "casual",
    "music": "casual",
    "news": "casual",
    "query_database": "sheet_action",
    "telegram_notify": "workflow_action",
    "sheets_update": "sheet_action",
    "summarize": "email_action",
}


# ── Hybrid Classifier ───────────────────────────────────────────────────────

class HybridIntentClassifier:
    """
    Two-stage intent classifier combining ML model with decision tree.

    Stage 1 (optional): HuggingFace local model narrows to a broad category.
    Stage 2 (always):   IntentClassifier tree walk produces detailed category,
                         confidence, extracted parameters, and follow-up question.

    Confidence logic:
      - Both stages agree        -> tree confidence boosted by up to +0.1
      - Tree uncertain, ML has   -> use ML category at reduced confidence
      - Stages disagree          -> prefer tree (it has extracted params)
      - ML unavailable           -> tree result returned as-is
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: Path to intent_tree.json. If None, uses default
                         playbook/intent_tree.json resolved by IntentClassifier.
        """
        self._tree_classifier = IntentClassifier(config_path=config_path)
        self._hf_available = _HF_AVAILABLE

    def classify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentResult:
        """
        Classify user intent using hybrid approach.

        Args:
            text: Raw user input.
            context: Optional dict with keys like ``active_tasks``,
                     ``recent_emails``, etc.

        Returns:
            IntentResult(category, confidence, parameters, follow_up_question)
        """
        if context is None:
            context = {}

        # Stage 2 always runs (it extracts parameters)
        tree_result = self._tree_classifier.classify(text, context)

        # Stage 1: ML model (optional confidence boost)
        if not self._hf_available or _HF_CLASSIFIER is None:
            return tree_result

        try:
            hf_output = _HF_CLASSIFIER(text[:512])  # Truncate for model limits
            if not hf_output:
                return tree_result

            hf_label = hf_output[0].get("label", "").lower()
            hf_score = hf_output[0].get("score", 0.0)
            mapped_category = _HF_LABEL_MAP.get(hf_label)

            if mapped_category and mapped_category == tree_result.category:
                # Both agree: boost confidence
                boosted = min(1.0, tree_result.confidence + (hf_score * 0.1))
                return IntentResult(
                    category=tree_result.category,
                    confidence=boosted,
                    parameters=tree_result.parameters,
                    follow_up_question=tree_result.follow_up_question,
                )

            if mapped_category and tree_result.category == "clarification_needed":
                # Tree was uncertain but ML has an idea: use ML category
                # with conservative confidence and no extracted params.
                return IntentResult(
                    category=mapped_category,
                    confidence=hf_score * 0.6,  # Conservative
                    parameters={},
                    follow_up_question=None,
                )

            # Stages disagree: prefer tree (it has params)
            return tree_result

        except Exception as e:
            logger.debug("HF classification failed, using tree-only: %s", e)
            return tree_result

    # ── Delegation helpers ───────────────────────────────────────────────

    @property
    def thresholds(self) -> Dict[str, float]:
        """Delegate to tree classifier's thresholds."""
        return self._tree_classifier.thresholds

    def reload_if_changed(self):
        """Delegate to tree classifier's hot-reload."""
        self._tree_classifier.reload_if_changed()
