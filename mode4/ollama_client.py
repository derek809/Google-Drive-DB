"""
Ollama Client for Mode 4
Local LLM integration for email triage and draft generation.

Usage:
    from ollama_client import OllamaClient

    client = OllamaClient()

    # Triage an email
    result = client.triage(email_data, patterns)

    # Generate a draft
    draft = client.generate_draft(email_data, instruction, template)
"""

import json
import re
from typing import Dict, List, Optional, Any

# Ollama library
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


class OllamaClientError(Exception):
    """Custom exception for Ollama client errors."""
    pass


class OllamaClient:
    """
    Ollama client for local LLM operations.

    Provides email triage and draft generation using locally running Ollama models.
    """

    def __init__(
        self,
        model: str = None,
        host: str = None,
        temperature: float = None
    ):
        """
        Initialize Ollama client.

        Args:
            model: Ollama model name (e.g., "llama3.2", "mistral")
            host: Ollama API host (default: http://localhost:11434)
            temperature: Generation temperature (lower = more deterministic)
        """
        if not OLLAMA_AVAILABLE:
            raise OllamaClientError(
                "Ollama package not installed. Run:\n"
                "pip install ollama\n\n"
                "Also ensure Ollama is running:\n"
                "brew install ollama && ollama pull llama3.2"
            )

        # Try to import config for defaults
        try:
            from m1_config import OLLAMA_MODEL, OLLAMA_HOST, OLLAMA_TEMPERATURE
            self.model = model or OLLAMA_MODEL
            self.host = host or OLLAMA_HOST
            self.temperature = temperature if temperature is not None else OLLAMA_TEMPERATURE
        except ImportError:
            self.model = model or "llama3.2"
            self.host = host or "http://localhost:11434"
            self.temperature = temperature if temperature is not None else 0.3

        # Configure Ollama client
        if self.host != "http://localhost:11434":
            ollama.Client(host=self.host)

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            response = ollama.list()
            # Handle both old dict format and new object format
            if hasattr(response, 'models'):
                # New format: response.models is a list of Model objects
                model_names = [m.model.split(':')[0] for m in response.models]
            else:
                # Old format: response is a dict with 'models' key
                model_names = [m['name'].split(':')[0] for m in response.get('models', [])]
            return self.model.split(':')[0] in model_names
        except Exception:
            return False

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text string
        """
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': max_tokens
                }
            )
            return response.get('response', '')
        except Exception as e:
            raise OllamaClientError(f"Generation failed: {e}")

    # ==================
    # EMAIL TRIAGE
    # ==================

    def triage(
        self,
        email_data: Dict[str, Any],
        patterns: List[Dict[str, Any]],
        contacts: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Triage an email to determine pattern match and confidence.

        Args:
            email_data: Dict with subject, body, sender_email, sender_name
            patterns: List of pattern dicts from Sheets (pattern_name, keywords, confidence_boost)
            contacts: Optional list of known contacts

        Returns:
            Dict with:
                - pattern_name: Matched pattern (or None)
                - confidence: 0-100 score
                - reasoning: List of reasons
                - can_template: Whether a template can handle this
                - route: 'ollama_only', 'ollama_with_review', or 'escalate_to_claude'
        """
        # First, do keyword-based pattern matching
        keyword_result = self._keyword_pattern_match(email_data, patterns)

        # Check if sender is known
        sender_known = False
        if contacts:
            sender_known = any(
                c.get('email', '').lower() == email_data.get('sender_email', '').lower()
                for c in contacts
            )

        # Calculate base confidence
        confidence, reasoning = self._calculate_confidence(
            email_data,
            keyword_result,
            sender_known
        )

        # Use LLM to validate and potentially adjust
        llm_result = self._llm_triage(email_data, keyword_result, confidence)

        # Combine results
        final_confidence = llm_result.get('adjusted_confidence', confidence)
        final_reasoning = reasoning + llm_result.get('llm_reasoning', [])

        # Determine routing
        try:
            from m1_config import OLLAMA_ONLY_THRESHOLD, OLLAMA_REVIEW_THRESHOLD
        except ImportError:
            OLLAMA_ONLY_THRESHOLD = 90
            OLLAMA_REVIEW_THRESHOLD = 70

        if final_confidence >= OLLAMA_ONLY_THRESHOLD:
            route = 'ollama_only'
        elif final_confidence >= OLLAMA_REVIEW_THRESHOLD:
            route = 'ollama_with_review'
        else:
            route = 'escalate_to_claude'

        return {
            'pattern_name': keyword_result.get('pattern_name'),
            'pattern_confidence_boost': keyword_result.get('confidence_boost', 0),
            'keyword_matches': keyword_result.get('matched_keywords', []),
            'confidence': final_confidence,
            'reasoning': final_reasoning,
            'can_template': keyword_result.get('pattern_name') is not None,
            'sender_known': sender_known,
            'route': route,
            'llm_notes': llm_result.get('notes', '')
        }

    def _keyword_pattern_match(
        self,
        email_data: Dict[str, Any],
        patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Match email against patterns using keyword matching.

        Returns dict with pattern_name, confidence_boost, matched_keywords
        """
        subject = email_data.get('subject', '').lower()
        body = email_data.get('body', '').lower()
        combined = f"{subject} {body}"

        best_match = None
        best_score = 0
        best_keywords = []

        for pattern in patterns:
            pattern_name = pattern.get('Pattern Name') or pattern.get('pattern_name', '')
            keywords_str = pattern.get('Keywords') or pattern.get('keywords', '')
            confidence_boost = pattern.get('Confidence Boost') or pattern.get('confidence_boost', 0)

            # Parse keywords
            if isinstance(keywords_str, str):
                keywords = [k.strip().lower() for k in keywords_str.split(',') if k.strip()]
            else:
                keywords = keywords_str if keywords_str else []

            # Count matches
            matched = [kw for kw in keywords if kw in combined]
            score = len(matched)

            if score > best_score:
                best_score = score
                best_match = {
                    'pattern_name': pattern_name,
                    'confidence_boost': int(confidence_boost) if confidence_boost else 0,
                    'matched_keywords': matched
                }
                best_keywords = matched

        return best_match or {'pattern_name': None, 'confidence_boost': 0, 'matched_keywords': []}

    def _calculate_confidence(
        self,
        email_data: Dict[str, Any],
        pattern_result: Dict[str, Any],
        sender_known: bool
    ) -> tuple:
        """
        Calculate confidence score based on various factors.

        Returns (score, reasoning_list)
        """
        score = 50  # Base confidence
        reasoning = ["Base confidence: 50"]

        # Pattern match bonus
        if pattern_result.get('pattern_name'):
            boost = pattern_result.get('confidence_boost', 0)
            score += boost
            reasoning.append(f"Pattern '{pattern_result['pattern_name']}' matched: +{boost}")

            # Bonus for multiple keyword matches
            match_count = len(pattern_result.get('matched_keywords', []))
            if match_count > 1:
                extra = min(match_count * 2, 10)
                score += extra
                reasoning.append(f"Multiple keywords matched ({match_count}): +{extra}")

        # Known sender bonus
        if sender_known:
            score += 10
            reasoning.append("Known sender: +10")
        else:
            score -= 20
            reasoning.append("Unknown sender: -20")

        # Check for compliance/sensitive keywords (penalties)
        content = f"{email_data.get('subject', '')} {email_data.get('body', '')}".lower()

        compliance_keywords = ['finra', 'sec', 'compliance', 'regulatory', 'audit', 'subpoena', 'legal']
        for keyword in compliance_keywords:
            if keyword in content:
                score -= 30
                reasoning.append(f"Compliance keyword '{keyword}': -30")
                break

        # Clamp to 0-100
        score = max(0, min(100, score))

        return score, reasoning

    def _llm_triage(
        self,
        email_data: Dict[str, Any],
        keyword_result: Dict[str, Any],
        current_confidence: int
    ) -> Dict[str, Any]:
        """
        Use LLM to validate/adjust triage.

        Returns dict with adjusted_confidence, llm_reasoning, notes
        """
        prompt = f"""You are an email triage assistant for Old City Capital, a real estate investment firm.

Analyze this email and validate/adjust the automated confidence score.

EMAIL:
Subject: {email_data.get('subject', 'N/A')}
From: {email_data.get('sender_name', 'Unknown')} <{email_data.get('sender_email', 'unknown')}>
Body:
{email_data.get('body', 'N/A')[:1000]}

AUTOMATED ANALYSIS:
- Pattern matched: {keyword_result.get('pattern_name', 'None')}
- Keywords found: {', '.join(keyword_result.get('matched_keywords', [])) or 'None'}
- Current confidence: {current_confidence}%

TASK:
1. Validate if the pattern match is correct
2. Assess complexity (simple template response vs complex reasoning needed)
3. Adjust confidence if warranted (suggest new score if different)

Respond in JSON format:
{{
    "pattern_correct": true/false,
    "complexity": "simple/medium/complex",
    "adjusted_confidence": {current_confidence},
    "reasoning": "brief explanation",
    "can_use_template": true/false
}}"""

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': 300
                }
            )

            text = response.get('response', '{}')

            # Try to parse JSON from response
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {}

            return {
                'adjusted_confidence': result.get('adjusted_confidence', current_confidence),
                'llm_reasoning': [result.get('reasoning', 'LLM analysis completed')],
                'notes': f"Complexity: {result.get('complexity', 'unknown')}, Template: {result.get('can_use_template', 'unknown')}"
            }

        except Exception as e:
            # On LLM error, return original confidence
            return {
                'adjusted_confidence': current_confidence,
                'llm_reasoning': [f'LLM triage skipped: {str(e)}'],
                'notes': 'LLM unavailable'
            }

    # ==================
    # DRAFT GENERATION
    # ==================

    def generate_draft(
        self,
        email_data: Dict[str, Any],
        instruction: str,
        template: Dict[str, Any] = None,
        contact_tone: str = None
    ) -> Dict[str, Any]:
        """
        Generate an email draft response.

        Args:
            email_data: Original email data
            instruction: User's instruction (e.g., "send W9 and wiring")
            template: Optional template dict with template_body and variables
            contact_tone: Optional preferred tone for this contact

        Returns:
            Dict with draft_text, confidence, notes
        """
        # Build context
        context = f"""You are drafting an email response for Derek Criollo, Director of Operations at Old City Capital.

ORIGINAL EMAIL:
Subject: {email_data.get('subject', 'N/A')}
From: {email_data.get('sender_name', 'Unknown')} <{email_data.get('sender_email', 'unknown')}>
Body:
{email_data.get('body', 'N/A')[:1500]}

DEREK'S INSTRUCTION: {instruction}
"""

        if contact_tone:
            context += f"\nPREFERRED TONE for this contact: {contact_tone}\n"

        if template:
            context += f"""
TEMPLATE TO USE:
{template.get('template_body', '')}

Variables to fill: {template.get('variables', '')}
"""
            prompt = context + """
Fill in the template with appropriate values based on the email and instruction.
Keep the response professional and concise.
Return ONLY the email body text, no subject line or headers."""

        else:
            prompt = context + """
Write a professional email response following Derek's instruction.
Keep it concise and appropriate for business communication.
Return ONLY the email body text, no subject line or headers."""

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': 800
                }
            )

            draft_text = response.get('response', '').strip()

            # Clean up common LLM artifacts
            draft_text = self._clean_draft(draft_text)

            return {
                'success': True,
                'draft_text': draft_text,
                'model': self.model,
                'template_used': template.get('template_id') if template else None
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'draft_text': None
            }

    def _clean_draft(self, text: str) -> str:
        """Clean up LLM-generated draft text."""
        # Remove common prefixes
        prefixes_to_remove = [
            'Here is the email:', 'Here is your email:', 'Draft:',
            'Email response:', 'Response:', 'Here\'s the draft:'
        ]
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()

        # Remove markdown code blocks
        if text.startswith('```'):
            text = re.sub(r'^```[^\n]*\n', '', text)
            text = re.sub(r'\n```$', '', text)

        # Remove subject line if accidentally included
        lines = text.split('\n')
        if lines and lines[0].lower().startswith('subject:'):
            lines = lines[1:]
            text = '\n'.join(lines).strip()

        return text.strip()


# ==================
# TESTING
# ==================

def test_ollama_client():
    """Test the Ollama client."""
    print("Testing Ollama Client...")
    print("=" * 60)

    if not OLLAMA_AVAILABLE:
        print("ERROR: Ollama package not installed.")
        print("Run: pip install ollama")
        return

    try:
        client = OllamaClient()

        if not client.is_available():
            print(f"ERROR: Ollama model '{client.model}' not available.")
            print("Ensure Ollama is running: ollama serve")
            print(f"Pull the model: ollama pull {client.model}")
            return

        print(f"Ollama available with model: {client.model}")
        print()

        # Test triage
        print("Testing triage...")
        test_email = {
            'subject': 'W9 Request',
            'body': 'Hi Derek, can you send your W9 and wiring instructions? Thanks!',
            'sender_email': 'client@example.com',
            'sender_name': 'John Client'
        }

        test_patterns = [
            {'pattern_name': 'w9_wiring_request', 'keywords': 'w9, wiring instructions, wire details', 'confidence_boost': 20},
            {'pattern_name': 'invoice_processing', 'keywords': 'invoice, fees, quarterly', 'confidence_boost': 15}
        ]

        result = client.triage(test_email, test_patterns)
        print(f"  Pattern: {result.get('pattern_name')}")
        print(f"  Confidence: {result.get('confidence')}%")
        print(f"  Route: {result.get('route')}")
        print()

        # Test draft generation
        print("Testing draft generation...")
        draft_result = client.generate_draft(
            test_email,
            "send W9 and wiring instructions"
        )

        if draft_result.get('success'):
            print("  Draft generated successfully!")
            print(f"  Preview: {draft_result['draft_text'][:100]}...")
        else:
            print(f"  ERROR: {draft_result.get('error')}")

        print()
        print("Ollama client test complete!")

    except OllamaClientError as e:
        print(f"ERROR: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    test_ollama_client()
