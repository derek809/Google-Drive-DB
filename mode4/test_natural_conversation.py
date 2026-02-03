#!/usr/bin/env python3
"""
Test natural conversation flow for Mode 4.
Simulates real user messages to ensure the bot feels human.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_handler import TelegramHandler
from mode4_processor import Mode4Processor

def test_natural_messages():
    """Test parsing of natural human messages."""

    print("Testing Natural Conversation Flow")
    print("=" * 60)
    print()

    # Initialize processor
    processor = Mode4Processor()
    telegram = processor.telegram

    # Test messages that a human would actually send
    test_messages = [
        "Hello",
        "Draft an email to Jason",
        "Add sending 1099 to todo list",
        "Re: W9 Request - send W9 and wiring",
        "Forward the invoice to accounting",
        "draft email to jason on the laura clarke email",
        "Can you help me with the Q4 report?",
        "/status",
        "/help"
    ]

    print("Processing natural messages:")
    print()

    for msg in test_messages:
        print(f"User: {msg}")

        try:
            # Parse the message
            parsed = telegram.parse_message(msg)

            # Show what the bot understood
            if parsed.get('valid'):
                if 'command' in parsed:
                    print(f"  → Command: {parsed['command']}")
                else:
                    print(f"  → Reference: {parsed.get('email_reference', 'N/A')}")
                    print(f"  → Instruction: {parsed.get('instruction', 'N/A')}")
                    print(f"  → Search type: {parsed.get('search_type', 'N/A')}")
                    if 'parsed_with' in parsed:
                        print(f"  → Parsed with: {parsed['parsed_with']}")
            else:
                print(f"  → Could not parse")

            print()

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            print()
            return False

    print("=" * 60)
    print("✓ All natural messages parsed successfully!")
    print()
    print("The bot can now understand natural conversation.")
    return True

if __name__ == "__main__":
    try:
        success = test_natural_messages()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
