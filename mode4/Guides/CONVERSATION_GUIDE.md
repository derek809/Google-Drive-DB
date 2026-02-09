# Conversational Interface Guide

## Overview

Mode 4 now has a natural conversational interface! You can talk to your assistant naturally instead of using rigid formats.

## How to Use

### Greetings
Just say hi!
```
You: hi
Bot: Hey! What can I help you with today? I can draft emails, manage your todos, fetch files, or give you a morning brief.
```

### Email Drafting
Natural language works:
```
You: draft email to jason about the invoice
Bot: 🔍 Searching for emails from jason about invoice...
```

Legacy format still works:
```
You: Re: Q4 Budget - approve the numbers
Bot: 🔍 Searching for email: Q4 Budget...
```

### Todo Management
Add tasks naturally:
```
You: add call sarah tomorrow to my todo list
Bot: ✓ Added to your todo list: Call sarah
     📅 Due: tomorrow
```

View your tasks:
```
You: show my todos
Bot: 📋 Your Tasks
     🔴 Call sarah
        📅 tomorrow
        /task_done 1
```

### Information Requests
Morning brief:
```
You: morning brief
Bot: [Shows email summary with categories]
```

System status:
```
You: status
Bot: System Status:
     Ollama: OK
     Gmail: Configured
```

### Help
```
You: help
Bot: I can help you with:
     • Email drafts - "draft email to [person]"
     • Todo management - "add [task] to my list"
     • Morning digest - "show my emails"
     ...
```

### Casual Chat
```
You: how are you
Bot: I'm doing great! How can I help you today?

You: what's up
Bot: All systems running smoothly! What do you need?
```

## Intent Detection

The bot automatically detects what you want:

| Intent | Examples |
|--------|----------|
| **Greeting** | "hi", "hello", "hey" |
| **Help** | "help", "what can you do" |
| **Email Draft** | "draft email to X", "write to Y" |
| **Email Search** | "find emails from X" |
| **Todo Add** | "add X to todo", "remind me to Y" |
| **Todo List** | "show my todos", "list tasks" |
| **Info Digest** | "morning brief", "email summary" |
| **Status** | "status", "system status" |
| **Casual** | "how are you", "what's up" |

## Backward Compatibility

All existing formats still work:
- `Re: [subject] - [instruction]`
- `From [sender] - [instruction]`
- `latest from [sender] - [instruction]`
- `/command [args]`

## Configuration

Edit `/Users/work/Telgram bot/mode4/m1_config.py`:

```python
# Enable/disable conversational interface
CONVERSATION_ENABLED = True

# Context timeout (how long bot remembers conversation)
CONVERSATION_CONTEXT_TIMEOUT = 30 * 60  # 30 minutes

# Response style
CONVERSATION_GREETING_STYLE = "friendly"  # friendly, brief, personality
```

## Examples

### Example 1: Morning Routine
```
You: morning brief
Bot: [Shows email summary]

You: draft email to the first one
Bot: [Searches and shows email with draft options]
```

### Example 2: Quick Task
```
You: remind me to call john tomorrow at 2pm
Bot: ✓ Added: Call john - Tomorrow at 2pm (High priority)
```

### Example 3: Email Workflow
```
You: find emails from sarah about budget
Bot: 📧 Email Found
     From: Sarah Johnson
     Subject: Q4 Budget Review
     [Ollama] [Claude] [Cancel]
```

## Testing

Run the test suite:
```bash
cd "/Users/work/Telgram bot/mode4"
python3 test_conversation.py
```

All tests should pass:
```
Testing Intent Classification
============================================================
✓ 28 passed, 0 failed

Testing Legacy Format Detection
============================================================
✓ 4 passed, 0 failed

✓ ALL TESTS PASSED
```

## Troubleshooting

### Intent not detected correctly
The bot uses a hybrid approach:
1. **Rule-based** (fast) - checks for obvious keywords
2. **LLM-based** (smart) - uses Ollama for complex cases

If Ollama is not running, it falls back to rules only.

### Bot not responding to greetings
1. Check that conversation manager is enabled in config
2. Check that Telegram bot is running
3. Look at logs for errors

### Legacy format broken
The conversational layer sits on top - it never breaks existing formats. If legacy format stops working, check telegram_handler logs.

## Architecture

```
Telegram Message
    ↓
ConversationManager (NEW)
    ├─ Intent Classification (LLM + rules)
    ├─ Greeting → Direct response
    ├─ Email → Route to existing email processor
    ├─ Todo → Route to TodoManager
    ├─ Info → Route to DailyDigest/FileFetcher
    └─ Unclear → Ask for clarification
    ↓
Existing Capabilities (email, todos, digest, etc.)
```

## Features

✅ Natural language understanding
✅ Intent classification
✅ Friendly responses
✅ Context memory (30 min)
✅ Smart routing to capabilities
✅ 100% backward compatible
✅ Fast response (<500ms)
✅ Graceful fallbacks

## Future Enhancements

Potential future additions:
- Multi-turn conversations
- User preference learning
- Voice input support
- Proactive suggestions ("You haven't replied to Jason in 3 days")
- Smart follow-ups ("Shall I add that to your todo list?")
