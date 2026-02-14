"""
Test Workflow Chaining
Tests multi-step workflow detection and execution.
"""
import os, sys
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _d in ["brain","core","core/Infrastructure","core/InputOutput","core/State&Memory","Bot_actions","LLM"]:
    _p = os.path.join(_root, _d)
    if _p not in sys.path: sys.path.insert(0, _p)

import asyncio
from conversation_manager import ConversationManager

def test_workflow_detection():
    """Test detection of multi-step workflows."""
    conv_mgr = ConversationManager()

    test_cases = [
        # Should detect workflow
        ("Draft email to Jason. Then create a Google Sheet with columns Name, Email, Status. Then email Sarah about it.", True),
        ("Find emails from John. Also draft a response.", True),
        ("Add task to call Sarah. Then remind me tomorrow.", True),
        ("Search for budget email. Then create sheet. Then forward to accounting.", True),
        ("Draft email to Jason and then send it.", True),
        ("Create sheet. After that email the team.", True),

        # Should NOT detect workflow (single step)
        ("Draft email to Jason", False),
        ("Create a Google Sheet", False),
        ("Add task to call Sarah", False),
        ("Find emails from John", False),
    ]

    print("Testing Workflow Detection")
    print("=" * 60)

    passed = 0
    failed = 0

    for text, should_detect in test_cases:
        result = conv_mgr._detect_workflow_chain(text)
        is_workflow = result is not None

        if is_workflow == should_detect:
            status = "✓"
            passed += 1
            if is_workflow:
                print(f"{status} '{text[:50]}...' → Workflow detected ({len(result)} steps)")
            else:
                print(f"{status} '{text[:50]}...' → Single step (correct)")
        else:
            status = "✗"
            failed += 1
            print(f"{status} '{text[:50]}...' → Expected {should_detect}, got {is_workflow}")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_workflow_splitting():
    """Test splitting of workflow into steps."""
    conv_mgr = ConversationManager()

    test_cases = [
        (
            "Draft email to Jason. Then create a Google Sheet with columns Name, Email. Then email Sarah about it.",
            [
                "Draft email to Jason",
                "create a Google Sheet with columns Name, Email",
                "email Sarah about it"
            ]
        ),
        (
            "Find emails from budget. Also draft response.",
            [
                "Find emails from budget",
                "draft response"
            ]
        ),
        (
            "Add task. Plus remind me tomorrow. After that send email.",
            [
                "Add task",
                "remind me tomorrow",
                "send email"
            ]
        ),
    ]

    print("\nTesting Workflow Splitting")
    print("=" * 60)

    passed = 0
    failed = 0

    for text, expected_steps in test_cases:
        result = conv_mgr._detect_workflow_chain(text)

        if result and len(result) == len(expected_steps):
            # Check if steps match (case-insensitive, trimmed)
            match = all(
                r.strip().lower() == e.strip().lower()
                for r, e in zip(result, expected_steps)
            )

            if match:
                status = "✓"
                passed += 1
                print(f"{status} '{text[:40]}...' → {len(result)} steps")
                for i, step in enumerate(result, 1):
                    print(f"    {i}. {step}")
            else:
                status = "✗"
                failed += 1
                print(f"{status} '{text[:40]}...' → Steps don't match")
                print(f"    Expected: {expected_steps}")
                print(f"    Got: {result}")
        else:
            status = "✗"
            failed += 1
            print(f"{status} '{text[:40]}...' → Expected {len(expected_steps)} steps, got {len(result) if result else 0}")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_context_resolution():
    """Test resolution of context references (it, that, the sheet)."""
    conv_mgr = ConversationManager()

    # Create context
    context = {
        'last_email': {
            'subject': 'Q4 Budget',
            'sender': 'Jason',
            'body': 'Please review the budget...'
        },
        'last_sheet': {
            'title': 'Budget Tracker',
            'url': 'https://docs.google.com/spreadsheets/d/abc123'
        },
        'last_draft': {
            'recipient': 'Sarah',
            'subject': 'Re: Budget'
        }
    }

    test_cases = [
        ("email Sarah about the sheet", "email Sarah about the sheet 'Budget Tracker'"),
        ("send it to accounting", "send the email from Jason to accounting"),
        ("update the draft", "update the draft to Sarah"),
    ]

    print("\nTesting Context Resolution")
    print("=" * 60)

    passed = 0
    failed = 0

    for original, expected in test_cases:
        result = conv_mgr._resolve_context_references(original, context)

        if expected.lower() in result.lower() or result.lower() == expected.lower():
            status = "✓"
            passed += 1
            print(f"{status} '{original}' → '{result}'")
        else:
            status = "✗"
            failed += 1
            print(f"{status} '{original}'")
            print(f"    Expected: '{expected}'")
            print(f"    Got: '{result}'")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_sheet_title_generation():
    """Test generation of meaningful sheet titles."""
    conv_mgr = ConversationManager()

    test_cases = [
        # With explicit title
        ("Create a sheet called 'Budget 2024'", {}, "Budget 2024"),
        ("Create sheet named 'Client Tracker'", {}, "Client Tracker"),

        # From email context
        ("Create a sheet with columns Name, Email", {'last_email': {'subject': 'Q4 Report'}}, "Q4 Report - Data"),

        # Default (just check it has a value)
        ("Create a sheet", {}, None),  # Will have timestamp
    ]

    print("\nTesting Sheet Title Generation")
    print("=" * 60)

    passed = 0
    failed = 0

    for step, context, expected_title in test_cases:
        result = conv_mgr._generate_sheet_title(step, context)

        if expected_title is None:
            # Just check it generated something
            if result and len(result) > 0:
                status = "✓"
                passed += 1
                print(f"{status} '{step}' → '{result}' (default)")
            else:
                status = "✗"
                failed += 1
                print(f"{status} '{step}' → No title generated")
        elif result == expected_title:
            status = "✓"
            passed += 1
            print(f"{status} '{step}' → '{result}'")
        else:
            status = "✗"
            failed += 1
            print(f"{status} '{step}'")
            print(f"    Expected: '{expected_title}'")
            print(f"    Got: '{result}'")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_workflow_examples():
    """Show example workflows that should work."""
    print("\nWorkflow Examples")
    print("=" * 60)

    examples = [
        {
            'description': 'Email + Sheet + Notify',
            'text': 'Draft email to Jason about budget. Then create a Google Sheet with columns Client, Amount, Status. Then email Sarah saying I created the sheet.',
            'expected_steps': 3
        },
        {
            'description': 'Search + Respond',
            'text': 'Find emails from John about invoice. Also draft a response approving it.',
            'expected_steps': 2
        },
        {
            'description': 'Sheet + Email + Todo',
            'text': 'Create sheet with data. Then email team with link. Plus add reminder to follow up.',
            'expected_steps': 3
        },
        {
            'description': 'Multi-step with context',
            'text': 'Find budget email. Then create sheet from it. Then forward the sheet to accounting.',
            'expected_steps': 3
        },
    ]

    conv_mgr = ConversationManager()

    for example in examples:
        print(f"\n📋 {example['description']}")
        print(f"   Input: {example['text']}")

        steps = conv_mgr._detect_workflow_chain(example['text'])

        if steps and len(steps) == example['expected_steps']:
            print(f"   ✓ Detected {len(steps)} steps:")
            for i, step in enumerate(steps, 1):
                print(f"      {i}. {step}")
        else:
            print(f"   ✗ Expected {example['expected_steps']} steps, got {len(steps) if steps else 0}")

    print("\n" + "=" * 60)


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Workflow Chaining Test Suite")
    print("="*60 + "\n")

    all_passed = True

    # Run tests
    all_passed &= test_workflow_detection()
    all_passed &= test_workflow_splitting()
    all_passed &= test_context_resolution()
    all_passed &= test_sheet_title_generation()

    # Show examples
    test_workflow_examples()

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
    import sys
    sys.exit(main())
