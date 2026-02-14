"""Quick test for the todo intent fix."""
import os, sys
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _d in ["brain","core","core/Infrastructure","core/InputOutput","core/State&Memory","Bot_actions","LLM"]:
    _p = os.path.join(_root, _d)
    if _p not in sys.path: sys.path.insert(0, _p)

from conversation_manager import ConversationManager, Intent

def test_todo_intent():
    """Test that todo requests are correctly identified."""
    conv_mgr = ConversationManager()

    test_cases = [
        ("Add a task to my todo list talk to Eytan about Debbie Lee", Intent.TODO_ADD),
        ("add call sarah to my agenda", Intent.TODO_ADD),
        ("create task for meeting", Intent.TODO_ADD),
        ("remind me to send invoice", Intent.TODO_ADD),
        ("Add a task to my todo list: draft an email to George", Intent.TODO_ADD),  # Task about drafting
        ("Add to my agenda: draft email to jason", Intent.TODO_ADD),  # Task about drafting
        ("draft email to jason", Intent.EMAIL_DRAFT),  # Actually draft (no todo context)
    ]

    print("Testing Todo Intent Classification Fix")
    print("=" * 60)

    for text, expected in test_cases:
        result = conv_mgr.classify_intent(text)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{text[:50]}...' → {result.value} (expected {expected.value})")

    print("\nTesting Multiple Task Splitting")
    print("=" * 60)

    text = "Add a task to my todo list talk to Eytan about Debbie Lee. Another one is to draft something for Geo"
    tasks = conv_mgr._split_multiple_tasks(text)
    print(f"Input: {text}")
    print(f"Split into {len(tasks)} tasks:")
    for i, task in enumerate(tasks, 1):
        print(f"  {i}. {task}")

if __name__ == "__main__":
    test_todo_intent()
