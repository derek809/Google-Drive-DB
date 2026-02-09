"""
Tests for Mode 4 Intent Decision Tree.

Verifies that the IntentClassifier correctly routes user inputs to the
expected categories with appropriate confidence and parameter extraction.
"""

import os
import sys
import json
import pytest

# Ensure mode4/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.intent_tree import IntentClassifier, IntentResult, DecisionNode


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def classifier():
    """Return an IntentClassifier using the default config or fallback tree."""
    return IntentClassifier()


# ── Greeting / Casual ────────────────────────────────────────────────────────

class TestCasualClassification:
    def test_hello(self, classifier):
        result = classifier.classify("Hello")
        assert result.category == "casual"
        assert result.confidence == 1.0

    def test_hey(self, classifier):
        result = classifier.classify("hey")
        assert result.category == "casual"

    def test_hi_there(self, classifier):
        result = classifier.classify("hi there")
        assert result.category == "casual"

    def test_good_morning(self, classifier):
        result = classifier.classify("good morning")
        assert result.category == "casual"

    def test_thanks(self, classifier):
        result = classifier.classify("thanks")
        assert result.category == "casual"

    def test_ok(self, classifier):
        result = classifier.classify("ok")
        assert result.category == "casual"

    def test_lol(self, classifier):
        result = classifier.classify("lol")
        assert result.category == "casual"


# ── Email Actions ────────────────────────────────────────────────────────────

class TestEmailClassification:
    def test_draft_email(self, classifier):
        result = classifier.classify("draft email to John about the meeting")
        assert result.category == "email_action"
        assert result.confidence >= 0.8

    def test_email_with_params(self, classifier):
        result = classifier.classify("Email John about the meeting")
        assert result.category == "email_action"
        # Check parameter extraction
        assert "recipient" in result.parameters or "topic" in result.parameters

    def test_forward_email(self, classifier):
        result = classifier.classify("forward the invoice to accounting")
        assert result.category == "email_action"

    def test_reply_to_email(self, classifier):
        result = classifier.classify("reply to that email")
        assert result.category == "email_action"

    def test_search_email(self, classifier):
        result = classifier.classify("search email from Jason")
        assert result.category == "email_action"

    def test_check_inbox(self, classifier):
        result = classifier.classify("check my inbox")
        assert result.category == "email_action"


# ── Sheet Actions ────────────────────────────────────────────────────────────

class TestSheetClassification:
    def test_create_sheet(self, classifier):
        result = classifier.classify("create a sheet with Q3 data")
        assert result.category == "sheet_action"
        assert result.confidence >= 0.8

    def test_spreadsheet(self, classifier):
        result = classifier.classify("make a spreadsheet for the project")
        assert result.category == "sheet_action"

    def test_update_tracker(self, classifier):
        result = classifier.classify("update the tracker with new numbers")
        assert result.category == "sheet_action"


# ── Workflow Actions ─────────────────────────────────────────────────────────

class TestWorkflowClassification:
    def test_multi_step(self, classifier):
        # Use input without email/sheet keywords so it falls through to multi-step check
        result = classifier.classify("gather the report then summarize it")
        assert result.category == "workflow_action"
        assert result.confidence >= 0.5

    def test_then_keyword(self, classifier):
        result = classifier.classify("create a draft and then send it")
        # "draft" and "send" are email keywords; tree checks email before multi-step
        assert result.category in ("workflow_action", "email_action")

    def test_first_step(self, classifier):
        # Use input without email/sheet keywords so multi-step indicators match
        result = classifier.classify("first check the status, then notify the team")
        assert result.category == "workflow_action"

    def test_mixed_email_and_step(self, classifier):
        # When input has both email keywords and multi-step indicators,
        # tree correctly prioritizes the specific action (email)
        result = classifier.classify("find the email then create a sheet from it")
        assert result.category == "email_action"


# ── Clarification Needed ────────────────────────────────────────────────────

class TestClarificationClassification:
    def test_do_the_thing(self, classifier):
        result = classifier.classify("do the thing")
        assert result.category == "clarification_needed"
        assert result.follow_up_question is not None

    def test_vague_request(self, classifier):
        result = classifier.classify("handle it please")
        assert result.category == "clarification_needed"

    def test_ambiguous(self, classifier):
        result = classifier.classify("can you take care of that")
        assert result.category == "clarification_needed"


# ── IntentResult structure ───────────────────────────────────────────────────

class TestIntentResult:
    def test_result_fields(self, classifier):
        result = classifier.classify("Hello")
        assert hasattr(result, "category")
        assert hasattr(result, "confidence")
        assert hasattr(result, "parameters")
        assert hasattr(result, "follow_up_question")

    def test_result_is_namedtuple(self, classifier):
        result = classifier.classify("Hello")
        assert isinstance(result, IntentResult)

    def test_parameters_is_dict(self, classifier):
        result = classifier.classify("draft email to John")
        assert isinstance(result.parameters, dict)


# ── DecisionNode ─────────────────────────────────────────────────────────────

class TestDecisionNode:
    def test_from_dict(self):
        data = {
            "name": "test",
            "condition_type": "keywords",
            "condition_data": ["hello"],
            "true_branch": {"name": "leaf", "action": "casual", "confidence": 1.0},
            "false_branch": {"name": "other", "action": "unclear", "confidence": 0.0},
        }
        node = DecisionNode.from_dict(data)
        assert node.name == "test"
        assert node.true_branch.action == "casual"
        assert node.false_branch.action == "unclear"

    def test_evaluate_keywords(self):
        node = DecisionNode(
            condition_type="keywords",
            condition_data=["hello", "hi"],
        )
        assert node.evaluate("hello there", {}) is True
        assert node.evaluate("goodbye", {}) is False

    def test_evaluate_regex(self):
        node = DecisionNode(
            condition_type="regex",
            condition_data=[r"email\s+\w+\s+about"],
        )
        assert node.evaluate("email John about meeting", {}) is True
        assert node.evaluate("hello there", {}) is False

    def test_extract_params(self):
        node = DecisionNode(
            extract_params=[
                {"pattern": r"(?:to|for)\s+(\w+)", "param": "recipient"},
            ],
        )
        params = node.extract("email to John")
        assert params.get("recipient") == "John"


# ── Config loading ───────────────────────────────────────────────────────────

class TestConfigLoading:
    def test_default_tree_works_without_config(self):
        # Use a non-existent config path to force fallback
        classifier = IntentClassifier(config_path="/tmp/nonexistent_intent_tree.json")
        result = classifier.classify("Hello")
        assert result.category == "casual"

    def test_thresholds(self, classifier):
        thresholds = classifier.thresholds
        assert "auto_route" in thresholds
        assert "suggest" in thresholds
        assert "clarify" in thresholds


# ── Edge cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string(self, classifier):
        result = classifier.classify("")
        # Should not crash
        assert result.category is not None

    def test_very_long_input(self, classifier):
        result = classifier.classify("hello " * 1000)
        assert result.category is not None

    def test_special_characters(self, classifier):
        result = classifier.classify("email!!! @#$ John??")
        assert result.category is not None

    def test_none_context(self, classifier):
        result = classifier.classify("Hello", context=None)
        assert result.category == "casual"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
