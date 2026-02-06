"""
LLM Router for Mode 4
Routes tasks to Ollama (fast/free) or Claude (smart) based on complexity.

Key principle: User ALWAYS chooses via button - router only provides recommendations.

Usage:
    from llm_router import LLMRouter

    router = LLMRouter()

    # Get recommendation for user
    rec = router.get_recommendation(message, pattern_confidence=0.85)
    # Returns: "Ollama (85% pattern match - high confidence)"

    # Check which LLMs are available
    status = router.get_availability_status()
"""

import os
from typing import Dict, Any, Optional, Tuple


class LLMRouter:
    """
    Routes tasks between Ollama and Claude.

    Routing logic:
    - User ALWAYS makes final choice via inline buttons
    - Router provides recommendations based on:
      1. Pattern confidence score
      2. Task complexity indicators
      3. Ambiguity detection
    """

    def __init__(self):
        """Initialize router with keyword sets for detection."""
        # Keywords suggesting Ollama can handle it
        self.simple_task_keywords = [
            'draft', 'rewrite', 'summarize', 'format',
            'meeting request', 'follow up', 'thank you',
            'confirm', 'reschedule', 'w9', 'wiring',
            'invoice', 'receipt', 'acknowledge'
        ]

        # Keywords suggesting Claude is needed
        self.complex_task_keywords = [
            'complex', 'sensitive', 'negotiate', 'strategy',
            'analyze', 'recommend', 'brainstorm', 'plan',
            'help me figure out', 'what should i', 'advice',
            'legal', 'compliance', 'finra', 'sec', 'audit'
        ]

        # Keywords suggesting ambiguity
        self.ambiguous_indicators = [
            'help', 'not sure', 'what should', 'figure out',
            "don't know", 'confused', 'unclear', 'maybe'
        ]

        # Confidence thresholds
        self.high_confidence_threshold = 0.90
        self.medium_confidence_threshold = 0.70

    def get_recommendation(
        self,
        message: str,
        pattern_confidence: float = None,
        sender_known: bool = False
    ) -> str:
        """
        Get LLM recommendation text to show user.

        Args:
            message: User's message text
            pattern_confidence: Confidence score from pattern matching (0.0-1.0)
            sender_known: Whether sender is in contacts

        Returns:
            Human-readable recommendation string
        """
        # Determine recommendation
        llm, reason = self.analyze(message, pattern_confidence, sender_known)

        # Format recommendation text
        if llm == 'ollama':
            if pattern_confidence and pattern_confidence >= self.high_confidence_threshold:
                return f"Ollama ({int(pattern_confidence * 100)}% pattern match - high confidence)"
            elif pattern_confidence and pattern_confidence >= self.medium_confidence_threshold:
                return f"Ollama ({int(pattern_confidence * 100)}% confidence - medium)"
            else:
                return "Ollama (simple task detected)"

        elif llm == 'claude':
            if reason == 'low_confidence':
                conf_pct = int(pattern_confidence * 100) if pattern_confidence else 0
                return f"Claude (low pattern confidence - {conf_pct}%)"
            elif reason == 'complex_task':
                return "Claude (complex reasoning needed)"
            elif reason == 'ambiguous':
                return "Claude (ambiguous request - needs clarification)"
            elif reason == 'compliance':
                return "Claude (sensitive/compliance topic detected)"
            else:
                return "Claude (recommended for this task)"

        else:
            # Either could work
            return "Either Ollama or Claude (your choice)"

    def analyze(
        self,
        message: str,
        pattern_confidence: float = None,
        sender_known: bool = False
    ) -> Tuple[str, str]:
        """
        Analyze message and determine recommended LLM.

        Args:
            message: User's message text
            pattern_confidence: Confidence score (0.0-1.0)
            sender_known: Whether sender is in contacts

        Returns:
            Tuple of (recommended_llm, reason)
            llm: 'ollama', 'claude', or 'either'
            reason: 'high_confidence', 'low_confidence', 'complex_task', etc.
        """
        msg_lower = message.lower()

        # Check for compliance/sensitive keywords - always escalate
        if self._has_compliance_keywords(msg_lower):
            return 'claude', 'compliance'

        # Check for explicit complexity
        if self._is_complex(msg_lower):
            return 'claude', 'complex_task'

        # Check for ambiguity
        if self._is_ambiguous(msg_lower):
            return 'claude', 'ambiguous'

        # Use pattern confidence if available
        if pattern_confidence is not None:
            if pattern_confidence >= self.high_confidence_threshold:
                return 'ollama', 'high_confidence'
            elif pattern_confidence >= self.medium_confidence_threshold:
                # Medium confidence - could go either way
                if sender_known:
                    return 'ollama', 'medium_confidence_known_sender'
                else:
                    return 'either', 'medium_confidence'
            else:
                return 'claude', 'low_confidence'

        # Check for simple task keywords
        if self._is_simple(msg_lower):
            return 'ollama', 'simple_task'

        # Default to either
        return 'either', 'uncertain'

    def _is_simple(self, message: str) -> bool:
        """Check if task is simple (Ollama can handle)."""
        return any(kw in message for kw in self.simple_task_keywords)

    def _is_complex(self, message: str) -> bool:
        """Check if task requires complex reasoning (Claude needed)."""
        return any(kw in message for kw in self.complex_task_keywords)

    def _is_ambiguous(self, message: str) -> bool:
        """Check if message lacks clear intent."""
        # Very short messages are ambiguous
        words = message.split()
        if len(words) < 3:
            return True

        # Check for ambiguity indicators
        return any(ind in message for ind in self.ambiguous_indicators)

    def _has_compliance_keywords(self, message: str) -> bool:
        """Check for compliance/sensitive content."""
        compliance_keywords = [
            'finra', 'sec', 'compliance', 'regulatory', 'audit',
            'subpoena', 'legal action', 'investigation', 'lawsuit'
        ]
        return any(kw in message for kw in compliance_keywords)

    def get_availability_status(self) -> Dict[str, bool]:
        """
        Check which LLMs are available.

        Returns:
            Dict with 'ollama', 'claude', and 'kimi' availability booleans
        """
        status = {
            'ollama': False,
            'claude': False,
            'kimi': False
        }

        # Check Ollama
        try:
            from ollama_client import OllamaClient
            client = OllamaClient()
            status['ollama'] = client.is_available()
            del client
        except Exception:
            pass

        # Check Claude
        try:
            from claude_client import ClaudeClient
            client = ClaudeClient()
            status['claude'] = client.is_available()
            del client
        except Exception:
            pass

        # Check Kimi
        try:
            from kimi_client import KimiClient
            client = KimiClient()
            status['kimi'] = client.is_available()
            del client
        except Exception:
            pass

        return status

    def get_fallback_llm(self) -> Optional[str]:
        """
        Get fallback LLM if primary is unavailable.

        Returns:
            'ollama', 'kimi', 'claude', or None if none available
        """
        status = self.get_availability_status()

        if status['ollama']:
            return 'ollama'
        elif status['kimi']:
            return 'kimi'
        elif status['claude']:
            return 'claude'
        else:
            return None

    def get_smart_llm(self) -> Optional[str]:
        """
        Get the best available 'smart' LLM (Kimi or Claude).

        Returns:
            'kimi', 'claude', or None if neither available
        """
        status = self.get_availability_status()

        if status['kimi']:
            return 'kimi'
        elif status['claude']:
            return 'claude'
        else:
            return None


# ==================
# ROUTING HELPERS
# ==================

def route_draft_request(
    message: str,
    email_data: Dict[str, Any],
    pattern_match: Optional[Dict] = None,
    contact_known: bool = False
) -> Dict[str, Any]:
    """
    Route a draft request and return routing decision.

    Args:
        message: User's instruction
        email_data: Email being replied to
        pattern_match: Result from pattern matching (if any)
        contact_known: Whether sender is in contacts

    Returns:
        Dict with:
            - recommended_llm: 'ollama' or 'claude'
            - recommendation_text: Human-readable recommendation
            - reason: Why this LLM was recommended
            - confidence: Pattern confidence if available
            - can_use_ollama: Whether Ollama is a reasonable choice
            - should_escalate: Whether Claude is strongly recommended
    """
    router = LLMRouter()

    # Extract pattern confidence
    pattern_confidence = None
    if pattern_match:
        # Normalize confidence to 0-1 range
        boost = pattern_match.get('confidence_boost', 0)
        keyword_count = pattern_match.get('keyword_matches', 0)

        # Calculate effective confidence
        base = 50
        score = base + boost + (min(keyword_count, 5) * 2)
        if contact_known:
            score += 10
        else:
            score -= 20

        pattern_confidence = max(0, min(100, score)) / 100

    # Get recommendation
    recommended_llm, reason = router.analyze(
        message,
        pattern_confidence=pattern_confidence,
        sender_known=contact_known
    )

    recommendation_text = router.get_recommendation(
        message,
        pattern_confidence=pattern_confidence,
        sender_known=contact_known
    )

    return {
        'recommended_llm': recommended_llm,
        'recommendation_text': recommendation_text,
        'reason': reason,
        'confidence': pattern_confidence,
        'can_use_ollama': recommended_llm in ['ollama', 'either'],
        'should_escalate': recommended_llm == 'claude' and reason in ['compliance', 'complex_task']
    }


# ==================
# TESTING
# ==================

def test_llm_router():
    """Test the LLM router."""
    print("Testing LLM Router...")
    print("=" * 60)

    router = LLMRouter()

    # Test cases
    test_cases = [
        # (message, pattern_confidence, sender_known, expected_recommendation)
        ("Draft W9 response", 0.95, True, "Ollama"),
        ("Send invoice confirmation", 0.85, True, "Ollama"),
        ("Help me figure out the strategy", None, False, "Claude"),
        ("Respond to FINRA audit request", 0.70, True, "Claude"),
        ("Quick follow up", 0.60, False, "Claude/Either"),
        ("", None, False, "Ambiguous"),
        ("thanks", None, False, "Ambiguous"),
    ]

    print("\nTesting recommendations:\n")
    for message, confidence, known, expected in test_cases:
        rec = router.get_recommendation(message, confidence, known)
        llm, reason = router.analyze(message, confidence, known)

        print(f"Message: '{message[:30]}...' if len(message) > 30 else '{message}'")
        print(f"  Confidence: {confidence}, Known: {known}")
        print(f"  Recommendation: {rec}")
        print(f"  LLM: {llm}, Reason: {reason}")
        print()

    # Test availability
    print("\nChecking LLM availability...")
    status = router.get_availability_status()
    print(f"  Ollama: {'Available' if status['ollama'] else 'Not available'}")
    print(f"  Kimi:   {'Available' if status['kimi'] else 'Not available'}")
    print(f"  Claude: {'Available' if status['claude'] else 'Not available'}")

    fallback = router.get_fallback_llm()
    print(f"  Fallback: {fallback or 'None available'}")

    smart_llm = router.get_smart_llm()
    print(f"  Smart LLM: {smart_llm or 'None available'}")

    print("\n" + "=" * 60)
    print("LLM Router test complete!")


if __name__ == "__main__":
    test_llm_router()
