"""
Smart Parser - Natural Language Message Parser for Mode 4
Uses Local LLM (Qwen2.5) with Regex Fallbacks
"""

import re
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama not available - SmartParser will use regex-only mode")


class SmartParserError(Exception):
    """Exception raised when SmartParser encounters an error."""
    pass


class SmartParser:
    """
    Hybrid parser using Local LLM (Qwen2.5) and Regex Fallbacks.

    This parser attempts to use a local LLM for intelligent parsing,
    but gracefully falls back to regex patterns if LLM is unavailable.
    """

    def __init__(self, model: str = "qwen2.5:3b"):
        """
        Initialize SmartParser.

        Args:
            model: Ollama model name to use for parsing (default: qwen2.5:3b)
        """
        self.model = model
        self.available = OLLAMA_AVAILABLE and self._check_model()

        if self.available:
            logger.info(f"SmartParser initialized with LLM model: {self.model}")
        else:
            logger.info("SmartParser initialized in regex-only mode")

    def _check_model(self) -> bool:
        """
        Check if the configured Ollama model is available.

        Handles both response formats:
        - Object with .models attribute (ollama >= 0.2)
        - Dict with 'models' key (ollama < 0.2 or some versions)

        If the model is missing, logs a warning suggesting to pull it.
        """
        try:
            result = ollama.list()
            model_names = []

            # Handle object-style response (ListResponse with .models)
            if hasattr(result, 'models'):
                try:
                    model_names = [m.model for m in result.models]
                except (AttributeError, TypeError):
                    # .models might be a list of dicts in some versions
                    model_names = [
                        m.get('name', '') if isinstance(m, dict) else str(m)
                        for m in result.models
                    ]

            # Handle dict-style response
            elif isinstance(result, dict) and 'models' in result:
                for m in result['models']:
                    if isinstance(m, dict):
                        model_names.append(m.get('name', m.get('model', '')))
                    else:
                        model_names.append(str(m))

            found = any(self.model in name for name in model_names)
            if not found and model_names:
                logger.warning(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Available: {model_names[:5]}. "
                    f"Run: ollama pull {self.model}"
                )
            elif not model_names:
                logger.warning("No Ollama models found. SmartParser will use regex fallback.")

            return found
        except Exception as e:
            logger.warning(f"Could not check Ollama models: {e}. SmartParser will use regex fallback.")
            return False

    def parse_with_llm(self, text: str) -> Optional[Dict]:
        """
        Layer 1: Few-Shot LLM Extraction

        Uses local LLM to intelligently parse the message.
        Returns None if LLM is unavailable or parsing fails.
        """
        if not self.available:
            return None

        prompt = f"""Extract email reference and instruction as JSON.
Examples:
Msg: "draft email to jason on the laura clarke email"
JSON: {{"email_reference": "laura clarke", "instruction": "draft email to jason", "search_type": "keyword"}}

Msg: "forward the invoice to accounting"
JSON: {{"email_reference": "invoice", "instruction": "forward to accounting", "search_type": "keyword"}}

Msg: "Re: Q4 Report - send update to team"
JSON: {{"email_reference": "Q4 Report", "instruction": "send update to team", "search_type": "subject"}}

Now parse:
Msg: "{text}"
JSON:"""

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': 0.1},
                format='json'
            )
            data = json.loads(response['response'])
            data['parsed_with'] = 'llm'
            logger.debug(f"LLM parsed: {text} -> {data}")
            return data
        except Exception as e:
            logger.warning(f"LLM Parse failed: {e}")
            return None

    def _rule_based_parse(self, text: str) -> Dict:
        """
        Layer 2: Regex Patterns (Backward Compatibility)

        Fallback parser using regex patterns to extract email reference
        and instruction from the message text.
        """
        # Pattern 1: "X - Y" format
        match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', text)
        if match:
            return {
                'email_reference': match.group(1).strip(),
                'instruction': match.group(2).strip(),
                'search_type': 'keyword',
                'parsed_with': 'rules'
            }

        # Pattern 2: "Re: X - Y" format
        match = re.match(r'^Re:\s*(.+?)\s*[-–—]\s*(.+)$', text, re.IGNORECASE)
        if match:
            return {
                'email_reference': match.group(1).strip(),
                'instruction': match.group(2).strip(),
                'search_type': 'subject',
                'parsed_with': 'rules'
            }

        # Pattern 3: "From X - Y" format
        match = re.match(r'^From\s+(.+?)\s*[-–—]\s*(.+)$', text, re.IGNORECASE)
        if match:
            return {
                'email_reference': match.group(1).strip(),
                'instruction': match.group(2).strip(),
                'search_type': 'sender',
                'parsed_with': 'rules'
            }

        # Layer 3: Safety Fallback
        # If no pattern matches, treat entire text as email reference
        return {
            'email_reference': text,
            'instruction': 'process email',
            'search_type': 'keyword',
            'parsed_with': 'fallback'
        }

    def parse_with_fallback(self, text: str) -> Dict:
        """
        Main entry point for parsing.

        Attempts LLM parsing first, falls back to regex if LLM unavailable.

        Args:
            text: The message text to parse

        Returns:
            Dict containing:
                - email_reference: The email identifier (subject, sender, keyword)
                - instruction: What to do with the email
                - search_type: How to search (keyword, subject, sender)
                - parsed_with: Which method was used (llm, rules, fallback)
        """
        # Try LLM first
        result = self.parse_with_llm(text)
        if result:
            return result

        # Fall back to regex
        return self._rule_based_parse(text)


# --- Test Suite ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    parser = SmartParser()
    print(f"SmartParser initialized. LLM available: {parser.available}\n")

    tests = [
        "draft email to jason on the laura clarke email",
        "Project X - send update",
        "forward the invoice",
        "Re: Q4 Report - send summary to team",
        "From john@example.com - confirm payment received",
    ]

    for t in tests:
        res = parser.parse_with_fallback(t)
        print(f"Input: {t}")
        print(f"Output: {json.dumps(res, indent=2)}\n")
