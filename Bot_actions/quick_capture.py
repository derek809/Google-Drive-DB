"""
Quick Capture Capability for Mode 4
Natural language task parsing via Ollama.

Converts shorthand like "jason invoice friday" into structured tasks.

Commands:
    /quick <text> - Quick capture with NL parsing
    /q <text> - Shorthand alias

Usage:
    from quick_capture import QuickCapture

    capture = QuickCapture()
    result = capture.parse("jason invoice friday high priority")
    # Returns: {'title': 'Send invoice to Jason', 'deadline': friday, 'priority': 'high'}
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class QuickCaptureError(Exception):
    """Custom exception for quick capture errors."""
    pass


class QuickCapture:
    """
    Natural language task parsing for quick capture.

    Uses Ollama to understand context and extract structured task data.
    Falls back to rule-based parsing if Ollama unavailable.
    """

    def __init__(self):
        """Initialize quick capture."""
        self._ollama = None
        self._todo = None

        # Common patterns for rule-based fallback
        self.patterns = {
            'invoice': ['send invoice to', 'invoice for'],
            'call': ['call', 'phone'],
            'email': ['email', 'send email to', 'reply to'],
            'meeting': ['meeting with', 'meet with', 'schedule meeting'],
            'review': ['review', 'check', 'look at'],
            'send': ['send', 'deliver', 'share'],
            'follow up': ['follow up with', 'followup', 'check in with'],
        }

        # Priority keywords
        self.priority_keywords = {
            'high': ['urgent', 'asap', 'important', 'high', 'critical', '!', 'priority'],
            'low': ['low', 'whenever', 'eventually', 'not urgent'],
        }

        # Day keywords
        self.day_keywords = {
            'today': ['today', 'now', 'asap'],
            'tomorrow': ['tomorrow', 'tmrw'],
            'monday': ['monday', 'mon'],
            'tuesday': ['tuesday', 'tue', 'tues'],
            'wednesday': ['wednesday', 'wed'],
            'thursday': ['thursday', 'thu', 'thurs'],
            'friday': ['friday', 'fri'],
            'saturday': ['saturday', 'sat'],
            'sunday': ['sunday', 'sun'],
            'next week': ['next week', 'nextweek'],
        }

    def _get_ollama(self):
        """Lazy load Ollama client."""
        if self._ollama is None:
            try:
                from ollama_client import OllamaClient
                self._ollama = OllamaClient()
            except Exception as e:
                logger.warning(f"Could not load Ollama: {e}")
        return self._ollama

    def _get_todo(self):
        """Lazy load todo manager."""
        if self._todo is None:
            from todo_manager import TodoManager
            self._todo = TodoManager()
        return self._todo

    # ==================
    # PARSING
    # ==================

    def parse(self, text: str, use_llm: bool = True) -> Dict[str, Any]:
        """
        Parse natural language into structured task.

        Args:
            text: Natural language input
            use_llm: Whether to use Ollama for parsing

        Returns:
            Dict with title, priority, deadline, notes
        """
        text = text.strip()
        if not text:
            return {'error': 'Empty input'}

        # Try LLM parsing first
        if use_llm:
            ollama = self._get_ollama()
            if ollama and ollama.is_available():
                try:
                    result = self._parse_with_llm(text)
                    if result.get('title'):
                        return result
                except Exception as e:
                    logger.warning(f"LLM parsing failed: {e}")

        # Fall back to rule-based parsing
        return self._parse_rules(text)

    def _parse_with_llm(self, text: str) -> Dict[str, Any]:
        """Parse using Ollama LLM."""
        ollama = self._get_ollama()

        prompt = f"""Parse this quick note into a structured task.
Input: "{text}"

Extract:
1. Task title (clear, actionable description)
2. Priority (high/medium/low based on urgency keywords)
3. Deadline (if mentioned - today, tomorrow, day name, or date)
4. Person (if mentioned)

Respond in this exact format:
TITLE: <clear task title>
PRIORITY: <high|medium|low>
DEADLINE: <none|today|tomorrow|monday|tuesday|...|YYYY-MM-DD>
PERSON: <name or none>

Examples:
Input: "jason invoice friday"
TITLE: Send invoice to Jason
PRIORITY: medium
DEADLINE: friday
PERSON: Jason

Input: "call mom urgent"
TITLE: Call Mom
PRIORITY: high
DEADLINE: none
PERSON: Mom

Now parse: "{text}"
"""

        response = ollama.generate(prompt)
        return self._parse_llm_response(response)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured dict."""
        result = {
            'title': '',
            'priority': 'medium',
            'deadline': None,
            'person': None
        }

        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('TITLE:'):
                result['title'] = line[6:].strip()
            elif line.startswith('PRIORITY:'):
                p = line[9:].strip().lower()
                if p in ('high', 'medium', 'low'):
                    result['priority'] = p
            elif line.startswith('DEADLINE:'):
                d = line[9:].strip().lower()
                if d and d != 'none':
                    result['deadline'] = self._parse_deadline(d)
            elif line.startswith('PERSON:'):
                p = line[7:].strip()
                if p.lower() != 'none':
                    result['person'] = p

        return result

    def _parse_rules(self, text: str) -> Dict[str, Any]:
        """Rule-based parsing fallback."""
        text_lower = text.lower()
        words = text_lower.split()

        result = {
            'title': '',
            'priority': 'medium',
            'deadline': None,
            'person': None,
            'raw': text
        }

        # Extract priority
        for priority, keywords in self.priority_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    result['priority'] = priority
                    text_lower = text_lower.replace(kw, '').strip()
                    break

        # Extract deadline
        for day, keywords in self.day_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    result['deadline'] = self._parse_deadline(day)
                    text_lower = text_lower.replace(kw, '').strip()
                    break
            if result['deadline']:
                break

        # Find action type and construct title
        action = None
        for action_type, keywords in self.patterns.items():
            for kw in keywords:
                if kw in text_lower:
                    action = action_type
                    break
            if action:
                break

        # Extract person (capitalized word or word before action)
        words_clean = [w for w in text.split() if w.lower() not in
                       sum(self.priority_keywords.values(), []) +
                       sum(self.day_keywords.values(), [])]

        person = None
        for word in words_clean:
            if word[0].isupper() and len(word) > 1:
                person = word
                result['person'] = person
                break

        # Construct title
        if action and person:
            if action == 'invoice':
                result['title'] = f"Send invoice to {person}"
            elif action == 'call':
                result['title'] = f"Call {person}"
            elif action == 'email':
                result['title'] = f"Send email to {person}"
            elif action == 'meeting':
                result['title'] = f"Schedule meeting with {person}"
            elif action == 'follow up':
                result['title'] = f"Follow up with {person}"
            else:
                result['title'] = f"{action.title()} {person}"
        elif action:
            result['title'] = f"{action.title()}: {' '.join(words_clean)}"
        else:
            # Just use cleaned text as title
            result['title'] = ' '.join(words_clean).strip().title()

        if not result['title']:
            result['title'] = text.strip().title()

        return result

    def _parse_deadline(self, text: str) -> Optional[datetime]:
        """Parse deadline string to datetime."""
        text = text.lower().strip()
        today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)

        mapping = {
            'today': today,
            'tomorrow': today + timedelta(days=1),
            'monday': self._next_weekday(today, 0),
            'tuesday': self._next_weekday(today, 1),
            'wednesday': self._next_weekday(today, 2),
            'thursday': self._next_weekday(today, 3),
            'friday': self._next_weekday(today, 4),
            'saturday': self._next_weekday(today, 5),
            'sunday': self._next_weekday(today, 6),
            'next week': today + timedelta(days=7),
        }

        if text in mapping:
            return mapping[text]

        # Try parsing as date
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m/%d']:
            try:
                parsed = datetime.strptime(text, fmt)
                if fmt == '%m/%d':
                    parsed = parsed.replace(year=today.year)
                return parsed
            except ValueError:
                continue

        return None

    def _next_weekday(self, start: datetime, weekday: int) -> datetime:
        """Get next occurrence of weekday."""
        days_ahead = weekday - start.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return start + timedelta(days=days_ahead)

    # ==================
    # COMMAND HANDLER
    # ==================

    def handle_command(self, command: str, args: str, user_id: int) -> str:
        """
        Handle quick capture command.

        Args:
            command: /quick or /q
            args: Natural language text
            user_id: Telegram user ID

        Returns:
            Response message
        """
        if not args.strip():
            return (
                "Quick Capture - Natural language task entry\n\n"
                "Usage: /q <text>\n"
                "Examples:\n"
                "  /q jason invoice friday\n"
                "  /q call mom urgent\n"
                "  /q review contract tomorrow high priority\n"
            )

        # Parse the input
        result = self.parse(args)

        if result.get('error'):
            return f"Could not parse: {result['error']}"

        # Create the task
        todo = self._get_todo()
        task_id = todo.add_task(
            title=result['title'],
            priority=result.get('priority', 'medium'),
            deadline=result.get('deadline')
        )

        # Format response
        response = f"Task #{task_id} created:\n{result['title']}"
        if result.get('priority') != 'medium':
            response += f"\nPriority: {result['priority']}"
        if result.get('deadline'):
            response += f"\nDeadline: {result['deadline'].strftime('%A, %b %d')}"
        if result.get('person'):
            response += f"\nPerson: {result['person']}"

        return response

    def cleanup(self):
        """Cleanup resources."""
        if self._ollama:
            del self._ollama
            self._ollama = None
        if self._todo:
            self._todo.cleanup()
            self._todo = None


# ==================
# TESTING
# ==================

def test_quick_capture():
    """Test quick capture parsing."""
    print("Testing Quick Capture...")
    print("=" * 60)

    capture = QuickCapture()

    test_inputs = [
        "jason invoice friday",
        "call mom urgent",
        "review contract tomorrow",
        "email Sarah about meeting",
        "send w9 to accountant asap",
        "follow up with client next week",
        "meeting with team monday high priority",
    ]

    for text in test_inputs:
        print(f"\nInput: '{text}'")
        result = capture.parse(text, use_llm=False)  # Use rules for testing
        print(f"  Title: {result.get('title')}")
        print(f"  Priority: {result.get('priority')}")
        print(f"  Deadline: {result.get('deadline')}")
        print(f"  Person: {result.get('person')}")

    capture.cleanup()
    print("\nQuick capture test complete!")


if __name__ == "__main__":
    test_quick_capture()
