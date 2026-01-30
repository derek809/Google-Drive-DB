# MCP Email Processor - User Guide

## Overview

Your MCP system has two modes of operation:

1. **Google Apps Script Mode** - Batch processing via Google Sheets (ready now)
2. **Claude Desktop Mode** - Interactive processing (future, requires MCP server)

---

## Mode 1: Google Apps Script (Batch Processing)

### When to Use
- Processing multiple emails at once
- End-of-day email cleanup
- When you want drafts created automatically in Gmail

### Setup (One-Time)
1. Go to [script.google.com](https://script.google.com)
2. Create new project "MCP Email Processor"
3. Create 6 files, copy content from `AppsScript/` folder:
   - `1_Config.gs`
   - `2_Sheets.gs`
   - `3_Patterns.gs`
   - `4_Queue.gs`
   - `5_Processing.gs`
   - `6_Utils.gs`
4. Run `setupMCP()` function
5. Set API keys from menu: **MCP Queue > API Keys**

### Daily Workflow

#### Step 1: Label Emails
In Gmail, add the `[MCP]` label to emails you want processed.

#### Step 2: Populate Queue
In Google Sheets:
- **MCP Queue > Populate from Emails**
- Emails appear in the MCP sheet (columns A-H)

#### Step 3: Add Instructions
For each email in the queue:
- Fill in **Column C (Prompt)** with what you want done
- Examples:
  - "Send W9 and wiring instructions"
  - "Confirm payment received, check NetSuite"
  - "Loop in Eytan for guidance"
  - "Draft polite decline"

#### Step 4: Configure Options
- **Column D (Gemini?)** - Check if you need data fetched from Drive/Sheets
- **Column E (Ready?)** - Check when ready to process

#### Step 5: Process
- **MCP Queue > Process Ready Items**
- Claude processes each checked item
- Gmail drafts are created automatically
- Results stored in cell notes (right-click Prompt cell)

#### Step 6: Review & Send
- Open Gmail Drafts folder
- Review each draft Claude created
- Edit if needed, then send

#### Step 7: Archive
- **MCP Queue > Archive Completed**
- Moves done items to History sheet

### Learning Loop
After sending emails:
- **MCP Queue > Trigger Learning**
- System compares drafts to what you actually sent
- Updates pattern success rates
- Learns contact preferences

### Menu Reference

| Menu Item | What It Does |
|-----------|--------------|
| Run Setup | Creates sheets and Gmail labels |
| Add Manual Task | Add non-email task to queue |
| Populate from Emails | Pull [MCP] labeled emails into queue |
| Process Ready Items | Run Claude on checked items, create drafts |
| Archive Completed | Move done items to History |
| Trigger Learning | Learn from sent emails |
| Show Stats | Display queue and learning statistics |

---

## Mode 2: Claude Desktop (Interactive - Future)

### When to Use
- Real-time email processing
- When you want to iterate on a response
- Complex emails requiring back-and-forth

### Status
**Not yet implemented.** Requires MCP server setup.

### How It Would Work (Future)
1. Copy email content to Claude Desktop
2. Tell Claude: "Process this email, send W9"
3. Claude uses MCP tools to:
   - Match patterns from your database
   - Calculate confidence
   - Generate draft using templates
4. You review and edit in conversation
5. Tell Claude what you changed
6. System learns from your edits

### To Enable (Future Steps)
1. Create `mcp_server.py` with MCP protocol support
2. Configure Claude Desktop to use the server
3. Server connects to `mcp_learning.db`

---

## Sheet Structure

### MCP Sheet (Main)
```
Columns A-H: Queue
  A: Source (Email/Manual)
  B: Subject/Task
  C: Prompt (your instructions)
  D: Gemini? (checkbox)
  E: Ready? (checkbox)
  F: Status (Pending/Processing/Done/Error)
  G: Email ID (hidden)
  H: Date Added

Column I: Separator

Columns J-O: Patterns (editable!)
  J: Pattern Name
  K: Keywords (comma-separated)
  L: Confidence Boost (+%)
  M: Usage Count (auto-updated)
  N: Success Rate (auto-updated)
  O: Notes
```

### Templates Sheet
```
  A: Template ID
  B: Template Name
  C: Template Body (use {variable} syntax)
  D: Variables (comma-separated)
  E: Attachments
  F: Usage Count
```

### Contacts Sheet
```
  A: Email
  B: Name
  C: Relationship
  D: Preferred Tone (learned)
  E: Common Topics (learned)
  F: Interactions (count)
  G: Last Contact
```

### History Sheet
Same structure as Queue (A-H), stores archived items.

---

## Patterns Reference

| Pattern | Keywords | Boost | Use When |
|---------|----------|-------|----------|
| invoice_processing | invoice, fees, mgmt, Q3, Q4, quarterly | +15% | Invoice or fee requests |
| w9_wiring_request | w9, w-9, wiring instructions, wire details | +20% | W9 or wire info requests |
| payment_confirmation | payment, wire, received, OCS Payment | +15% | Confirming payments |
| producer_statements | producer statements, producer report | +10% | Producer report requests |
| delegation_eytan | insufficient info, not sure, need eytan | +0% | Need Eytan's input |
| turnaround_expectation | how long, timeline, when, deadline | +5% | Timeline questions |
| journal_entry_reminder | JE, journal entry, partner compensation | +0% | Journal entry tasks |

**To add a new pattern:** Just add a row in columns J-O of the MCP sheet!

---

## Templates Reference

| Template | Variables | When to Use |
|----------|-----------|-------------|
| w9_response | {name}, {wiring_details} | Responding to W9/wiring requests |
| payment_confirmation | {name}, {amount}, {date} | Confirming payment received |
| delegation_eytan | {name}, {context} | Looping in Eytan |
| turnaround_time | {name}, {request_type}, {timeline}, {specific_date} | Setting timeline expectations |

**To add a new template:** Just add a row in the Templates sheet!

---

## Tips

### Writing Good Prompts
Be specific about what you want:
- "Send W9 and wiring instructions" ✓
- "Reply to email" ✗ (too vague)
- "Confirm payment, mention NetSuite reference #12345" ✓
- "Handle this" ✗ (too vague)

### When to Use Gemini
Check the Gemini box when you need:
- Data from a Google Sheet
- Information from a Google Doc
- Numbers or dates that need to be looked up

### Confidence Scores
- **70%+** - High confidence, draft likely good as-is
- **50-70%** - Medium confidence, review carefully
- **Below 50%** - Low confidence, expect to edit significantly

### Learning Over Time
The system improves as you use it:
- Pattern usage counts help prioritize matches
- Success rates track which patterns work best
- Contact preferences learned from your edits
- The more you use it, the better it gets

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No emails appearing | Check Gmail has [MCP] label applied |
| API errors | Verify API keys set in MCP Queue > API Keys |
| Drafts not created | Check email has valid sender address |
| Pattern not matching | Add keywords to pattern in column K |
| Wrong template used | Update pattern notes in column O |

---

## File Locations

```
Google Drive DB/
├── AppsScript/           # Google Apps Script files
│   ├── 1_Config.gs
│   ├── 2_Sheets.gs
│   ├── 3_Patterns.gs
│   ├── 4_Queue.gs
│   ├── 5_Processing.gs
│   └── 6_Utils.gs
├── mcp_learning.db       # SQLite database (source of truth)
├── orchestrator.py       # Python orchestrator
├── mcp_api_server.py     # Flask API server
└── MCP_USER_GUIDE.md     # This file
```
