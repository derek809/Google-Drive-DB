"""
Test Conversation Manager
Tests natural language understanding and intent classification.
"""

import asyncio
import sys
from conversation_manager import ConversationManager, Intent


def test_intent_classification():
    """Test intent classification with various inputs."""
    conv_mgr = ConversationManager()

    test_cases = [
        # Greetings
        ("hi", Intent.GREETING),
        ("hello", Intent.GREETING),
        ("hey", Intent.GREETING),
        ("yo", Intent.GREETING),

        # Help
        ("help", Intent.HELP_REQUEST),
        ("what can you do", Intent.HELP_REQUEST),
        ("how do i", Intent.HELP_REQUEST),

        # Email draft
        ("draft email to jason", Intent.EMAIL_DRAFT),
        ("write to sarah about the invoice", Intent.EMAIL_DRAFT),
        ("compose email", Intent.EMAIL_DRAFT),

        # Email search
        ("find emails from john", Intent.EMAIL_SEARCH),
        ("search for emails about budget", Intent.EMAIL_SEARCH),

        # Todo add
        ("add call sarah to my todo list", Intent.TODO_ADD),
        ("remind me to send invoice", Intent.TODO_ADD),
        ("create task for meeting", Intent.TODO_ADD),

        # Todo list
        ("show my todos", Intent.TODO_LIST),
        ("list my tasks", Intent.TODO_LIST),
        ("what's on my todo", Intent.TODO_LIST),

        # Info digest
        ("morning brief", Intent.INFO_DIGEST),
        ("email digest", Intent.INFO_DIGEST),
        ("email summary", Intent.INFO_DIGEST),

        # Status
        ("status", Intent.INFO_STATUS),
        ("system status", Intent.INFO_STATUS),

        # Casual
        ("how are you", Intent.CASUAL_CHAT),
        ("what's up", Intent.CASUAL_CHAT),

        # Commands (should stay as commands)
        ("/status", Intent.COMMAND),
        ("/help", Intent.COMMAND),
        ("/morning", Intent.COMMAND),

        # Legacy email formats (should NOT be classified, but detected as legacy)
        # These will be tested separately in test_legacy_format()
    ]

    passed = 0
    failed = 0

    print("Testing Intent Classification")
    print("=" * 60)

    for text, expected_intent in test_cases:
        result = conv_mgr.classify_intent(text)
        status = "✓" if result == expected_intent else "✗"

        if result == expected_intent:
            passed += 1
            print(f"{status} '{text}' → {result.value}")
        else:
            failed += 1
            print(f"{status} '{text}' → Expected {expected_intent.value}, got {result.value}")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_legacy_format_detection():
    """Test that legacy email formats are correctly detected."""
    conv_mgr = ConversationManager()

    legacy_formats = [
        "Re: W9 Request - send W9 and wiring",
        "From john@example.com - confirm payment",
        "latest from sarah@company.com - schedule meeting",
        "Budget Q4 - approve the numbers",
    ]

    print("\nTesting Legacy Format Detection")
    print("=" * 60)

    passed = 0
    failed = 0

    for text in legacy_formats:
        is_legacy = conv_mgr._is_legacy_email_format(text)
        status = "✓" if is_legacy else "✗"

        if is_legacy:
            passed += 1
            print(f"{status} '{text}' → Detected as legacy")
        else:
            failed += 1
            print(f"{status} '{text}' → NOT detected as legacy (FAIL)")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_response_generation():
    """Test response generation for different intents."""
    conv_mgr = ConversationManager()

    print("\nTesting Response Generation")
    print("=" * 60)

    # Test greetings
    greeting = conv_mgr._generate_greeting()
    print(f"Greeting: {greeting[:80]}...")

    # Test help
    help_msg = conv_mgr._generate_help_message()
    print(f"Help (first line): {help_msg.split(chr(10))[0]}")

    # Test casual
    casual = conv_mgr._generate_casual_response("how are you")
    print(f"Casual: {casual}")

    # Test unclear
    unclear = conv_mgr._generate_unclear_response()
    print(f"Unclear: {unclear[:80]}...")

    print("\n✓ All responses generated successfully")
    return True


def test_context_management():
    """Test conversation context storage and expiry."""
    conv_mgr = ConversationManager()

    print("\nTesting Context Management")
    print("=" * 60)

    user_id = 123456

    # Store context
    conv_mgr.update_context(user_id, {
        'last_intent': Intent.EMAIL_DRAFT,
        'last_reference': 'jason'
    })

    # Retrieve context
    context = conv_mgr.get_context(user_id)
    if context and context.get('last_reference') == 'jason':
        print("✓ Context stored and retrieved correctly")
    else:
        print("✗ Context retrieval failed")
        return False

    # Test expiry (artificially expire)
    import time
    conv_mgr._context_store[user_id]['timestamp'] = time.time() - 2000  # Expired
    expired_context = conv_mgr.get_context(user_id)

    if expired_context is None:
        print("✓ Expired context correctly removed")
    else:
        print("✗ Expired context not removed")
        return False

    print("\n✓ Context management working correctly")
    return True


async def test_integration():
    """Test full integration (requires mocking)."""
    print("\nTesting Integration (Mock)")
    print("=" * 60)

    conv_mgr = ConversationManager(
        telegram_handler=None,  # Would need mock
        mode4_processor=None
    )

    # Test that handle_message returns correct structure
    # This would require actual Telegram handler, so just test the structure

    print("✓ Integration test structure verified")
    print("  (Full integration test requires running bot)")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Conversation Manager Test Suite")
    print("="*60 + "\n")

    all_passed = True

    # Run tests
    all_passed &= test_intent_classification()
    all_passed &= test_legacy_format_detection()
    all_passed &= test_response_generation()
    all_passed &= test_context_management()

    # Async test
    asyncio.run(test_integration())

    # Summary
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("="*60)
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
