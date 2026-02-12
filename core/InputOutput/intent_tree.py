"""
Intent Decision Tree for Mode 4.

Implements a configurable decision tree that classifies user input into
actionable categories (email_action, sheet_action, workflow_action) or
non-actionable ones (casual, clarification_needed).

The tree is loaded from config/intent_tree.json and evaluated top-down.
Leaf nodes return an IntentResult with category, confidence, extracted
parameters, and an optional follow-up question when clarification is needed.

Integration:
    Called from ConversationManager.classify_intent() as a structured
    replacement for the implicit "conversation gate" logic.
"""

import json
import logging
import os
import re
import time
from collections import namedtuple
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Result type ──────────────────────────────────────────────────────────────

IntentResult = namedtuple(
    "IntentResult",
    ["category", "confidence", "parameters", "follow_up_question"],
)


# ── Decision Node ────────────────────────────────────────────────────────────

class DecisionNode:
    """
    A single node in the decision tree.

    Attributes:
        name:           Human-readable label (for debugging / logging).
        condition_type: One of "keywords", "regex", "always_true".
        condition_data: Data driving the condition check.
        true_branch:    Child DecisionNode if condition matches.
        false_branch:   Child DecisionNode if condition does not match.
        action:         If this is a leaf, the resulting category string.
        extract_params: Optional list of extraction rules for this leaf.
        follow_up:      Optional follow-up question for "clarification_needed".
        confidence:     Base confidence assigned at this leaf (0.0–1.0).
    """

    def __init__(
        self,
        name: str = "",
        condition_type: str = "always_true",
        condition_data: Any = None,
        true_branch: Optional["DecisionNode"] = None,
        false_branch: Optional["DecisionNode"] = None,
        action: Optional[str] = None,
        extract_params: Optional[List[Dict]] = None,
        follow_up: Optional[str] = None,
        confidence: float = 1.0,
    ):
        self.name = name
        self.condition_type = condition_type
        self.condition_data = condition_data or []
        self.true_branch = true_branch
        self.false_branch = false_branch
        self.action = action
        self.extract_params = extract_params or []
        self.follow_up = follow_up
        self.confidence = confidence

    # ── evaluation ───────────────────────────────────────────────────────

    def evaluate(self, text: str, context: Dict[str, Any]) -> bool:
        """Return True if *text* satisfies this node's condition."""
        text_lower = text.lower().strip()
        text_clean = re.sub(r"[^\w\s]", "", text_lower).strip()

        if self.condition_type == "always_true":
            return True

        if self.condition_type == "keywords":
            keywords = self.condition_data
            if isinstance(keywords, list):
                return any(
                    re.search(r"\b" + re.escape(kw) + r"\b", text_clean)
                    for kw in keywords
                )
            return False

        if self.condition_type == "regex":
            patterns = self.condition_data
            if isinstance(patterns, str):
                patterns = [patterns]
            return any(re.search(p, text_lower, re.IGNORECASE) for p in patterns)

        if self.condition_type == "starts_with":
            prefixes = self.condition_data
            if isinstance(prefixes, str):
                prefixes = [prefixes]
            return any(text_clean.startswith(p) for p in prefixes)

        if self.condition_type == "context_check":
            key = self.condition_data
            return bool(context.get(key))

        return False

    # ── parameter extraction helpers ─────────────────────────────────────

    def extract(self, text: str) -> Dict[str, Any]:
        """Run extraction rules against *text* and return captured params."""
        params: Dict[str, Any] = {}
        for rule in self.extract_params:
            pattern = rule.get("pattern")
            param_name = rule.get("param")
            if pattern and param_name:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    try:
                        params[param_name] = m.group(1).strip()
                    except IndexError:
                        params[param_name] = m.group(0).strip()
        return params

    # ── serialisation helpers ────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionNode":
        """Recursively build a tree from a JSON-compatible dict."""
        true_branch = None
        false_branch = None

        if "true_branch" in data and data["true_branch"] is not None:
            true_branch = cls.from_dict(data["true_branch"])
        if "false_branch" in data and data["false_branch"] is not None:
            false_branch = cls.from_dict(data["false_branch"])

        return cls(
            name=data.get("name", ""),
            condition_type=data.get("condition_type", "always_true"),
            condition_data=data.get("condition_data"),
            true_branch=true_branch,
            false_branch=false_branch,
            action=data.get("action"),
            extract_params=data.get("extract_params", []),
            follow_up=data.get("follow_up"),
            confidence=data.get("confidence", 1.0),
        )


# ── Intent Classifier ────────────────────────────────────────────────────────

class IntentClassifier:
    """
    Configurable intent classifier backed by a JSON decision tree.

    Usage::

        classifier = IntentClassifier()
        result = classifier.classify("Hello", context={})
        # result.category == "casual"
    """

    _CONFIG_FILENAME = "intent_tree.json"

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Look in playbook/ directory (project root / playbook)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(project_root, "playbook", self._CONFIG_FILENAME)

        self._config_path = config_path
        self._root: Optional[DecisionNode] = None
        self._config: Dict[str, Any] = {}
        self._load_time: float = 0.0
        self._load()

    # ── loading ──────────────────────────────────────────────────────────

    def _load(self):
        """Load (or reload) the tree from the JSON config file."""
        try:
            with open(self._config_path, "r") as fh:
                self._config = json.load(fh)

            tree_data = self._config.get("tree")
            if tree_data:
                self._root = DecisionNode.from_dict(tree_data)
            else:
                logger.warning("intent_tree.json has no 'tree' key; classifier disabled")
                self._root = None

            self._load_time = time.time()
            logger.info("IntentClassifier loaded from %s", self._config_path)
        except FileNotFoundError:
            logger.warning("Intent tree config not found at %s – using defaults", self._config_path)
            self._root = self._build_default_tree()
            self._load_time = time.time()
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in %s: %s", self._config_path, exc)
            self._root = self._build_default_tree()
            self._load_time = time.time()

    def reload_if_changed(self):
        """Reload config if the file has been modified since last load."""
        try:
            mtime = os.path.getmtime(self._config_path)
            if mtime > self._load_time:
                self._load()
        except OSError:
            pass

    # ── classification ───────────────────────────────────────────────────

    def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> IntentResult:
        """
        Walk the decision tree and return an IntentResult.

        Args:
            text:    Raw user input.
            context: Dict with optional keys like ``active_tasks``,
                     ``recent_emails``, ``last_search_results``, etc.

        Returns:
            IntentResult(category, confidence, parameters, follow_up_question)
        """
        if context is None:
            context = {}

        if self._root is None:
            return IntentResult("clarification_needed", 0.0, {}, "I couldn't classify that. What would you like to do?")

        node = self._root
        depth = 0
        max_depth = 30  # prevent infinite loops in malformed trees

        while node and depth < max_depth:
            depth += 1

            # Leaf node – return result
            if node.action is not None:
                params = node.extract(text)
                confidence = node.confidence

                # If required params are missing for an action, downgrade
                required = self._config.get("required_params", {}).get(node.action, [])
                missing = [p for p in required if p not in params]
                if missing and node.action not in ("casual", "clarification_needed"):
                    return IntentResult(
                        "clarification_needed",
                        max(0.3, confidence - 0.3),
                        params,
                        f"I need more info. What's the {missing[0]}?",
                    )

                return IntentResult(
                    node.action,
                    confidence,
                    params,
                    node.follow_up,
                )

            # Interior node – branch
            if node.evaluate(text, context):
                node = node.true_branch
            else:
                node = node.false_branch

        # Fell through (shouldn't happen with a well-formed tree)
        return IntentResult("clarification_needed", 0.0, {}, "Could you rephrase that?")

    # ── default tree ─────────────────────────────────────────────────────

    @staticmethod
    def _build_default_tree() -> DecisionNode:
        """Hardcoded fallback tree when JSON config is absent."""

        # Leaf nodes
        casual_leaf = DecisionNode(
            name="casual_leaf",
            action="casual",
            confidence=1.0,
        )
        email_action_leaf = DecisionNode(
            name="email_action_leaf",
            action="email_action",
            confidence=0.85,
            extract_params=[
                {"pattern": r"(?:to|for)\s+(\w+)", "param": "recipient"},
                {"pattern": r"(?:about|regarding|re:?)\s+(.+?)(?:\s+and\s+|\s*$)", "param": "topic"},
            ],
        )
        sheet_action_leaf = DecisionNode(
            name="sheet_action_leaf",
            action="sheet_action",
            confidence=0.85,
            extract_params=[
                {"pattern": r"(?:sheet|spreadsheet)\s+(?:for|about|with)\s+(.+)", "param": "sheet_topic"},
            ],
        )
        workflow_action_leaf = DecisionNode(
            name="workflow_action_leaf",
            action="workflow_action",
            confidence=0.75,
        )
        clarification_leaf = DecisionNode(
            name="clarification_leaf",
            action="clarification_needed",
            confidence=0.0,
            follow_up="I'm not sure what you'd like me to do. Could you be more specific?",
        )

        # Multi-step check
        multi_step_node = DecisionNode(
            name="contains_multi_step_indicators",
            condition_type="keywords",
            condition_data=["then", "and then", "after that", "next", "first", "finally", "step 1", "step 2"],
            true_branch=workflow_action_leaf,
            false_branch=clarification_leaf,
        )

        # Sheet keywords check
        sheet_node = DecisionNode(
            name="contains_sheet_keywords",
            condition_type="keywords",
            condition_data=[
                "sheet", "spreadsheet", "table", "csv", "excel",
                "columns", "rows", "data", "tracker",
                "create a sheet", "make a sheet", "update the sheet",
            ],
            true_branch=sheet_action_leaf,
            false_branch=multi_step_node,
        )

        # Email keywords check
        email_node = DecisionNode(
            name="contains_email_keywords",
            condition_type="keywords",
            condition_data=[
                "email", "draft", "reply", "forward", "send",
                "compose", "inbox", "unread", "search email",
                "mail", "respond", "cc", "bcc",
            ],
            true_branch=email_action_leaf,
            false_branch=sheet_node,
        )

        # Root – greeting check
        root = DecisionNode(
            name="is_conversational_greeting",
            condition_type="keywords",
            condition_data=[
                "hi", "hello", "hey", "yo", "sup", "hiya", "howdy",
                "morning", "afternoon", "evening", "good morning",
                "good afternoon", "good evening", "gm",
                "whats up", "wassup", "how are you",
                "thanks", "thank you", "thx", "bye", "goodbye",
                "cool", "nice", "great", "ok", "okay",
                "got it", "understood", "lol", "haha",
            ],
            true_branch=casual_leaf,
            false_branch=email_node,
        )

        return root

    # ── introspection ────────────────────────────────────────────────────

    @property
    def thresholds(self) -> Dict[str, float]:
        """Return confidence thresholds from config."""
        return self._config.get("thresholds", {
            "auto_route": 0.8,
            "suggest": 0.5,
            "clarify": 0.0,
        })
