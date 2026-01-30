"""
Claude Client for Mode 4
Claude Team API integration for escalated emails and complex tasks.

SETUP INSTRUCTIONS:
1. Go to https://console.anthropic.com/
2. Sign in with your Claude Team account
3. Navigate to API Keys → Create new key
4. Copy the key (starts with 'sk-ant-')
5. Add to environment:
   - Mac: Add to ~/.zshrc: export ANTHROPIC_API_KEY="sk-ant-..."
   - Or add to mode4/m1_config.py: ANTHROPIC_API_KEY = "sk-ant-..."

Usage:
    from claude_client import ClaudeClient

    client = ClaudeClient()

    # Generate draft for complex email
    draft = client.generate_email_draft(context)

    # Refine an Ollama draft
    refined = client.refine_draft(ollama_draft, context)
"""

import os
import json
import re
from typing import Dict, Any, Optional, List

# Anthropic library
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ClaudeClientError(Exception):
    """Custom exception for Claude client errors."""
    pass


class ClaudeClient:
    """
    Claude Team API client for escalated emails.

    Uses claude-3-haiku for fast, cost-effective draft generation.
    Falls back gracefully when API is unavailable.
    """

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (optional, loads from config/env)
            model: Model to use (default: claude-3-haiku-20240307)
        """
        if not ANTHROPIC_AVAILABLE:
            raise ClaudeClientError(
                "Anthropic package not installed. Run:\n"
                "pip install anthropic"
            )

        # Try to load API key from config first, then env var
        self.api_key = api_key
        if not self.api_key:
            try:
                from m1_config import ANTHROPIC_API_KEY
                self.api_key = ANTHROPIC_API_KEY
            except (ImportError, AttributeError):
                pass

        if not self.api_key:
            self.api_key = os.getenv('ANTHROPIC_API_KEY')

        # Model selection - haiku is fast and cheap
        self.model = model or 'claude-3-haiku-20240307'

        # Initialize client if key is available
        self._client = None
        if self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)

    def is_available(self) -> bool:
        """Check if Claude API is configured and working."""
        if not self.api_key or not self._client:
            return False

        try:
            # Quick test - just check if we can instantiate
            # Don't make actual API call to avoid costs
            return True
        except Exception:
            return False

    # ==================
    # EMAIL DRAFT GENERATION
    # ==================

    def generate_email_draft(
        self,
        email_data: Dict[str, Any],
        instruction: str,
        template: Dict[str, Any] = None,
        contact_tone: str = None
    ) -> Dict[str, Any]:
        """
        Generate an email draft for complex/low-confidence emails.

        Args:
            email_data: Original email data (subject, body, sender_email, sender_name)
            instruction: User's instruction (e.g., "send W9 and wiring")
            template: Optional template dict with template_body and variables
            contact_tone: Optional preferred tone for this contact

        Returns:
            Dict with draft_text, confidence, notes, model
        """
        if not self._client:
            return {
                'success': False,
                'error': 'Claude API not configured',
                'draft_text': None
            }

        # Build context
        context = f"""You are drafting an email response for Derek Criollo, Director of Operations at Old City Capital (a real estate investment firm).

ORIGINAL EMAIL:
Subject: {email_data.get('subject', 'N/A')}
From: {email_data.get('sender_name', 'Unknown')} <{email_data.get('sender_email', 'unknown')}>
Body:
{email_data.get('body', 'N/A')[:2000]}

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
Return ONLY the email body text, no subject line or headers.
Do not include any explanations or meta-commentary."""

        else:
            prompt = context + """
Write a professional email response following Derek's instruction.
Keep it concise and appropriate for business communication.
Return ONLY the email body text, no subject line or headers.
Do not include any explanations or meta-commentary."""

        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            draft_text = message.content[0].text.strip()

            # Clean up common artifacts
            draft_text = self._clean_draft(draft_text)

            return {
                'success': True,
                'draft_text': draft_text,
                'model': self.model,
                'template_used': template.get('template_id') if template else None,
                'input_tokens': message.usage.input_tokens,
                'output_tokens': message.usage.output_tokens
            }

        except anthropic.APIError as e:
            return {
                'success': False,
                'error': f"Claude API error: {str(e)}",
                'draft_text': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'draft_text': None
            }

    def refine_draft(
        self,
        original_draft: str,
        email_data: Dict[str, Any],
        instructions: str = "Review and improve this draft. Focus on: tone, clarity, completeness"
    ) -> Dict[str, Any]:
        """
        Refine an Ollama-generated draft with Claude.

        Args:
            original_draft: Draft text from Ollama
            email_data: Original email context
            instructions: Refinement instructions

        Returns:
            Dict with refined_draft, changes_made, model
        """
        if not self._client:
            return {
                'success': False,
                'error': 'Claude API not configured',
                'draft_text': None
            }

        prompt = f"""You are reviewing and improving an email draft for Derek Criollo, Director of Operations at Old City Capital.

ORIGINAL EMAIL BEING REPLIED TO:
Subject: {email_data.get('subject', 'N/A')}
From: {email_data.get('sender_name', 'Unknown')} <{email_data.get('sender_email', 'unknown')}>
Body excerpt:
{email_data.get('body', 'N/A')[:1000]}

CURRENT DRAFT (generated by another AI):
{original_draft}

INSTRUCTIONS: {instructions}

Please:
1. Improve the draft while keeping Derek's voice and intent
2. List 2-3 specific changes you made

Respond in this exact format:
IMPROVED DRAFT:
[your improved draft text here]

CHANGES MADE:
- [change 1]
- [change 2]
- [change 3 if applicable]"""

        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=1200,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text.strip()

            # Parse response
            refined_draft, changes = self._parse_refinement_response(response_text)

            return {
                'success': True,
                'draft_text': refined_draft,
                'changes_made': changes,
                'model': self.model,
                'original_draft': original_draft,
                'input_tokens': message.usage.input_tokens,
                'output_tokens': message.usage.output_tokens
            }

        except anthropic.APIError as e:
            return {
                'success': False,
                'error': f"Claude API error: {str(e)}",
                'draft_text': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'draft_text': None
            }

    def _parse_refinement_response(self, response: str) -> tuple:
        """Parse Claude's refinement response into draft and changes."""
        draft = response
        changes = []

        # Try to extract IMPROVED DRAFT section
        if "IMPROVED DRAFT:" in response:
            parts = response.split("IMPROVED DRAFT:", 1)
            if len(parts) > 1:
                remainder = parts[1]

                # Try to extract CHANGES MADE section
                if "CHANGES MADE:" in remainder:
                    draft_part, changes_part = remainder.split("CHANGES MADE:", 1)
                    draft = draft_part.strip()

                    # Parse bullet points
                    for line in changes_part.strip().split('\n'):
                        line = line.strip()
                        if line.startswith('-') or line.startswith('•'):
                            changes.append(line.lstrip('-•').strip())
                else:
                    draft = remainder.strip()

        # Clean draft
        draft = self._clean_draft(draft)

        return draft, changes

    def _clean_draft(self, text: str) -> str:
        """Clean up Claude-generated draft text."""
        # Remove common prefixes
        prefixes_to_remove = [
            'Here is the email:', 'Here is your email:', 'Draft:',
            'Email response:', 'Response:', 'Here\'s the draft:',
            'Here is the improved draft:', 'Improved draft:',
            'IMPROVED DRAFT:'
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
    # IDEA BOUNCING
    # ==================

    def generate_probing_question(
        self,
        idea: str,
        previous_qa: List[tuple] = None
    ) -> str:
        """
        Generate a probing question for idea exploration.

        Args:
            idea: The initial idea being explored
            previous_qa: List of (question, answer) tuples from previous rounds

        Returns:
            Next probing question
        """
        if not self._client:
            return "What specific problem does this solve?"

        qa_context = ""
        if previous_qa:
            qa_context = "\n\nPREVIOUS Q&A:\n"
            for q, a in previous_qa:
                qa_context += f"Q: {q}\nA: {a}\n\n"

        prompt = f"""You are helping Derek explore and refine this idea: "{idea}"
{qa_context}
Ask ONE specific, probing question that:
1. Reveals gaps or assumptions in the idea
2. Is actionable and leads to concrete answers
3. Builds on previous answers if any

Return ONLY the question, no explanation."""

        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return message.content[0].text.strip()

        except Exception as e:
            # Fallback question
            return "What's the most important outcome you're trying to achieve?"

    def generate_gameplan(
        self,
        idea: str,
        qa_pairs: List[tuple]
    ) -> str:
        """
        Generate a gameplan based on idea exploration.

        Args:
            idea: The initial idea
            qa_pairs: All (question, answer) pairs from exploration

        Returns:
            Gameplan text
        """
        if not self._client:
            return "Unable to generate gameplan - Claude API not configured."

        qa_text = ""
        for q, a in qa_pairs:
            qa_text += f"Q: {q}\nA: {a}\n\n"

        prompt = f"""Based on exploring this idea with Derek:

IDEA: {idea}

EXPLORATION:
{qa_text}

Create a brief, actionable gameplan that:
1. Summarizes key insights from the exploration
2. Lists 3-5 concrete next steps
3. Identifies any remaining gaps or risks

Keep it concise and actionable."""

        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=800,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return message.content[0].text.strip()

        except Exception as e:
            return f"Gameplan generation failed: {str(e)}"


# ==================
# TESTING
# ==================

def test_claude_client():
    """Test the Claude client."""
    print("Testing Claude Client...")
    print("=" * 60)

    if not ANTHROPIC_AVAILABLE:
        print("ERROR: Anthropic package not installed.")
        print("Run: pip install anthropic")
        return

    try:
        client = ClaudeClient()

        if not client.is_available():
            print("WARNING: Claude API not configured.")
            print("\nTo set up Claude API:")
            print("1. Go to https://console.anthropic.com/")
            print("2. Sign in with your Claude Team account")
            print("3. Navigate to API Keys → Create new key")
            print("4. Add to environment: export ANTHROPIC_API_KEY='sk-ant-...'")
            print("\nOr add to m1_config.py: ANTHROPIC_API_KEY = 'sk-ant-...'")
            return

        print(f"Claude available with model: {client.model}")
        print()

        # Test draft generation
        print("Testing draft generation...")
        test_email = {
            'subject': 'Complex investment question',
            'body': 'Hi Derek, I need help understanding the cap rate analysis for the Phoenix property. Can you explain how you calculated the 7.2% figure?',
            'sender_email': 'investor@example.com',
            'sender_name': 'John Investor'
        }

        result = client.generate_email_draft(
            test_email,
            "explain the cap rate calculation professionally"
        )

        if result.get('success'):
            print("  Draft generated successfully!")
            print(f"  Preview: {result['draft_text'][:100]}...")
            print(f"  Tokens: {result.get('input_tokens', 0)} in, {result.get('output_tokens', 0)} out")
        else:
            print(f"  ERROR: {result.get('error')}")
        print()

        # Test refinement
        print("Testing draft refinement...")
        ollama_draft = """Hi John,

The cap rate is 7.2%. Let me know if you have questions.

Best,
Derek"""

        refine_result = client.refine_draft(ollama_draft, test_email)

        if refine_result.get('success'):
            print("  Draft refined successfully!")
            print(f"  Changes: {refine_result.get('changes_made', [])}")
            print(f"  Preview: {refine_result['draft_text'][:100]}...")
        else:
            print(f"  ERROR: {refine_result.get('error')}")
        print()

        print("Claude client test complete!")

    except ClaudeClientError as e:
        print(f"ERROR: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    test_claude_client()
