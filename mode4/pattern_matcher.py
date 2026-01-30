"""
Pattern Matcher for Mode 4
Reads patterns, templates, and contacts from Google Sheets (not SQLite).

This module provides pattern matching and confidence scoring adapted from
the work laptop's orchestrator.py, but designed to read from Sheets.

Usage:
    from pattern_matcher import PatternMatcher

    # Initialize with Sheets client
    matcher = PatternMatcher(sheets_client, spreadsheet_id)

    # Load data from Sheets
    matcher.load_data()

    # Match patterns
    result = matcher.match_pattern(email_subject, email_body)

    # Calculate confidence
    confidence, reasoning = matcher.calculate_confidence(email_data, pattern_result, sender_known)
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple

# Import Sheets client
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from sheets_client import GoogleSheetsClient, SheetsClientError
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False


class PatternMatcherError(Exception):
    """Custom exception for pattern matcher errors."""
    pass


class PatternMatcher:
    """
    Pattern matching and confidence scoring for Mode 4.

    Reads patterns, templates, and contacts from Google Sheets and provides
    matching functionality similar to the work laptop's orchestrator.
    """

    def __init__(
        self,
        sheets_client: 'GoogleSheetsClient' = None,
        spreadsheet_id: str = None
    ):
        """
        Initialize pattern matcher.

        Args:
            sheets_client: GoogleSheetsClient instance (optional, will create if not provided)
            spreadsheet_id: Google Sheet ID (optional, loads from config if not provided)
        """
        self.sheets_client = sheets_client
        self._owns_client = False

        # Try to get spreadsheet ID from config
        try:
            from m1_config import SPREADSHEET_ID, SHEETS_CREDENTIALS_PATH
            from m1_config import PATTERNS_SHEET, TEMPLATES_SHEET, CONTACTS_SHEET
            self.spreadsheet_id = spreadsheet_id or SPREADSHEET_ID
            self.credentials_path = SHEETS_CREDENTIALS_PATH
            self.patterns_sheet = PATTERNS_SHEET
            self.templates_sheet = TEMPLATES_SHEET
            self.contacts_sheet = CONTACTS_SHEET
        except ImportError:
            self.spreadsheet_id = spreadsheet_id
            self.credentials_path = None
            self.patterns_sheet = "Patterns"
            self.templates_sheet = "Templates"
            self.contacts_sheet = "Contacts"

        # Cached data from Sheets
        self.patterns: List[Dict] = []
        self.templates: Dict[str, Dict] = {}
        self.contacts: Dict[str, Dict] = {}  # Keyed by email

    def _ensure_client(self):
        """Ensure Sheets client is connected."""
        if self.sheets_client is None:
            if not SHEETS_AVAILABLE:
                raise PatternMatcherError(
                    "Google Sheets client not available. "
                    "Install: pip install google-auth google-api-python-client"
                )

            self.sheets_client = GoogleSheetsClient(self.credentials_path)
            self.sheets_client.connect()
            self._owns_client = True

    def close(self):
        """Close the Sheets client if we own it."""
        if self._owns_client and self.sheets_client:
            self.sheets_client.close()

    def __enter__(self):
        """Context manager entry."""
        self._ensure_client()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # ==================
    # DATA LOADING
    # ==================

    def load_data(self):
        """Load patterns, templates, and contacts from Google Sheets."""
        self._ensure_client()

        self.load_patterns()
        self.load_templates()
        self.load_contacts()

    def load_patterns(self) -> List[Dict]:
        """Load patterns from Sheets."""
        self._ensure_client()

        result = self.sheets_client.read_range(
            self.spreadsheet_id,
            f"{self.patterns_sheet}!A:F"
        )

        if not result.get('success'):
            raise PatternMatcherError(f"Failed to load patterns: {result.get('error')}")

        values = result.get('values', [])
        if len(values) < 2:
            self.patterns = []
            return self.patterns

        # First row is header
        headers = [h.lower().replace(' ', '_') for h in values[0]]

        self.patterns = []
        for row in values[1:]:
            if not row or not row[0]:
                continue

            pattern = {}
            for i, header in enumerate(headers):
                pattern[header] = row[i] if i < len(row) else ""

            self.patterns.append(pattern)

        return self.patterns

    def load_templates(self) -> Dict[str, Dict]:
        """Load templates from Sheets."""
        self._ensure_client()

        result = self.sheets_client.read_range(
            self.spreadsheet_id,
            f"{self.templates_sheet}!A:F"
        )

        if not result.get('success'):
            raise PatternMatcherError(f"Failed to load templates: {result.get('error')}")

        values = result.get('values', [])
        if len(values) < 2:
            self.templates = {}
            return self.templates

        headers = [h.lower().replace(' ', '_') for h in values[0]]

        self.templates = {}
        for row in values[1:]:
            if not row or not row[0]:
                continue

            template = {}
            for i, header in enumerate(headers):
                template[header] = row[i] if i < len(row) else ""

            template_id = template.get('template_id', '')
            if template_id:
                self.templates[template_id] = template

        return self.templates

    def load_contacts(self) -> Dict[str, Dict]:
        """Load contacts from Sheets."""
        self._ensure_client()

        result = self.sheets_client.read_range(
            self.spreadsheet_id,
            f"{self.contacts_sheet}!A:G"
        )

        if not result.get('success'):
            raise PatternMatcherError(f"Failed to load contacts: {result.get('error')}")

        values = result.get('values', [])
        if len(values) < 2:
            self.contacts = {}
            return self.contacts

        headers = [h.lower().replace(' ', '_') for h in values[0]]

        self.contacts = {}
        for row in values[1:]:
            if not row or not row[0]:
                continue

            contact = {}
            for i, header in enumerate(headers):
                contact[header] = row[i] if i < len(row) else ""

            email = contact.get('email', '').lower()
            if email:
                self.contacts[email] = contact

        return self.contacts

    # ==================
    # PATTERN MATCHING
    # ==================

    def match_pattern(
        self,
        email_content: str,
        subject: str = ""
    ) -> Optional[Dict]:
        """
        Match email content against known patterns.

        Args:
            email_content: Email body text
            subject: Email subject line

        Returns:
            Dict with pattern info if match found, None otherwise
        """
        if not self.patterns:
            self.load_patterns()

        content_lower = email_content.lower()
        subject_lower = subject.lower()
        combined_text = f"{subject_lower} {content_lower}"

        best_match = None
        best_score = 0

        for pattern in self.patterns:
            pattern_name = pattern.get('pattern_name', '')
            keywords_str = pattern.get('keywords', '')
            confidence_boost = pattern.get('confidence_boost', 0)

            # Parse keywords (comma-separated)
            if isinstance(keywords_str, str):
                keywords = [k.strip().lower() for k in keywords_str.split(',') if k.strip()]
            else:
                keywords = []

            # Count matches
            matched_keywords = [kw for kw in keywords if kw in combined_text]
            matches = len(matched_keywords)

            if matches > best_score:
                best_score = matches
                best_match = {
                    'pattern_name': pattern_name,
                    'confidence_boost': int(confidence_boost) if confidence_boost else 0,
                    'keyword_matches': matches,
                    'matched_keywords': matched_keywords,
                    'notes': pattern.get('notes', '')
                }

        return best_match

    # ==================
    # CONFIDENCE SCORING
    # ==================

    def calculate_confidence(
        self,
        email_data: Dict,
        pattern_match: Optional[Dict],
        sender_known: bool
    ) -> Tuple[int, List[str]]:
        """
        Calculate confidence score for processing this email.

        Args:
            email_data: Dict with subject, body, sender_email
            pattern_match: Result from match_pattern()
            sender_known: Whether sender is in contacts

        Returns:
            Tuple of (score, reasoning_list)
        """
        score = 50  # Base confidence
        reasoning = ["Base confidence: 50"]

        # Pattern match bonus
        if pattern_match:
            boost = pattern_match.get('confidence_boost', 0)
            score += boost
            reasoning.append(f"Pattern '{pattern_match['pattern_name']}' matched: +{boost}")

            # Extra boost for multiple keyword matches
            keyword_count = pattern_match.get('keyword_matches', 0)
            if keyword_count > 1:
                extra = min(keyword_count * 2, 10)
                score += extra
                reasoning.append(f"Multiple keywords ({keyword_count}): +{extra}")

        # Known sender bonus
        if sender_known:
            score += 10
            reasoning.append("Known sender: +10")
        else:
            score -= 20
            reasoning.append("Unknown sender: -20")

        # Check for compliance keywords (penalties)
        content_lower = email_data.get('body', '').lower()
        subject_lower = email_data.get('subject', '').lower()
        combined = f"{subject_lower} {content_lower}"

        compliance_keywords = [
            'finra audit', 'sec', 'compliance violation', 'regulatory',
            'subpoena', 'legal action', 'investigation'
        ]
        for keyword in compliance_keywords:
            if keyword in combined:
                score -= 30
                reasoning.append(f"Compliance keyword '{keyword}': -30")
                break

        # Clamp score to 0-100 range
        score = max(0, min(100, score))

        return score, reasoning

    # ==================
    # INTENT PARSING
    # ==================

    def parse_intent(self, mcp_prompt: str, email_content: str = "") -> str:
        """
        Determine intent from user's instruction.

        Args:
            mcp_prompt: User's instruction (e.g., "send W9 and wiring")
            email_content: Optional email body for context

        Returns:
            Intent type: 'extract', 'execute', 'modify', 'delegate', or 'unclear'
        """
        prompt_lower = mcp_prompt.lower()

        # EXTRACTION: Just give me information
        extraction_keywords = ['tell me', 'what is', 'find', 'show me', 'list', 'extract', 'summarize']
        if any(kw in prompt_lower for kw in extraction_keywords):
            return 'extract'

        # EXECUTION: Do something (draft, send, generate)
        execution_keywords = ['generate', 'create', 'send', 'make', 'draft', 'reply', 'respond', 'confirm']
        if any(kw in prompt_lower for kw in execution_keywords):
            return 'execute'

        # MODIFICATION: Edit existing content
        modification_keywords = ['update', 'edit', 'change', 'fix', 'remove', 'correct', 'revise']
        if any(kw in prompt_lower for kw in modification_keywords):
            return 'modify'

        # DELEGATION: Pass to someone else
        delegation_keywords = ['loop in', 'ask', 'forward to', 'delegate', 'cc', 'involve']
        if any(kw in prompt_lower for kw in delegation_keywords):
            return 'delegate'

        # Default: Unclear intent (but likely wants a draft response)
        return 'unclear'

    # ==================
    # HELPER METHODS
    # ==================

    def is_known_sender(self, email_address: str) -> bool:
        """Check if sender is in contacts."""
        if not self.contacts:
            self.load_contacts()

        return email_address.lower() in self.contacts

    def get_contact_info(self, email_address: str) -> Optional[Dict]:
        """Get contact information if available."""
        if not self.contacts:
            self.load_contacts()

        return self.contacts.get(email_address.lower())

    def get_template(self, template_id: str) -> Optional[Dict]:
        """Get template by ID."""
        if not self.templates:
            self.load_templates()

        return self.templates.get(template_id)

    def get_template_for_pattern(self, pattern_name: str) -> Optional[Dict]:
        """Get template associated with a pattern name."""
        # Common pattern-to-template mappings
        mapping = {
            'w9_wiring_request': 'w9_response',
            'payment_confirmation': 'payment_confirmation',
            'delegation_eytan': 'delegation_eytan',
            'turnaround_expectation': 'turnaround_time'
        }

        template_id = mapping.get(pattern_name)
        if template_id:
            return self.get_template(template_id)

        return None


# ==================
# TESTING
# ==================

def test_pattern_matcher():
    """Test the pattern matcher."""
    print("Testing Pattern Matcher...")
    print("=" * 60)

    if not SHEETS_AVAILABLE:
        print("ERROR: Google Sheets client not available.")
        print("Install: pip install google-auth google-api-python-client")
        return

    try:
        from m1_config import SPREADSHEET_ID
        if SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
            print("ERROR: SPREADSHEET_ID not configured in m1_config.py")
            return
    except ImportError:
        print("ERROR: m1_config.py not found. Configure it first.")
        return

    try:
        with PatternMatcher() as matcher:
            # Load data
            print("Loading data from Sheets...")
            matcher.load_data()

            print(f"  Loaded {len(matcher.patterns)} patterns")
            print(f"  Loaded {len(matcher.templates)} templates")
            print(f"  Loaded {len(matcher.contacts)} contacts")
            print()

            # Test pattern matching
            print("Testing pattern matching...")
            test_subject = "W9 Request"
            test_body = "Hi Derek, can you send your W9 and wiring instructions?"

            result = matcher.match_pattern(test_body, test_subject)
            if result:
                print(f"  Matched: {result['pattern_name']}")
                print(f"  Boost: +{result['confidence_boost']}")
                print(f"  Keywords: {result['matched_keywords']}")
            else:
                print("  No pattern matched")
            print()

            # Test confidence
            print("Testing confidence scoring...")
            email_data = {
                'subject': test_subject,
                'body': test_body,
                'sender_email': 'unknown@example.com'
            }

            confidence, reasoning = matcher.calculate_confidence(
                email_data, result, sender_known=False
            )
            print(f"  Confidence: {confidence}%")
            print("  Reasoning:")
            for r in reasoning:
                print(f"    - {r}")
            print()

            # Test intent parsing
            print("Testing intent parsing...")
            intents = [
                "send W9 and wiring",
                "tell me what this is about",
                "loop in Eytan",
                "update the numbers"
            ]
            for prompt in intents:
                intent = matcher.parse_intent(prompt)
                print(f"  '{prompt}' -> {intent}")

            print()
            print("Pattern matcher test complete!")

    except PatternMatcherError as e:
        print(f"ERROR: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    test_pattern_matcher()
