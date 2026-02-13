#!/usr/bin/env python3
"""
Test natural conversation flow for Mode 4.
Simulates real user messages to ensure the bot feels human.
"""

import sys
import os
import unittest
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _d in ["brain","core","core/Infrastructure","core/InputOutput","core/State&Memory","Bot_actions","LLM"]:
    _p = os.path.join(_root, _d)
    if _p not in sys.path: sys.path.insert(0, _p)

try:
    from telegram_handler import TelegramHandler
    from mode4_processor import Mode4Processor
    _DEPS_AVAILABLE = True
    _DEPS_ERROR = ""
except ImportError as _e:
    _DEPS_AVAILABLE = False
    _DEPS_ERROR = str(_e)


@unittest.skipUnless(_DEPS_AVAILABLE, f"Missing dependency: {_DEPS_ERROR}")
class TestNaturalConversation(unittest.TestCase):
    """Test parsing of natural human messages."""

    @classmethod
    def setUpClass(cls):
        cls.processor = Mode4Processor()
        cls.telegram = cls.processor.telegram

    def _parse(self, msg):
        parsed = self.telegram.parse_message(msg)
        self.assertIsInstance(parsed, dict)
        return parsed

    def test_greeting(self):
        parsed = self._parse("Hello")
        self.assertTrue(parsed.get('valid'))

    def test_draft_email(self):
        parsed = self._parse("Draft an email to Jason")
        self.assertTrue(parsed.get('valid'))

    def test_todo(self):
        parsed = self._parse("Add sending 1099 to todo list")
        self.assertTrue(parsed.get('valid'))

    def test_legacy_format(self):
        parsed = self._parse("Re: W9 Request - send W9 and wiring")
        self.assertTrue(parsed.get('valid'))
        self.assertEqual(parsed.get('search_type'), 'subject')

    def test_forward(self):
        parsed = self._parse("Forward the invoice to accounting")
        self.assertTrue(parsed.get('valid'))

    def test_help_command(self):
        parsed = self._parse("/help")
        self.assertTrue(parsed.get('valid'))
        self.assertEqual(parsed.get('command'), '/help')

    def test_status_command(self):
        parsed = self._parse("/status")
        self.assertTrue(parsed.get('valid'))
        self.assertEqual(parsed.get('command'), '/status')


if __name__ == "__main__":
    unittest.main()
