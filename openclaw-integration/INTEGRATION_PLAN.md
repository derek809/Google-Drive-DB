# OpenClaw ↔ Work Bot Integration Plan

**Branch:** `claude/openclaw-work-bot-integration-8B2Ou`
**Date:** 2026-02-21
**Status:** Ready to implement

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Skill Mapping — What the Work Bot Can Do](#2-skill-mapping)
3. [File Protocol — Inbox/Outbox Schemas](#3-file-protocol)
4. [Task Translation — How OpenClaw Formats Tasks](#4-task-translation)
5. [Decision Logic — When to Delegate vs Handle Directly](#5-decision-logic)
6. [FAILURE HANDLING — Complete Escalation Flows](#6-failure-handling)
7. [OpenClaw Configuration](#7-openclaw-configuration)
8. [Bridge Code Overview](#8-bridge-code)
9. [Scenario Walkthroughs (5 Cases)](#9-scenario-walkthroughs)
10. [Decision Tree Diagram](#10-decision-tree-diagram)
11. [Implementation Checklist](#11-implementation-checklist)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           YOU (Human)                               │
│                    Telegram / Chat Interface                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ approve / decline / feedback
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        OPENCLAW                                      │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │ Job Monitor  │   │  Decision Engine │   │  Minimax (complex) │  │
│  │ (email/alert)│   │  Ollama (simple) │   │  (fallback/reason) │  │
│  └──────┬───────┘   └────────┬─────────┘   └────────────────────┘  │
│         │                    │                                       │
│         └──────────┬─────────┘                                       │
│                    ▼                                                  │
│            ┌───────────────┐                                          │
│            │ File Bridge   │                                          │
│            │ inbox/outbox  │                                          │
│            └───────┬───────┘                                          │
└────────────────────┼────────────────────────────────────────────────┘
                     │ JSON task files
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       WORK BOT (bridge.py)                          │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Skill Dispatcher                                            │    │
│  │  • Email (Gmail API)          • Ideas (Master Doc)         │    │
│  │  • Tasks (Google Sheets)      • Workflows (multi-step)     │    │
│  │  • Files (Google Drive)       • Digests / Status           │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  External services: Gmail · Sheets · Docs · Drive · Ollama · Claude│
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

- **OpenClaw is the manager.** It never acts without you approving first (for new jobs).
- **Work Bot is the worker.** It executes using its existing skill infrastructure.
- **Communication is file-based.** No HTTP servers needed — just a shared directory.
- **Failures are first-class.** Every failure type has a defined escalation path.

---

## 2. Skill Mapping

### 2.1 Email Skills

| Skill | Description | Required Params | Risk |
|-------|-------------|-----------------|------|
| `draft_email_reply` | Find an email and create a Gmail draft reply | `email_search_query` | Medium |
| `search_email` | Search Gmail for matching emails | `query` | Low |
| `summarize_thread` | Summarize an email thread | `email_search_query` | Low |
| `forward_email` | Forward an email to a recipient | `email_search_query`, `to_address` | **High** |
| `extract_contacts` | Pull contact info from thread | `email_search_query` | Low |
| `handle_w9_request` | Respond to W9 request with template | `email_search_query` | Medium |

**Note:** Work Bot creates **drafts only** — it does NOT auto-send emails. Human review required.

### 2.2 Task Management Skills

| Skill | Description | Required Params | Risk |
|-------|-------------|-----------------|------|
| `add_task` | Add task to Google Sheets to-do list | `title` | Low |
| `list_tasks` | List pending tasks sorted by priority | — | Low |
| `complete_task` | Mark a task as done | `task_identifier` | Medium |
| `delete_task` | Delete a task | `task_identifier` | **High** |
| `update_task` | Change priority/deadline | `task_identifier` | Medium |
| `view_task_history` | Show recently completed tasks | — | Low |

### 2.3 Idea / Knowledge Skills

| Skill | Description | Required Params | Risk |
|-------|-------------|-----------------|------|
| `capture_idea` | Save idea to Master Doc + extract actions | `idea_text` | Low |
| `brainstorm` | Start interactive brainstorming session | `topic` | Low |
| `save_to_master_doc` | Append content to Google Doc | `content` | Low |
| `extract_action_items` | Extract tasks from unstructured text | `text` | Low |
| `search_skills` | Search saved knowledge base | `query` | Low |
| `finalize_idea_session` | Complete a brainstorming session | — | Low |

### 2.4 Information / Digest Skills

| Skill | Description | Required Params | Risk |
|-------|-------------|-----------------|------|
| `daily_digest` | Morning summary (emails + tasks) | — | Low |
| `on_demand_digest` | Current snapshot summary | — | Low |
| `system_status` | Health check of all services | — | Low |
| `get_template` | Retrieve named response template | `template_name` | Low |

### 2.5 Workflow Skills (Multi-step)

| Skill | Description | Steps |
|-------|-------------|-------|
| `process_invoice_workflow` | Invoice: find → extract → draft confirmation | 3 |
| `idea_to_execution_workflow` | Idea: capture → save → create tasks | 3 |
| `w9_fulfillment_workflow` | W9: find request → draft response | 2 |

### 2.6 File Skills

| Skill | Description | Required Params | Risk |
|-------|-------------|-----------------|------|
| `fetch_google_drive_file` | Find and retrieve a Drive file | `file_query` | Low |

---

## 3. File Protocol

### 3.1 Directory Structure

```
/shared/                        # Shared between OpenClaw and Work Bot
├── inbox/                      # OpenClaw drops tasks here
│   ├── task_<uuid>.json        # Pending task
│   ├── task_<uuid>.lock        # Lock file (prevents double-processing)
│   ├── processed/              # Archived after successful pickup
│   └── failed/                 # Archived if bridge crashed parsing it
└── outbox/                     # Work Bot writes results here
    └── result_<uuid>.json      # One result per task (UUID matches task)
```

### 3.2 Task File (inbox/task_*.json)

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-02-21T09:15:00Z",
  "source": "openclaw",
  "skill": "draft_email_reply",
  "parameters": {
    "email_search_query": "from:client@acme.com subject:invoice subject:March",
    "reply_tone": "professional",
    "reply_instructions": "Confirm receipt and say we will process within 3 business days"
  },
  "context": {
    "user_intent_raw": "Reply to Acme's March invoice email",
    "job_source": "email",
    "prior_task_ids": []
  },
  "timeout_seconds": 300,
  "priority": "normal",
  "retry_attempt": 0
}
```

### 3.3 Result File (outbox/result_*.json)

#### Success:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-02-21T09:15:47Z",
  "source": "workbot",
  "status": "success",
  "skill_used": "draft_email_reply",
  "confidence": 0.95,
  "duration_ms": 4720,
  "result": {
    "summary": "Draft created for email: 'March Invoice #1042'",
    "data": {
      "email_subject": "March Invoice #1042",
      "draft_text": "Dear Acme team, Thank you for sending over Invoice #1042..."
    },
    "artifacts": [
      {
        "type": "gmail_draft_id",
        "value": "r-8432098xyz",
        "label": "Gmail Draft ID"
      }
    ]
  }
}
```

#### Unknown Skill:
```json
{
  "task_id": "...",
  "status": "unknown_skill",
  "unknown_skill_info": {
    "requested_skill": "schedule_meeting",
    "available_skills": ["draft_email_reply", "add_task", ...],
    "closest_match": "add_task",
    "decomposition_hint": "Try: add_task with title='Schedule meeting with X on DATE'"
  }
}
```

#### Execution Failure:
```json
{
  "task_id": "...",
  "status": "failed",
  "skill_used": "draft_email_reply",
  "error": {
    "error_type": "not_found",
    "message": "No email found matching: from:client@acme.com subject:invoice March",
    "retryable": false,
    "suggested_fix": "Try a broader query: subject:invoice OR from:acme.com"
  }
}
```

#### Partial Success:
```json
{
  "task_id": "...",
  "status": "partial",
  "skill_used": "process_invoice_workflow",
  "partial_results": {
    "completed_steps": ["find_invoice_email", "extract_invoice_data"],
    "failed_steps": [
      {"step": "create_draft_reply", "reason": "Claude API rate limit hit"}
    ],
    "resumable": true,
    "resume_context": {
      "email_id": "18abc123",
      "invoice_data": {"number": "1042", "amount": "$3,400", "due": "2026-03-15"}
    }
  }
}
```

### 3.4 File Naming Convention

```
inbox:  task_{uuid4}.json
outbox: result_{uuid4}.json  (uuid4 matches the task's task_id)
```

OpenClaw knows which result belongs to which task because the UUIDs match exactly.

---

## 4. Task Translation

### 4.1 How OpenClaw Should Format Tasks

OpenClaw receives raw user/alert input and must translate it into a structured Work Bot task. This is the job of OpenClaw's Ollama (for simple cases) or Minimax (for complex ones).

**Translation prompt for Ollama:**

```
Given this user request: "{user_request}"
And these available Work Bot skills: {skill_list}

Output a JSON object with:
- skill: the best matching skill name
- parameters: the required and optional parameters
- confidence: 0.0-1.0

Rules:
- If unsure, output confidence < 0.5 and use Minimax to decide
- If no skill matches, set skill to "NONE" and explain why
```

### 4.2 Translation Examples

| User/Alert Input | OpenClaw Translates To |
|-----------------|------------------------|
| "Reply to Acme's invoice email" | `draft_email_reply` + `email_search_query: "from:acme subject:invoice"` |
| "What's on my to-do list?" | `list_tasks` |
| "Add task: call Dave about contract" | `add_task` + `title: "Call Dave about contract"` |
| "Summarize the thread with Sarah" | `summarize_thread` + `email_search_query: "from:sarah"` |
| "Get me the Q1 budget spreadsheet" | `fetch_google_drive_file` + `file_query: "Q1 budget"` |
| "Handle that W9 request from AWS" | `handle_w9_request` + `email_search_query: "from:aws W9"` |

### 4.3 Parameters OpenClaw Must Infer

For `draft_email_reply`, OpenClaw must translate natural language into Gmail search syntax:

```
"Reply to John's email about the contract"
→ email_search_query: "from:john subject:contract"

"Reply to the email I got yesterday about invoices"
→ email_search_query: "subject:invoice newer_than:2d"

"Reply to Acme Corp about the W9"
→ email_search_query: "from:acme W9"
```

---

## 5. Decision Logic

### 5.1 OpenClaw Routing Decision Tree

```
New job arrives (email / alert / scheduled)
         │
         ▼
   [Ollama] Classify: Is this something Work Bot can handle?
         │
    ┌────┴────┐
   YES        NO
    │          │
    ▼          ▼
 Confidence?  Can Minimax handle it?
    │          │
  ≥0.7        YES → Minimax handles directly
    │          NO  → Ask user
    ▼
 Ask user: "Job X available. Delegate to Work Bot?"
    │
  User: YES
    │
    ▼
 Send to Work Bot via inbox/
    │
    ▼
 Poll outbox/ for result
    │
    ▼
 Report to user: "Done. Details: ..."
```

### 5.2 Delegation Thresholds

| Condition | Action |
|-----------|--------|
| Ollama confidence ≥ 0.7, skill known | Delegate to Work Bot |
| Ollama confidence 0.5–0.7 | Ask user to confirm before delegating |
| Ollama confidence < 0.5 | Use Minimax to classify, then decide |
| Skill is high-risk (`forward_email`, `delete_task`) | Always ask user first |
| Job matches a known workflow | Use workflow skill |
| No matching skill found | Minimax: decompose OR handle itself OR ask user |

---

## 6. FAILURE HANDLING

This is the most critical section. Every failure type has a defined path.

### 6.1 Failure Type Matrix

| Failure Type | Work Bot Reports | OpenClaw First Action | OpenClaw Fallback | Final Fallback |
|-------------|-----------------|----------------------|-------------------|----------------|
| Unknown skill | `status: "unknown_skill"` | Try decomposition | Minimax attempts it | Ask user |
| Execution error (retryable) | `status: "failed"`, `retryable: true` | Wait + retry (max 2x) | Minimax attempts it | Ask user |
| Execution error (not retryable) | `status: "failed"`, `retryable: false` | Minimax attempts it | Ask user | — |
| Timeout (no response) | _(detected by OpenClaw)_ | Send cancel + wait 30s | Minimax attempts it | Ask user |
| Partial success (resumable) | `status: "partial"`, `resumable: true` | Resume via Work Bot | Minimax completes remaining | Ask user |
| Partial success (not resumable) | `status: "partial"`, `resumable: false` | Report completed + Minimax for rest | Ask user | — |

---

### 6.2 Failure Type 1: Unknown Skill

**What happened:** OpenClaw sent a skill name that Work Bot doesn't recognize.

**Work Bot response:**
```json
{
  "status": "unknown_skill",
  "unknown_skill_info": {
    "requested_skill": "schedule_meeting",
    "available_skills": ["add_task", "draft_email_reply", ...],
    "closest_match": "add_task",
    "decomposition_hint": "Use add_task with title='Schedule meeting with X on DATE'"
  }
}
```

**OpenClaw escalation flow:**

```
1. Read decomposition_hint from result
2. [Ollama] Can we reformulate using available_skills?
   YES → Remap to closest skill → Retry with new task file
   NO  → Go to step 3

3. [Minimax] "The user wants to: {original_request}
              Work Bot can't do: {requested_skill}
              It CAN do: {available_skills}
              Can you decompose this into available skills, or handle it yourself?"

   Option A: Minimax decomposes → Send individual tasks to Work Bot
   Option B: Minimax handles directly → No Work Bot involvement
   Option C: Neither → Ask user:
             "Work Bot can't do '{task}'. Want me to:
              A) Break it into smaller steps it can handle
              B) Handle it myself (using AI)
              C) Skip this job"
```

**Skill Gap Learning:**
When `unknown_skill` occurs for the same skill 3+ times, OpenClaw should:
1. Log to `USER.md` in its memory: "Work Bot lacks skill: {requested_skill}"
2. Suggest to user: "Should I generate code to add this skill to Work Bot?"
3. If user says yes → Minimax generates a new bridge handler → adds to `bridge.py`

---

### 6.3 Failure Type 2: Execution Error

**Subtypes and handling:**

#### 2a. Not Found (e.g., email doesn't exist)
```json
{
  "status": "failed",
  "error": {
    "error_type": "not_found",
    "retryable": false,
    "suggested_fix": "Try broader search: subject:invoice"
  }
}
```
**Flow:**
```
1. Apply suggested_fix → retry with modified parameters
2. If still fails → [Minimax] search with different strategy
3. If still fails → notify user: "Couldn't find the email.
                                  Can you be more specific?"
```

#### 2b. External Service Unavailable (e.g., Gmail API down)
```json
{
  "status": "failed",
  "error": {
    "error_type": "external_service_unavailable",
    "retryable": true,
    "retry_after_seconds": 60
  }
}
```
**Flow:**
```
1. Wait retry_after_seconds (60s default)
2. Retry up to 2 times
3. If still failing → check system_status skill
4. Notify user: "Gmail appears to be down. I'll retry in 10 minutes."
5. Queue task for automatic retry
```

#### 2c. Permission Denied
```json
{
  "status": "failed",
  "error": {
    "error_type": "permission_denied",
    "retryable": false
  }
}
```
**Flow:**
```
1. Do NOT retry (will fail again)
2. Notify user immediately: "Work Bot doesn't have permission to {action}.
                             You may need to re-authorize Gmail access."
3. Provide re-auth instructions if known
```

#### 2d. Rate Limited
```json
{
  "status": "failed",
  "error": {
    "error_type": "rate_limited",
    "retryable": true,
    "retry_after_seconds": 120
  }
}
```
**Flow:**
```
1. Wait retry_after_seconds
2. Retry automatically (no user notification needed unless 3rd attempt fails)
```

#### 2e. Ambiguous Input
```json
{
  "status": "failed",
  "error": {
    "error_type": "ambiguous_input",
    "message": "Found 5 emails matching 'invoice'. Which one?",
    "retryable": false,
    "suggested_fix": "Narrow search to specific sender or date"
  }
}
```
**Flow:**
```
1. [Minimax] Can we auto-resolve ambiguity? (pick most recent, most relevant?)
   YES → Retry with narrowed query
   NO  → Ask user: "Found multiple emails. Which one did you mean?
                    [List top 3 matches]"
```

---

### 6.4 Failure Type 3: Timeout

**What happened:** Work Bot received the task but didn't write a result in `timeout_seconds`.

**OpenClaw detection:**
```python
# Pseudocode in OpenClaw's result poller
elapsed = now() - task_timestamp
if elapsed > task.timeout_seconds + 60:  # 60s grace period
    handle_timeout(task_id)
```

**Escalation flow:**
```
1. Write inbox/task_{id}_CANCEL.json to signal Work Bot to stop
   (Work Bot should check for cancel files before long operations)

2. Wait 30 seconds for graceful shutdown

3. [Ollama] Is this task retryable by Work Bot?
   YES (e.g., temporary load spike) → Retry once after 2 minutes
   NO  (e.g., structural issue)     → Go to step 4

4. [Minimax] Attempt the task directly using AI capabilities
   - For email tasks: Minimax can draft emails using its reasoning
   - For task management: Minimax can interact with APIs directly

5. If Minimax also fails → Notify user:
   "Job '{task_name}' is taking too long and I couldn't complete it automatically.
    Would you like me to:
    A) Try again later
    B) Handle it differently
    C) Skip it"

6. Log incident to OpenClaw's memory for pattern detection
   (3 timeouts on same skill type = flag for architecture review)
```

**Cancel File Format:**
```json
{
  "cancel_task_id": "a1b2c3d4-...",
  "timestamp": "2026-02-21T09:20:00Z",
  "reason": "timeout"
}
```

---

### 6.5 Failure Type 4: Partial Success

**What happened:** Work Bot completed some steps of a multi-step workflow but not all.

**Work Bot response:**
```json
{
  "status": "partial",
  "skill_used": "process_invoice_workflow",
  "partial_results": {
    "completed_steps": ["find_invoice_email", "extract_invoice_data"],
    "failed_steps": [
      {"step": "create_draft_reply", "reason": "Claude API rate limit"}
    ],
    "resumable": true,
    "resume_context": {
      "email_id": "18abc123",
      "invoice_data": {"number": "1042", "amount": "$3,400"}
    }
  }
}
```

**Escalation flow:**

```
Case A: resumable = true
─────────────────────────────────────────────────────────────
1. Wait retry_after_seconds (for the root cause, e.g., rate limit)
2. Create new task file with:
   - skill: draft_email_reply  (just the remaining step)
   - parameters derived from resume_context
3. Send to Work Bot as a chained task
4. If that also fails → Minimax handles the remaining step

Case B: resumable = false
─────────────────────────────────────────────────────────────
1. Report completed steps to user (these are done and saved)
2. [Minimax] Attempt to complete the remaining steps
3. If Minimax succeeds → report combined result to user
4. If Minimax fails → ask user what to do with the incomplete job

Always:
─────────────────────────────────────────────────────────────
• Never discard completed work — always report what was done
• Store partial results in OpenClaw memory before attempting resume
```

---

### 6.6 Failure Handling Summary Decision Tree (ASCII)

```
Work Bot Result Received
        │
        ├─── status = "success" ──────────────────→ Report to user ✓
        │
        ├─── status = "partial"
        │         │
        │         ├── resumable = true ──→ Retry remaining steps via Work Bot
        │         │                            └── if fails → Minimax → ask user
        │         └── resumable = false → Report done steps + Minimax for rest
        │                                      └── if fails → ask user
        │
        ├─── status = "failed"
        │         │
        │         ├── retryable = true
        │         │       └── Wait retry_after → Retry (max 2x)
        │         │               └── still failing → Minimax → ask user
        │         │
        │         └── retryable = false
        │                 ├── error_type = "not_found" → Apply suggested_fix → retry once
        │                 ├── error_type = "permission_denied" → Alert user immediately
        │                 ├── error_type = "ambiguous_input" → Ask user to clarify
        │                 └── other → Minimax → ask user
        │
        ├─── status = "unknown_skill"
        │         │
        │         ├── decomposition_hint present → Try Ollama remap → retry
        │         ├── No remap possible → Minimax handles directly
        │         └── Minimax can't → Ask user for guidance
        │
        └─── (no response / timeout)
                  │
                  ├── Send cancel signal to Work Bot
                  ├── Wait 30s
                  ├── Retry once (if task is retryable)
                  ├── Minimax attempts task
                  └── Ask user if all else fails
```

---

### 6.7 Escalation Message Templates

**Unknown skill:**
```
Job: {job_name}
Issue: Work Bot doesn't know how to '{skill}'.

My options:
A) Break it into smaller steps it CAN handle: {decomposition_suggestion}
B) Handle it myself using AI (may be less reliable for real data operations)
C) Skip this job

What would you like?
```

**Execution failed (user decision needed):**
```
Job: {job_name}
Status: Failed after {attempts} attempt(s)
Reason: {error_message}

Suggested fix: {suggested_fix}

What would you like me to do?
A) Retry with the suggested fix applied
B) Try a different approach
C) Skip
```

**Timeout:**
```
Job: {job_name} is taking longer than expected ({elapsed} seconds).
Work Bot hasn't responded yet.

A) Wait another 5 minutes
B) Try with AI instead (no Work Bot)
C) Cancel this job
```

---

## 7. OpenClaw Configuration

See `openclaw.json` for the full configuration file. Key sections:

### 7.1 LLM Routing Rules

```
Ollama (local, fast, free) → Use for:
  • Classifying whether a job goes to Work Bot
  • Choosing the skill name from a user request
  • Simple parameter extraction
  • "Yes/No" routing decisions

Minimax (cloud, powerful) → Use for:
  • Decomposing unknown skills into known ones
  • Drafting fallback email content when Work Bot fails
  • Understanding complex/ambiguous job descriptions
  • Writing escalation messages to you
  • Analyzing patterns across multiple failures
```

### 7.2 Confirmation Requirements

These skills **always require user confirmation** before Work Bot executes:
- `forward_email` — sends to external recipient
- `delete_task` — permanent deletion
- `handle_w9_request` — external-facing document
- `w9_fulfillment_workflow` — same

---

## 8. Bridge Code

The bridge (`bridge.py`) is the translation layer between OpenClaw's file-based protocol and the Work Bot's Python API.

### 8.1 How to Run

**Standalone (alongside Work Bot):**
```bash
cd /home/user/Google-Drive-DB
python openclaw-integration/bridge.py \
  --inbox /path/to/shared/inbox \
  --outbox /path/to/shared/outbox \
  --poll 2
```

**Embedded in Work Bot (preferred — add to mode4_processor.py):**
```python
# In Mode4Processor.__init__:
from openclaw_integration.bridge import OpenClawBridge
self.openclaw_bridge = OpenClawBridge(
    inbox=Path(config.OPENCLAW_INBOX),
    outbox=Path(config.OPENCLAW_OUTBOX),
    processor=self,
)

# In Mode4Processor.run_async(), add to TaskGroup:
async with asyncio.TaskGroup() as tg:
    tg.create_task(self.telegram_handler.run())
    tg.create_task(self.openclaw_bridge.start())  # Add this line
    tg.create_task(self.proactive_engine.run())
```

**Add to .env:**
```env
OPENCLAW_INBOX=/path/to/shared/inbox
OPENCLAW_OUTBOX=/path/to/shared/outbox
```

### 8.2 Testing the Bridge (without OpenClaw)

```bash
# Drop a test task manually
cat > /tmp/inbox/task_test001.json << 'EOF'
{
  "task_id": "00000000-0000-0000-0000-000000000001",
  "timestamp": "2026-02-21T09:00:00Z",
  "source": "openclaw",
  "skill": "system_status",
  "parameters": {},
  "timeout_seconds": 30
}
EOF

# Check outbox for result
cat /tmp/outbox/result_00000000-0000-0000-0000-000000000001.json
```

### 8.3 Adding a New Skill Handler

1. Add entry to `SKILL_REGISTRY` in `bridge.py`
2. Add skill name to `openclaw.json` skills.available list
3. Implement `async def _handle_your_skill(self, task_id, params, context) -> dict`
4. Test by dropping a task file manually

---

## 9. Scenario Walkthroughs

### Scenario 1: SUCCESS — Draft reply to invoice email

```
[09:00] Gmail watcher: New email from acme@corp.com "March Invoice #1042"
[09:00] OpenClaw (Ollama): "This needs a reply. Skill: draft_email_reply. Confidence: 0.92"
[09:00] OpenClaw → User: "Invoice email from Acme Corp. Should I draft a reply?"
[09:01] User: "Yes"
[09:01] OpenClaw writes: inbox/task_a1b2c3.json
          {skill: "draft_email_reply",
           parameters: {email_search_query: "from:acme@corp.com subject:invoice March"}}
[09:01] Bridge picks up task → calls gmail.search_emails() → finds email
[09:05] Bridge calls claude.generate_draft() → creates professional reply
[09:05] Bridge calls gmail.create_reply_draft() → saves draft to Gmail
[09:05] Bridge writes: outbox/result_a1b2c3.json {status: "success", ...}
[09:05] OpenClaw reads result → User: "Done! Draft saved in Gmail.
          Subject: Re: March Invoice #1042
          Draft ID: r-8432098xyz
          Preview: 'Dear Acme team, Thank you for Invoice #1042...'"
```

---

### Scenario 2: UNKNOWN SKILL — "Schedule a meeting"

```
[10:00] User to OpenClaw: "Schedule a meeting with Dave next Tuesday at 3pm"
[10:00] OpenClaw (Ollama): Classifies skill as "schedule_meeting". Confidence: 0.88
[10:00] OpenClaw writes: inbox/task_b2c3d4.json {skill: "schedule_meeting", ...}
[10:00] Bridge picks up → skill "schedule_meeting" NOT in SKILL_REGISTRY
[10:00] Bridge writes: outbox/result_b2c3d4.json
          {status: "unknown_skill",
           unknown_skill_info: {
             closest_match: "add_task",
             decomposition_hint: "Use add_task with title='Schedule meeting with Dave Tue 3pm'"
           }}
[10:00] OpenClaw reads result → Escalation path:
        [Ollama] "Can we remap using available skills?" → YES, use add_task
[10:00] OpenClaw writes: inbox/task_c3d4e5.json
          {skill: "add_task",
           parameters: {title: "Schedule meeting with Dave - Tue 3pm",
                        priority: "high", deadline: "2026-02-24"}}
[10:00] Bridge processes → adds task to Google Sheets
[10:00] OpenClaw → User: "I can't create a calendar invite directly, but I added a reminder task:
          'Schedule meeting with Dave - Tue 3pm' [HIGH priority]
          Note: Work Bot doesn't have calendar access yet. Want me to generate that skill?"
```

---

### Scenario 3: EXECUTION ERROR — Email not found

```
[11:00] User: "Reply to the email from Bob about the contract"
[11:00] OpenClaw (Ollama): Generates query "from:bob subject:contract"
[11:00] inbox/task_d4e5f6.json → Bridge → gmail.search_emails("from:bob subject:contract")
[11:00] Gmail returns 0 results
[11:00] Bridge writes: outbox/result_d4e5f6.json
          {status: "failed",
           error: {error_type: "not_found", retryable: false,
                   suggested_fix: "Try: from:bob OR subject:contract"}}
[11:00] OpenClaw escalation path:
        Apply suggested_fix → retry with "from:bob OR subject:contract"
[11:00] inbox/task_e5f6g7.json (retry_attempt: 1, modified query)
[11:00] Gmail returns 3 results (found emails from "Bob Smith")
[11:01] Bridge drafts reply successfully
[11:01] OpenClaw → User: "Done! (Had to broaden the search — found 3 Bob emails,
          used the most recent contract-related one from Bob Smith.)"
```

---

### Scenario 4: TIMEOUT — Work Bot takes too long

```
[14:00] OpenClaw sends task_f6g7h8.json: process_invoice_workflow, timeout=300s
[14:00] Bridge picks up task, starts processing...
[14:05] Bridge is hung on a slow Google Sheets API response (no network error, just slow)
[14:06] OpenClaw polls outbox — no result_f6g7h8.json found
[14:06] OpenClaw: elapsed = 360s > 300s + 60s grace = TIMEOUT DETECTED
[14:06] OpenClaw writes: inbox/task_f6g7h8_CANCEL.json
[14:06] Bridge (if alive) sees cancel file, abandons task
[14:06] OpenClaw escalation:
        [Ollama] "Is invoice processing retryable?" → YES
        Wait 2 minutes → retry once
[14:08] Retry task_h8i9j0.json sent → Bridge completes in 90s (Sheets was slow)
[14:09] OpenClaw → User: "Invoice processed! (First attempt timed out — Sheets was slow,
          but the retry succeeded.)"

If retry also times out:
[14:13] OpenClaw (Minimax): "The invoice is: Acme Corp #1042, $3,400 due March 15.
          I'll draft a reply without Work Bot."
[14:13] Minimax drafts reply → OpenClaw saves via direct Gmail API call
[14:13] OpenClaw → User: "Done! (Work Bot timed out twice, so I handled it directly.)"
```

---

### Scenario 5: PARTIAL SUCCESS — Workflow fails midway

```
[16:00] OpenClaw: task_g7h8i9.json → process_invoice_workflow
[16:00] Bridge step 1: find_invoice_email → SUCCESS (email found)
[16:00] Bridge step 2: extract_invoice_data → SUCCESS (data extracted)
[16:00] Bridge step 3: create_draft_reply → FAIL (Claude API 429 rate limit)
[16:00] Bridge writes: outbox/result_g7h8i9.json
          {status: "partial",
           partial_results: {
             completed_steps: ["find_invoice_email", "extract_invoice_data"],
             failed_steps: [{step: "create_draft_reply", reason: "Claude API rate limit"}],
             resumable: true,
             resume_context: {email_id: "18abc", invoice_data: {...}}
           }}
[16:00] OpenClaw escalation:
        resumable = true → Wait 60s (rate limit recovery) → retry just the failed step
        Creates: inbox/task_h8i9j0.json
          {skill: "draft_email_reply",
           parameters: {email_search_query: "id:18abc",
                        reply_instructions: "Invoice #1042, $3400, due March 15"},
           context: {prior_task_ids: ["g7h8i9"]}}
[16:01] Bridge processes draft_email_reply → SUCCESS
[16:01] OpenClaw → User: "Invoice workflow complete!
          ✓ Found invoice email
          ✓ Extracted: Invoice #1042, $3,400, due March 15
          ✓ Draft created (had to retry step 3 due to API rate limit)
          Gmail Draft ID: r-xyz789"
```

---

## 10. Decision Tree Diagram

### Full Failure Escalation Decision Tree

```
                    ┌─────────────────────────────────┐
                    │   Work Bot Result Received       │
                    └──────────────┬──────────────────┘
                                   │
         ┌─────────────────────────┼──────────────────────────────────┐
         │                         │                                  │
         ▼                         ▼                                  ▼
   status=success           status=partial               (no response in N+60s)
         │                         │                                  │
         ▼                    resumable?                         TIMEOUT
   ✓ Report to user         /           \                             │
                          YES            NO                    Cancel signal
                           │              │                          │
                    Retry remaining   Report done steps          Retry once?
                    steps via WorkBot + Minimax for rest             │
                           │              │                      YES / NO
                      success? NO→       └──→ ask user           │     │
                      Minimax then ask                        Retry  Minimax
                      user                                         then ask user

         │
         ▼
   status=failed
         │
    retryable?
   /           \
 YES            NO
  │              │
Wait +       error_type?
Retry (2x)       │
  │         ┌────┴─────┬──────────────┬────────────────┐
 still   not_found  permission   ambiguous_input    other
 failing    │       _denied           │               │
  │         │          │           Minimax        Minimax
Minimax  Apply      Alert user    auto-resolve   attempts
then     suggested  immediately   OR ask user    then ask user
ask user fix→retry
         still fails
         → Minimax
         → ask user

         │
         ▼
   status=unknown_skill
         │
   decomposition_hint?
         │
        YES → Ollama remap → retry with new skill
         │         └── still unknown → step below
        NO
         │
   [Minimax] decompose OR handle directly
         │
    success? NO → ask user:
                  A) Decompose
                  B) AI handle
                  C) Skip
                  D) Build new skill
```

### User Escalation Thresholds

```
1 failure    → Try auto-recovery silently
2 failures   → Try Minimax silently
3 failures   → Notify user, offer options
Same failure
3+ times     → Log to USER.md, suggest architecture fix
```

---

## 11. Implementation Checklist

### Week 1: Foundation

- [ ] Create `inbox/` and `outbox/` shared directories
- [ ] Copy `openclaw.json` to OpenClaw root, update paths
- [ ] Run bridge in stub mode: `python bridge.py --inbox ./inbox --outbox ./outbox`
- [ ] Test with manual task file drops (system_status, list_tasks)
- [ ] Integrate bridge into `mode4_processor.py` TaskGroup

### Week 2: Core Skills

- [ ] Wire `draft_email_reply` handler to real gmail/claude pipeline
- [ ] Wire `add_task`, `list_tasks`, `complete_task` to todo_manager
- [ ] Wire `search_email`, `summarize_thread` to gmail pipeline
- [ ] Wire `on_demand_digest`, `daily_digest` to digest modules
- [ ] End-to-end test: OpenClaw → inbox → bridge → outbox → OpenClaw

### Week 3: Failure Handling

- [ ] Implement OpenClaw's outbox poller with timeout detection
- [ ] Implement retry logic (with backoff) in OpenClaw
- [ ] Implement Minimax fallback for `unknown_skill` cases
- [ ] Implement cancel file protocol
- [ ] Test all 5 scenarios from Section 9

### Week 4: Memory & Learning

- [ ] OpenClaw logs unknown skills to USER.md
- [ ] OpenClaw tracks skill success rates
- [ ] Add skill gap analysis: suggest when to add new Work Bot skills
- [ ] Wire high-risk skills to require confirmation before task file creation
- [ ] End-to-end integration test with real OpenClaw instance

---

## Appendix: Error Type Reference

| error_type | Meaning | Retryable | OpenClaw Action |
|-----------|---------|-----------|-----------------|
| `external_service_unavailable` | Gmail/Sheets/Drive API down | Yes | Wait + retry |
| `permission_denied` | OAuth scope missing | No | Alert user for re-auth |
| `not_found` | Email/task/file doesn't exist | No (modify query) | Apply suggested_fix |
| `validation_error` | Bad parameters sent by OpenClaw | No | Fix params in OpenClaw |
| `internal_error` | Work Bot bug | Sometimes | Retry once, then Minimax |
| `ambiguous_input` | Multiple matches | No (clarify) | Ask user OR auto-select |
| `rate_limited` | API quota exceeded | Yes (after delay) | Wait retry_after_seconds |
