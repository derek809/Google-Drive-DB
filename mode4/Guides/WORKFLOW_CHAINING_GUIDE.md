# Workflow Chaining Guide

## Overview

Workflow chaining allows you to execute multi-step tasks in a single command. The bot will parse your request, break it into steps, execute them sequentially, and pass context between steps.

## How It Works

### Detection

The bot automatically detects workflow chains when you use connectors like:
- `. then ` - Sequential steps
- `. also ` - Additional actions
- `. plus ` - More tasks
- `. after that ` - Sequential continuation
- `. next ` - Next action
- ` and then ` - Continuation

### Execution

When a workflow is detected:
1. Bot shows you the plan (all steps listed)
2. Executes each step sequentially
3. Passes context from one step to the next
4. Shows progress for each step
5. Notifies on completion or errors

### Context Passing

Each step can reference results from previous steps using:
- **"it"** - Last email/draft/sheet
- **"that"** - Last referenced item
- **"this"** - Current item
- **"the sheet"** - Last created sheet
- **"the draft"** - Last created draft
- **"the email"** - Last found email

## Examples

### Example 1: Email + Sheet + Notify

**Input:**
```
Draft email to Jason about budget. Then create a Google Sheet with columns Client, Amount, Status. Then email Sarah saying I created the sheet.
```

**Output:**
```
📋 Workflow Plan (3 steps)

1. Draft email to Jason about budget
2. Create Google Sheet with columns Client, Amount, Status
3. Email Sarah saying I created the sheet

⚙️ Starting execution...

▶️ Step 1/3: Draft email to Jason about budget
🔍 Searching for emails from jason about budget...
📧 Email Found
   From: Jason Smith <jason@company.com>
   Subject: Q4 Budget Review
   [Ollama] [Claude] [Cancel]

▶️ Step 2/3: Create Google Sheet with columns Client, Amount, Status
🤖 Using Gemini to extract data from email...
✅ Created Google Sheet
📊 Title: Q4 Budget Review - Data
📋 Columns: Client, Amount, Status
📝 Rows: 3
🔗 Link: https://docs.google.com/spreadsheets/d/abc123

▶️ Step 3/3: Email Sarah saying I created the sheet
🔍 Searching for emails from sarah...
📧 Drafting to: Sarah Johnson
💡 Context: Sheet 'Q4 Budget Review - Data'
[Draft composed with sheet reference]

✅ Workflow complete! Successfully executed 3 steps.
```

### Example 2: Search + Respond

**Input:**
```
Find emails from John about invoice. Also draft a response approving it.
```

**Output:**
```
📋 Workflow Plan (2 steps)

1. Find emails from John about invoice
2. Draft a response approving it

⚙️ Starting execution...

▶️ Step 1/2: Find emails from John about invoice
🔍 Searching for emails from john about invoice...
📧 Email Found
   From: John Doe <john@vendor.com>
   Subject: Invoice #1234 - Payment Due
   [View] [Draft Response] [Archive]

▶️ Step 2/2: Draft a response approving it
📧 Drafting response to John about Invoice #1234
💡 Context: Approving the invoice
[Draft composed: "Hi John, Invoice approved..."]

✅ Workflow complete! Successfully executed 2 steps.
```

### Example 3: Multi-step with Context References

**Input:**
```
Find budget email. Then create sheet from it. Then forward the sheet to accounting.
```

**Output:**
```
📋 Workflow Plan (3 steps)

1. Find budget email
2. Create sheet from it
3. Forward the sheet to accounting

⚙️ Starting execution...

▶️ Step 1/3: Find budget email
🔍 Searching for emails about budget...
📧 Email Found
   From: Finance Team
   Subject: Q4 Budget Breakdown
   [Context stored: last_email]

▶️ Step 2/3: Create sheet from it
💡 Resolved: "it" → email from Finance Team
🤖 Using Gemini to extract data from email...
✅ Created Google Sheet
📊 Title: Q4 Budget Breakdown - Data
[Context stored: last_sheet]

▶️ Step 3/3: Forward the sheet to accounting
💡 Resolved: "the sheet" → Q4 Budget Breakdown - Data
📧 Drafting email to accounting with sheet link
[Draft composed with sheet reference]

✅ Workflow complete! Successfully executed 3 steps.
```

### Example 4: Task + Reminder + Email

**Input:**
```
Add task to call Sarah. Then remind me tomorrow at 2pm. Plus email her saying I'll call.
```

**Output:**
```
📋 Workflow Plan (3 steps)

1. Add task to call Sarah
2. Remind me tomorrow at 2pm
3. Email her saying I'll call

⚙️ Starting execution...

▶️ Step 1/3: Add task to call Sarah
✓ Added to your agenda: Call Sarah
   📅 Due: today
   ⚡ Priority: medium

▶️ Step 2/3: Remind me tomorrow at 2pm
✓ Added to your agenda: Call Sarah (Reminder)
   📅 Due: tomorrow at 2pm
   ⚡ Priority: high

▶️ Step 3/3: Email her saying I'll call
💡 Context: Sarah (from task)
🔍 Searching for emails from sarah...
📧 Drafting to: Sarah Johnson
[Draft composed: "Hi Sarah, I'll call you tomorrow..."]

✅ Workflow complete! Successfully executed 3 steps.
```

## Gemini Integration

### How Gemini Helps

When you ask to create a Google Sheet in a workflow, Gemini:
1. Analyzes the context (email, previous steps)
2. Extracts relevant data
3. Structures it for the sheet
4. Identifies column headers
5. Formats the data appropriately

### Example with Gemini

**Input:**
```
Find AP Aging report email. Then create a Google Sheet with client data from it.
```

**Gemini Process:**
1. Email found: "AP Aging Report - January 2024"
2. Gemini analyzes email body
3. Identifies table with: Client Name, Amount Due, Days Overdue
4. Extracts 15 rows of data
5. Creates sheet with extracted data

**Result:**
```
✅ Created Google Sheet
📊 Title: AP Aging Report - January 2024 - Data
📋 Columns: Client Name, Amount Due, Days Overdue
📝 Rows: 15
🔗 Link: https://docs.google.com/spreadsheets/d/xyz789

Data extracted by Gemini:
- ACME Corp, $5,200, 15 days
- Globex Inc, $12,500, 45 days
- ... (13 more rows)
```

## Advanced Features

### Context Chaining

Context flows through steps automatically:

```
You: Find invoice email. Then create sheet. Then email client about the sheet.

Step 1: Finds invoice → stores as last_email
Step 2: Creates sheet from last_email → stores as last_sheet
Step 3: Emails client about last_sheet
```

### Smart References

The bot understands various reference forms:

- "it" → last item
- "that" → last referenced
- "this one" → current item
- "the [type]" → last of that type

### Error Handling

If a step fails:
```
❌ Step 2 failed: Could not find email from Jason

Stopping workflow.
Steps completed: 1/3
```

You can then:
- Retry the workflow
- Fix the issue and run remaining steps
- Start a new workflow

## Tips

### 1. Be Specific

**Good:**
```
Draft email to Jason about Q4 budget. Then create sheet with columns Revenue, Expenses, Profit.
```

**Vague:**
```
Email Jason. Then make a sheet.
```

### 2. Use Context

**Good:**
```
Find budget email. Then create sheet from it. Then send the sheet to team.
```

**Bad:**
```
Find budget email. Then create budget sheet. Then send budget sheet to team.
```

### 3. Logical Order

**Good:**
```
Find email. Then draft response. Then add follow-up task.
```

**Awkward:**
```
Add follow-up task. Then find email. Then draft response.
```

### 4. Explicit Columns

**Good:**
```
Create sheet with columns Name, Email, Phone, Status
```

**Less clear:**
```
Create sheet with contact info
```

## Testing

Test workflow chaining:

```bash
cd "/Users/work/Telgram bot/mode4"
python3 test_workflow_chaining.py
```

All tests should pass:
```
Testing Workflow Detection
============================================================
✓ 10 passed, 0 failed

Testing Workflow Splitting
============================================================
✓ 3 passed, 0 failed

Testing Context Resolution
============================================================
✓ 3 passed, 0 failed

Testing Sheet Title Generation
============================================================
✓ 4 passed, 0 failed

✓ ALL TESTS PASSED
```

## Configuration

Edit `/Users/work/Telgram bot/mode4/m1_config.py`:

```python
# Workflow chaining (enabled by default)
WORKFLOW_CHAINING_ENABLED = True

# Max steps per workflow
WORKFLOW_MAX_STEPS = 5

# Context timeout (shared with conversation)
CONVERSATION_CONTEXT_TIMEOUT = 30 * 60  # 30 minutes
```

## Troubleshooting

### Workflow Not Detected

**Problem:** Single-step request processed instead of workflow

**Solution:** Use explicit connectors
```
❌ "Draft email to Jason, create sheet"
✓ "Draft email to Jason. Then create sheet"
```

### Context Not Passed

**Problem:** Step doesn't have context from previous step

**Solution:** Use explicit references
```
❌ "Find email. Create sheet with data."
✓ "Find email. Then create sheet from it."
```

### Gemini Not Extracting Data

**Problem:** Sheet created but empty

**Possible causes:**
1. Email doesn't contain structured data
2. Gemini API key not configured
3. Email format not recognizable

**Solution:** Check logs, verify Gemini setup

### Step Fails

**Problem:** Workflow stops mid-execution

**Solution:**
1. Check error message
2. Fix the issue
3. Re-run the workflow
4. Or run remaining steps manually

## Examples Library

### Business Workflows

```
# Invoice Processing
Find invoice from Acme Corp. Then create sheet with items and amounts. Then email accounting with the sheet.

# Meeting Prep
Find emails from Sarah about project. Then create summary sheet. Then email team with agenda.

# Report Generation
Search for sales data emails. Then create sheet with quarterly numbers. Then draft report email.
```

### Personal Productivity

```
# Morning Routine
Show unread emails. Then create todo list from urgent ones. Then send daily summary to myself.

# Follow-up Tracking
Find emails needing response. Then add follow-up tasks. Then create tracking sheet.

# Weekly Planning
Search for this week's tasks. Then create priority sheet. Then email myself the plan.
```

### Data Management

```
# Consolidation
Find budget emails. Then create master sheet. Then share with finance team.

# Archive & Organize
Search for old invoices. Then create archive sheet. Then mark emails as processed.

# Client Tracking
Find client communications. Then create status sheet. Then add follow-up reminders.
```

## What's Next

Future enhancements:
- Conditional steps ("if email found, then...")
- Parallel execution ("do A and B simultaneously")
- Loop support ("for each email, create sheet")
- Template workflows ("run my weekly report workflow")
- Workflow history and replay

## Support

Issues? Questions?

1. Check logs: `/Users/work/Telgram bot/mode4/logs/`
2. Run tests: `python3 test_workflow_chaining.py`
3. Check context: Context expires after 30 minutes
4. Verify integrations: Gemini API, Google Sheets API

Report bugs at: https://github.com/anthropics/claude-code/issues
