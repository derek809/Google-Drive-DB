"""
Tests for Mode 4 Intent Decision Tree.

Verifies that the IntentClassifier correctly routes user inputs to the
expected categories with appropriate confidence and parameter extraction.
"""

import os
import sys
import unittest

# Set up import paths
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _d in ["brain","core","core/Infrastructure","core/InputOutput","core/State&Memory","Bot_actions","LLM"]:
    _p = os.path.join(_root, _d)
    if _p not in sys.path: sys.path.insert(0, _p)

from intent_tree import IntentClassifier, IntentResult, DecisionNode


def _classifier():
    return IntentClassifier()


# -- Greeting / Casual -------------------------------------------------------

class TestCasualClassification(unittest.TestCase):
    def setUp(self):
        self.classifier = _classifier()

    def test_hello(self):
        result = self.classifier.classify("Hello")
        self.assertEqual(result.category, "casual")
        self.assertEqual(result.confidence, 1.0)

    def test_hey(self):
        result = self.classifier.classify("hey")
        self.assertEqual(result.category, "casual")

    def test_hi_there(self):
        result = self.classifier.classify("hi there")
        self.assertEqual(result.category, "casual")

    def test_good_morning(self):
        result = self.classifier.classify("good morning")
        self.assertEqual(result.category, "casual")

    def test_thanks(self):
        result = self.classifier.classify("thanks")
        self.assertEqual(result.category, "casual")

    def test_ok(self):
        result = self.classifier.classify("ok")
        self.assertEqual(result.category, "casual")

    def test_lol(self):
        result = self.classifier.classify("lol")
        self.assertEqual(result.category, "casual")


# -- Email Actions ------------------------------------------------------------

class TestEmailClassification(unittest.TestCase):
    def setUp(self):
        self.classifier = _classifier()

    def test_draft_email(self):
        result = self.classifier.classify("draft email to John about the meeting")
        self.assertEqual(result.category, "email_action")
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_email_with_params(self):
        result = self.classifier.classify("Email John about the meeting")
        self.assertEqual(result.category, "email_action")
        self.assertTrue("recipient" in result.parameters or "topic" in result.parameters)

    def test_forward_email(self):
        result = self.classifier.classify("forward the invoice to accounting")
        self.assertEqual(result.category, "email_action")

    def test_reply_to_email(self):
        result = self.classifier.classify("reply to that email")
        self.assertEqual(result.category, "email_action")

    def test_search_email(self):
        result = self.classifier.classify("search email from Jason")
        self.assertEqual(result.category, "email_action")

    def test_check_inbox(self):
        result = self.classifier.classify("check my inbox")
        self.assertEqual(result.category, "email_action")


# -- Sheet Actions ------------------------------------------------------------

class TestSheetClassification(unittest.TestCase):
    def setUp(self):
        self.classifier = _classifier()

    def test_create_sheet(self):
        result = self.classifier.classify("create a sheet with Q3 data")
        self.assertEqual(result.category, "sheet_action")
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_spreadsheet(self):
        result = self.classifier.classify("make a spreadsheet for the project")
        self.assertEqual(result.category, "sheet_action")

    def test_update_tracker(self):
        result = self.classifier.classify("update the tracker with new numbers")
        self.assertEqual(result.category, "sheet_action")


# -- Workflow Actions ---------------------------------------------------------

class TestWorkflowClassification(unittest.TestCase):
    def setUp(self):
        self.classifier = _classifier()

    def test_multi_step(self):
        result = self.classifier.classify("gather the report then summarize it")
        self.assertEqual(result.category, "workflow_action")
        self.assertGreaterEqual(result.confidence, 0.5)

    def test_then_keyword(self):
        result = self.classifier.classify("create a draft and then send it")
        self.assertIn(result.category, ("workflow_action", "email_action"))

    def test_first_step(self):
        result = self.classifier.classify("first check the status, then notify the team")
        self.assertEqual(result.category, "workflow_action")

    def test_mixed_email_and_step(self):
        result = self.classifier.classify("find the email then create a sheet from it")
        self.assertEqual(result.category, "email_action")


# -- Clarification Needed ----------------------------------------------------

class TestClarificationClassification(unittest.TestCase):
    def setUp(self):
        self.classifier = _classifier()

    def test_do_the_thing(self):
        result = self.classifier.classify("do the thing")
        self.assertEqual(result.category, "clarification_needed")
        self.assertIsNotNone(result.follow_up_question)

    def test_vague_request(self):
        result = self.classifier.classify("handle it please")
        self.assertEqual(result.category, "clarification_needed")

    def test_ambiguous(self):
        result = self.classifier.classify("can you take care of that")
        self.assertEqual(result.category, "clarification_needed")


# -- IntentResult structure ---------------------------------------------------

class TestIntentResult(unittest.TestCase):
    def setUp(self):
        self.classifier = _classifier()

    def test_result_fields(self):
        result = self.classifier.classify("Hello")
        self.assertTrue(hasattr(result, "category"))
        self.assertTrue(hasattr(result, "confidence"))
        self.assertTrue(hasattr(result, "parameters"))
        self.assertTrue(hasattr(result, "follow_up_question"))

    def test_result_is_namedtuple(self):
        result = self.classifier.classify("Hello")
        self.assertIsInstance(result, IntentResult)

    def test_parameters_is_dict(self):
        result = self.classifier.classify("draft email to John")
        self.assertIsInstance(result.parameters, dict)


# -- DecisionNode -------------------------------------------------------------

class TestDecisionNode(unittest.TestCase):
    def test_from_dict(self):
        data = {
            "name": "test",
            "condition_type": "keywords",
            "condition_data": ["hello"],
            "true_branch": {"name": "leaf", "action": "casual", "confidence": 1.0},
            "false_branch": {"name": "other", "action": "unclear", "confidence": 0.0},
        }
        node = DecisionNode.from_dict(data)
        self.assertEqual(node.name, "test")
        self.assertEqual(node.true_branch.action, "casual")
        self.assertEqual(node.false_branch.action, "unclear")

    def test_evaluate_keywords(self):
        node = DecisionNode(
            condition_type="keywords",
            condition_data=["hello", "hi"],
        )
        self.assertTrue(node.evaluate("hello there", {}))
        self.assertFalse(node.evaluate("goodbye", {}))

    def test_evaluate_regex(self):
        node = DecisionNode(
            condition_type="regex",
            condition_data=[r"email\s+\w+\s+about"],
        )
        self.assertTrue(node.evaluate("email John about meeting", {}))
        self.assertFalse(node.evaluate("hello there", {}))

    def test_extract_params(self):
        node = DecisionNode(
            extract_params=[
                {"pattern": r"(?:to|for)\s+(\w+)", "param": "recipient"},
            ],
        )
        params = node.extract("email to John")
        self.assertEqual(params.get("recipient"), "John")


# -- Config loading -----------------------------------------------------------

class TestConfigLoading(unittest.TestCase):
    def test_default_tree_works_without_config(self):
        classifier = IntentClassifier(config_path="/tmp/nonexistent_intent_tree.json")
        result = classifier.classify("Hello")
        self.assertEqual(result.category, "casual")

    def test_thresholds(self):
        classifier = _classifier()
        thresholds = classifier.thresholds
        self.assertIn("auto_route", thresholds)
        self.assertIn("suggest", thresholds)
        self.assertIn("clarify", thresholds)


# -- Edge cases ---------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.classifier = _classifier()

    def test_empty_string(self):
        result = self.classifier.classify("")
        self.assertIsNotNone(result.category)

    def test_very_long_input(self):
        result = self.classifier.classify("hello " * 1000)
        self.assertIsNotNone(result.category)

    def test_special_characters(self):
        result = self.classifier.classify("email!!! @#$ John??")
        self.assertIsNotNone(result.category)

    def test_none_context(self):
        result = self.classifier.classify("Hello", context=None)
        self.assertEqual(result.category, "casual")


if __name__ == "__main__":
    unittest.main()
