# Advanced Conversational Features - Implementation Guide

## What's Been Implemented

### ✅ 1. Rich Context Memory (30 min)
The bot now remembers:
- **Last email** discussed - reference with "it", "that email", "this one"
- **Last draft** created - reference with "the draft", "that response"
- **Last sheet/file** created
- **Recent tasks** shown (#1, #2, #3)

### ✅ 2. Task References & Execution
**Show your agenda:**
```
You: show my agenda
Bot: 📋 Your Tasks
     1. 🔴 Draft email to George
     2. 🟡 Call Sarah
     3. 🟢 Review budget

     💡 Say '#1' or 'do task 2' to execute a task!
```

**Execute specific tasks:**
```
You: #1
Bot: 📧 Executing: Draft email to George
     Searching for emails from George...
```

or

```
You: do task 2
Bot: ✓ Working on task #2: Call Sarah
```

### ✅ 3. Auto Priority Detection
The bot automatically detects urgency:

**High Priority** (auto-detected):
- "URGENT: call Sarah" → 🔴 High priority
- "IMPORTANT: review contract" → 🔴 High priority
- "ASAP call Jason" → 🔴 High priority
- "!!!" → 🔴 High priority

**Low Priority** (auto-detected):
- "when you get a chance: review doc" → 🟢 Low priority
- "whenever: call John" → 🟢 Low priority
- "someday: clean inbox" → 🟢 Low priority

**Example:**
```
You: Add to agenda: URGENT call Sarah tomorrow
Bot: ✓ Added to your agenda: call Sarah tomorrow
     📅 Due: tomorrow
     ⚡ Priority: high  ← Auto-detected!
```

### ✅ 4. Multiple Task Support (Already Working)
Add multiple tasks at once:
```
You: Add to agenda: call Jason. Another one is to review budget. Plus draft email to George.
Bot: ✓ Added 3 tasks to your agenda:
     • call Jason
     • review budget
     • draft email to George
```

## What's Next to Implement

### ✅ 5. Workflow Chaining (IMPLEMENTED!)
Parse and execute multi-step requests:
```
You: Draft email to Jason. Then create a Google Sheet with columns Name, Email, Status. Then email Sarah saying I created the sheet.

Bot: 📋 Workflow Plan (3 steps)

     1. Draft email to Jason
     2. Create Google Sheet (Name, Email, Status)
     3. Email Sarah saying I created the sheet

     ⚙️ Starting execution...

     ▶️ Step 1/3: Draft email to Jason
     [Searches for emails from Jason with draft options]

     ▶️ Step 2/3: Create Google Sheet with columns Name, Email, Status
     🤖 Using Gemini to extract data from email...
     ✅ Created Google Sheet
     📊 Title: Budget Tracker
     📋 Columns: Name, Email, Status
     🔗 Link: https://docs.google.com/spreadsheets/d/...

     ▶️ Step 3/3: Email Sarah saying I created the sheet
     [Drafts email to Sarah with sheet reference]

     ✅ Workflow complete! Successfully executed 3 steps.
```

**Workflow Connectors Supported:**
- ". then " - Sequential steps
- ". also " - Additional actions
- ". plus " - More tasks
- ". after that " - Sequential continuation
- ". next " - Next action
- " and then " - Continuation

### ✅ 6. Context References (IMPLEMENTED!)
Reference previous items across workflow steps:
```
You: Find email from Jason about budget
Bot: 📧 Email Found
     From: Jason
     Subject: Q4 Budget Review
     [Ollama] [Claude] [Cancel]

You: Draft a response approving it
Bot: [Drafts response to Jason's email] ← knows "it" = budget email

You: Add to my agenda: follow up on that draft next week
Bot: ✓ Added: follow up on [Jason budget draft] next week ← knows "that draft"
```

**Context References Supported:**
- "it" - Last email/draft/sheet
- "that" - Last referenced item
- "this" - Current item
- "the sheet" - Last created sheet
- "the draft" - Last created draft
- "the email" - Last found email

### ✅ 7. Gemini Integration for Sheet Creation (IMPLEMENTED!)
Use Gemini to extract data and create Google Sheets:
```
You: Based on Jason's email, create a Google Sheet with columns for Client, Amount, Status
Bot: 🤖 Using Gemini to extract data from email...
     ✅ Created Google Sheet
     📊 Title: Q4 Budget - Data
     📋 Columns: Client, Amount, Status
     📝 Rows: 5
     🔗 Link: https://docs.google.com/spreadsheets/d/abc123

     Note: Sheet shared with your service account
```

**Gemini Capabilities:**
- Extract structured data from emails
- Identify column headers from context
- Parse tables and lists
- Generate summaries
- Smart data formatting

## How to Use (Available Now)

### Show Tasks with Numbers
```
You: show my agenda
Bot: 📋 Your Tasks
     1. 🔴 Draft email to George
     2. 🟡 Call Sarah
     3. 🟢 Review budget
```

### Execute by Number
```
You: #1
You: do task 2
You: the first one
```

### Auto Priority
```
You: Add to agenda: URGENT call Sarah
You: Add to agenda: when you get a chance review doc
```

### Multiple Tasks
```
You: Add to agenda: call Jason. Another one is review budget
```

## Configuration

Edit `/Users/work/Telgram bot/mode4/m1_config.py`:

```python
# Context timeout (how long bot remembers)
CONVERSATION_CONTEXT_TIMEOUT = 30 * 60  # 30 minutes

# Auto-priority detection (enabled by default)
CONVERSATION_AUTO_PRIORITY = True
```

## Testing

Test the new features:

```bash
cd "/Users/work/Telgram bot/mode4"
python3 test_conversation.py
```

## Examples

### Example 1: Task Reference Workflow
```
You: show my agenda
Bot: 📋 Your Tasks
     1. 🔴 Draft email to George
     2. 🟡 Call Sarah

You: #1
Bot: 📧 Executing: Draft email to George
     Searching for emails from George...
     [Shows email with draft options]
```

### Example 2: Priority Detection
```
You: Add URGENT: call client about payment issue
Bot: ✓ Added to your agenda: call client about payment issue
     ⚡ Priority: high

You: Add when you have time: organize files
Bot: ✓ Added to your agenda: organize files
     ⚡ Priority: low
```

### Example 3: Multiple Tasks
```
You: Add to agenda: draft email to Jason. Another is call Sarah. Plus review budget.
Bot: ✓ Added 3 tasks to your agenda:
     • draft email to Jason
     • call Sarah
     • review budget
```

## Architecture

### Context Storage Structure
```python
context = {
    'last_email': {
        'subject': 'Q4 Budget',
        'sender': 'Jason',
        'thread_id': 'abc123'
    },
    'last_draft': {
        'recipient': 'Jason',
        'subject': 'Re: Q4 Budget',
        'draft_id': 'xyz789'
    },
    'last_tasks': [
        {'number': 1, 'task_id': 1, 'title': 'Draft email to George'},
        {'number': 2, 'task_id': 2, 'title': 'Call Sarah'}
    ],
    'timestamp': 1234567890.0
}
```

### Task Reference Detection
Recognizes:
- `#1`, `#2` - Direct number references
- `task 1`, `do task 2` - Explicit task commands
- `the first one`, `the second one` - Ordinals
- `1st`, `2nd`, `3rd` - Numeric ordinals

### Priority Detection Keywords
**High:** urgent, asap, important, critical, emergency, now, !!!
**Low:** when you get a chance, whenever, low priority, someday, eventually
**Medium:** (default if no keywords detected)

## Next Steps

1. **Test the features** - Try the task references and priority detection
2. **Workflow chaining** - Multi-step task execution
3. **Context references** - "it", "that", "this" understanding
4. **Gemini sheet creation** - Automated Google Sheets from emails
5. **Draft references** - "show me the draft", "send that email"

## Files Modified

- `conversation_manager.py` - Added context storage, task references, priority detection
- `m1_config.py` - Added configuration options
- `CONVERSATION_GUIDE.md` - Updated usage guide

## Troubleshooting

**Task references not working?**
- Make sure you've said "show my agenda" first to populate task references
- References expire after 30 minutes

**Priority not auto-detected?**
- Check for keywords like "URGENT", "when you get a chance"
- Can still manually set with QuickCapture syntax

**Context not remembered?**
- Context expires after 30 minutes of inactivity
- Check `CONVERSATION_CONTEXT_TIMEOUT` in config
