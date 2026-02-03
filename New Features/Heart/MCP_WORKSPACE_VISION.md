# MCP Workspace System - Complete Vision & Spec

## The Core Problem You're Solving

**Current Reality:**
- You have 5-10 emails that actually need your attention
- They're already starred/labeled as "important"
- You know what needs action - you need help **clearing** them
- Everything else can wait

**What You Want:**
Mode4 should be a **proactive workspace assistant** that:
1. Monitors ONLY your curated 5-10 "mcp" labeled emails
2. Reminds you what needs attention (time-based + event-based)
3. Helps you take action via natural conversation
4. Remembers context so you can say "send it" / "mark done"
5. Runs in the background and alerts you when things happen

---

## The Two-Label System

### Label 1: `mcp` (Active Workspace)
- Your 5-10 emails that need action
- YOU decide what goes here (you label them in Gmail)
- Bot monitors these constantly
- Bot helps you clear them

### Label 2: `mcp done` (Completed Archive)
- Items you've finished
- Bot moves emails here when you say "mark done"
- OR you can manually move them yourself
- Keeps your workspace clean

---

## User Experience Walkthrough

### Morning: Proactive Digest
```
🌅 Good morning Derek! Your MCP workspace (6 items):

🔴 URGENT TODAY:
1. Compliance call prep - George (today 2pm)
   → Want me to draft talking points?

🟡 NEEDS ATTENTION:
2. Jason invoice (drafted 2 days ago, not sent yet)
   → Ready to send?
3. Laura Clarke follow-up (5 days, no reply)
   → Send a gentle nudge?

🟢 ACTIVE:
4. Mandate review - Chris D (uploaded yesterday)
   → Run pre-check on the form?
5. W9 request - New RR onboarding
   → Send standard W9 template?
6. AP reconciliation question - Chris (accounting)

Reply with number or just tell me what you need!
```

**You reply:** `1`

**Bot:** 
```
Compliance call at 2pm with George. 

Based on last week's bi-weekly call, I see you discussed:
- 3 new mandate submissions
- 1 pending MFN clause issue

Want me to draft talking points for today?
```

**You:** `yes`

**Bot:** `[generates draft talking points document]`
```
Here are your prep notes. Should I:
📧 Email to George
📝 Save as note (just for you)
```

**You:** `send to george`

**Bot:** `✅ Sent to George at george@oldcitycapital.com`
```
I'll remind you 30 min before the call (1:30pm).
Marking this workspace item as handled.
```

---

### Throughout Day: Ambient Intelligence

**[11:47am - Bot detects new activity]**
```
🔔 Jason replied to your invoice email!

His message: "Looks good, processing payment today"

Want to mark this as done?
```

**You:** `yes done`

**Bot:** `✅ Moved Jason invoice → mcp done. Nice work!`

---

**[2:15pm - After your call]**
```
Hope the compliance call went well! 

Any follow-ups I should track from the meeting?
```

**You:** `yeah we need to update the wsps by friday`

**Bot:** `✅ Created task: "Update WSPs" - Due Friday 5pm`
```
Should I also:
• Set a reminder for Thursday?
• Link this to the compliance call notes?
```

---

**[4:30pm - Time-based trigger]**
```
💬 Laura Clarke still hasn't replied (now 6 days).

Her last email was asking about the George mandate question.

Want me to draft a gentle follow-up?
```

**You:** `yeah make it casual`

**Bot:** `[generates draft]`
```
Subject: Re: George mandate question

Hey Laura,

Just wanted to follow up on this - any update from your end on the George mandate? No rush, just checking in.

Let me know!
Derek

---
How's this? Reply with:
✅ Send it
✏️ Edit (tell me what to change)
❌ Cancel
```

**You:** `send it`

**Bot:** `✅ Sent to Laura Clarke`
```
I'll keep watching this thread and let you know when she replies.
```

---

### Natural Conversation Flow (Memory)

**You:** `draft invoice to jason for the abc fund deal`

**Bot:** `[searches Gmail for ABC Fund context]`
```
Found the ABC Fund subscription docs from last week.

Investment amount: $100,000
Fee: 2% = $2,000
Retainer paid: $500
Net due: $1,500

Should I draft the invoice with these numbers?
```

**You:** `yes`

**Bot:** `[generates invoice email draft]`
```
Subject: Invoice - ABC Fund Investment

Hi Jason,

[Draft shows here...]

---
Looks good?
```

**You:** `make it shorter`

**Bot:** `[revises SAME draft - remembers "it" = jason invoice]`
```
Condensed version:

Subject: Invoice - ABC Fund

Hi Jason,

Please find attached invoice for ABC Fund placement.
Net fee due: $1,500 (gross $2,000 - $500 retainer)

Best,
Derek

---
Better?
```

**You:** `perfect send it`

**Bot:** `✅ Sent to Jason`
```
Created workspace item to track this invoice.
I'll alert you when he replies.
```

**[2 hours later]**

**Bot:** `🔔 Jason replied to the ABC Fund invoice - he approved it!`

**You:** `mark done`

**Bot:** `✅ Invoice complete → moved to mcp done`

---

## The Three Core Systems

### 1. Workspace Sync (Background - Every 15 min)
**What it does:**
- Polls Gmail for emails with "mcp" label
- Detects NEW emails you've labeled → adds to workspace
- Detects REMOVED labels → marks done automatically
- Detects NEW REPLIES on existing items → alerts you
- Keeps local database in sync with Gmail

**Why every 15 min:**
- Fast enough to feel real-time
- Slow enough to not hammer Gmail API
- You can manually trigger: `/sync` for instant check

---

### 2. Proactive Engine (Background - Every 2 hours)
**What it does:**
- Checks each workspace item for triggers
- Sends smart suggestions (max 1 per item per day - no spam)

**Triggers:**
1. **Time-based:**
   - "No reply in 3+ days" → suggest follow-up
   - "Urgent item + it's 3pm" → remind to tackle before EOD
   - "Thursday + you usually invoice Jason" → suggest drafting

2. **Event-based:**
   - "New reply detected" → alert immediately
   - "Draft created but not sent for 2 days" → nudge to send
   - "Compliance call in 2 hours" → offer prep help

3. **Pattern-based** (learns over time):
   - "You always do mandate reviews on Fridays" → batch them
   - "You respond to George within 1 hour" → prioritize his emails
   - "Invoice emails take you 5 min" → suggest batching 3 at once

---

### 3. Conversational Memory (Active during chats)
**What it does:**
- Tracks your last 3-5 interactions (10 min TTL)
- Remembers what "it", "that", "this" refers to
- Enables natural flow without repeating yourself

**What it tracks:**
```javascript
{
  last_draft_id: "draft_xyz123",
  last_workspace_item_id: 42,
  last_mentioned_person: "Jason",
  last_email_thread_id: "thread_abc789",
  last_action: "drafted_email",
  last_file_id: "1a2b3c4d",
  context_expires_at: "2026-01-30T15:45:00"
}
```

**Example resolutions:**
- "send it" → resolves to `last_draft_id`
- "mark done" → resolves to `last_workspace_item_id`
- "add tom to it" → resolves to `last_draft_id` (adds CC)
- "what's the status" → resolves to `last_workspace_item_id`

---

## Technical Architecture

```
┌─────────────────────────────────────────────┐
│         GMAIL ("mcp" label)                 │
│         Your 5-10 curated emails            │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│     WORKSPACE SYNC (every 15 min)           │
│     - Poll Gmail API                        │
│     - Detect new "mcp" labels → add         │
│     - Detect removed labels → mark done     │
│     - Detect new replies → alert            │
│     - Update workspace_items table          │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│     LOCAL DATABASE (workspace_items)        │
│     id | thread_id | subject | from_name   │
│     status | urgency | last_activity        │
│     bot_notes | related_task_id             │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│     PROACTIVE ENGINE (every 2 hours)        │
│     For each workspace item:                │
│     - Check time rules (3+ days old?)       │
│     - Check event rules (new reply?)        │
│     - Check patterns (Thursday invoice?)    │
│     - Send suggestion (max 1/day/item)      │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│     TELEGRAM ALERTS                         │
│     - Morning digest (7am)                  │
│     - Real-time alerts (new replies)        │
│     - Proactive suggestions                 │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│     YOU (via Telegram)                      │
│     - Read alerts                           │
│     - Give natural language commands        │
│     - Bot helps clear workspace             │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│     CONVERSATION MEMORY (10 min TTL)        │
│     - Tracks last 3-5 exchanges             │
│     - Resolves "it", "that", "this"         │
│     - Enables natural flow                  │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│     LLM ROUTER                              │
│     - Parse natural language                │
│     - Generate drafts (Ollama or Claude)    │
│     - Extract action intent                 │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│     ACTIONS                                 │
│     - Draft email                           │
│     - Send email                            │
│     - Mark workspace item done              │
│     - Create task                           │
│     - Move to "mcp done" label              │
└─────────────────────────────────────────────┘
```

---

## Database Schema

```sql
-- Main workspace table
CREATE TABLE workspace_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  
  -- Gmail identifiers
  gmail_thread_id TEXT UNIQUE NOT NULL,
  gmail_message_id TEXT,  -- Latest message in thread
  
  -- Email metadata
  subject TEXT,
  from_email TEXT,
  from_name TEXT,
  snippet TEXT,  -- First 200 chars preview
  
  -- Status tracking
  status TEXT DEFAULT 'active',  -- active | done | snoozed
  urgency TEXT DEFAULT 'normal', -- urgent | normal | low
  
  -- Timestamps
  added_to_workspace TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_gmail_activity TIMESTAMP,  -- Last reply/update in Gmail
  last_bot_suggestion TIMESTAMP,  -- Don't spam suggestions
  completed_at TIMESTAMP,
  snoozed_until TIMESTAMP,
  
  -- Relationships
  related_task_id INTEGER,
  related_draft_id TEXT,
  
  -- Bot intelligence
  bot_notes TEXT,  -- "Waiting on Jason reply", "Invoice sent", etc.
  suggestion_count INTEGER DEFAULT 0,
  
  FOREIGN KEY (related_task_id) REFERENCES tasks(id)
);

CREATE INDEX idx_workspace_status ON workspace_items(status);
CREATE INDEX idx_workspace_thread ON workspace_items(gmail_thread_id);
CREATE INDEX idx_workspace_urgency ON workspace_items(urgency, status);

-- Conversation memory (ephemeral - clears after 10 min)
CREATE TABLE conversation_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  
  -- Context tracking
  last_draft_id TEXT,
  last_workspace_item_id INTEGER,
  last_mentioned_person TEXT,
  last_email_thread_id TEXT,
  last_action TEXT,
  last_file_id TEXT,
  
  -- TTL
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP,
  
  FOREIGN KEY (last_workspace_item_id) REFERENCES workspace_items(id)
);

CREATE INDEX idx_memory_user ON conversation_memory(user_id);
CREATE INDEX idx_memory_expires ON conversation_memory(expires_at);

-- Proactive suggestions log (track what we've suggested)
CREATE TABLE suggestion_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_item_id INTEGER,
  suggestion_type TEXT,  -- follow_up | send_draft | prep_call | etc.
  suggested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  user_action TEXT,  -- accepted | dismissed | ignored
  
  FOREIGN KEY (workspace_item_id) REFERENCES workspace_items(id)
);
```

---

## Commands Reference

### Workspace Management
```
/workspace              # Show all active MCP items
/workspace urgent       # Filter by urgent only
/workspace jason        # Filter by person/keyword
/sync                   # Force Gmail sync now (don't wait 15 min)
```

### Item Actions
```
/done 3                 # Mark workspace item #3 as done
/done                   # Mark last mentioned item done (uses memory)
/snooze 2 friday        # Hide item #2 until Friday
/urgency 4 high         # Set item #4 to urgent
/note 1 waiting on X    # Add note to item #1
```

### Email Actions (natural language)
```
draft reply to jason
send it
make it shorter
add tom to cc
mark done
```

### Proactive Controls
```
/proactive on           # Enable proactive suggestions (default: on)
/proactive off          # Disable suggestions
/digest                 # Force morning digest now
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Basic workspace tracking

**Deliverables:**
- [ ] `workspace_items` table created
- [ ] Gmail sync script (15 min polling)
- [ ] `/workspace` command shows active items
- [ ] `/done <id>` moves item to "mcp done" label
- [ ] Manual add/remove to workspace works

**Success Criteria:**
- You label email "mcp" → shows in `/workspace` within 15 min
- You `/done 1` → email moves to "mcp done" label
- Bot doesn't crash if Gmail API is slow

---

### Phase 2: Proactive Basics (Week 2)
**Goal:** Bot starts helping proactively

**Deliverables:**
- [ ] Proactive engine (2-hour checks)
- [ ] Time-based rule: "3+ days old → suggest follow-up"
- [ ] Event-based rule: "New reply → alert immediately"
- [ ] Morning digest at 7am
- [ ] Urgency detection (keywords in subject/snippet)

**Success Criteria:**
- Email sits for 3 days → bot suggests follow-up
- Someone replies to workspace email → you get alerted within 15 min
- Every morning at 7am → digest shows workspace summary

---

### Phase 3: Conversational Memory (Week 3)
**Goal:** Natural language flow

**Deliverables:**
- [ ] `conversation_memory` table
- [ ] Pronoun resolution ("it", "that", "this")
- [ ] Context-aware parsing
- [ ] "send it" / "mark done" / "make it shorter" works

**Success Criteria:**
- You draft email, then say "send it" → bot sends the right draft
- You say "mark done" → bot marks the workspace item you were just discussing
- Memory expires after 10 min idle → bot asks for clarification

---

### Phase 4: Intelligence (Week 4+)
**Goal:** Bot learns your patterns

**Deliverables:**
- [ ] Pattern detection (weekly analysis)
- [ ] Smart batching ("3 invoices ready → batch them?")
- [ ] Habit learning ("You always invoice Jason on Thursdays")
- [ ] Workspace health metrics

**Success Criteria:**
- Bot suggests invoice drafting on Thursday mornings
- Bot detects you respond to George quickly → prioritizes his emails
- Weekly summary: "You cleared 12 items this week! Avg 1.8 days per item"

---

## Why This Design Works for You

### 1. Bounded Scope
- Bot ONLY watches 5-10 emails (your "mcp" label)
- Not drowning in noise
- Clear, manageable workspace

### 2. You Stay in Control
- YOU decide what goes in workspace (via Gmail labels)
- Bot helps clear, doesn't decide priority
- Can always override bot ("no not that one")

### 3. Proactive but Not Annoying
- Max 1 suggestion per item per day
- Morning digest = batched notifications
- Can disable: `/proactive off`

### 4. Natural Conversation
- Memory lets you talk naturally
- "send it" / "make it shorter" just works
- Don't have to repeat yourself

### 5. Zero Manual Tracking
- Bot syncs automatically
- New replies detected
- Status updates happen behind the scenes

### 6. Builds on What You Have
- Uses existing Gmail labels
- Works with current Mode4 setup
- Doesn't require new tools/apps

---

## Success Metrics (How You'll Know It's Working)

### Week 1:
- "I labeled 5 emails 'mcp' and they all showed in `/workspace`"
- "I marked 2 done and they moved to 'mcp done' automatically"

### Week 2:
- "Bot reminded me about Laura's email after 3 days - I would've forgotten"
- "I got alerted when Jason replied - didn't have to check Gmail"

### Week 3:
- "I said 'send it' and bot sent the right draft - felt natural"
- "Morning digest gave me perfect overview - knew what to tackle"

### Week 4:
- "Bot suggested batching 3 invoices on Thursday - saved me time"
- "Workspace feels manageable - never more than 7-8 items"
- "I'm checking Gmail less - bot tells me what matters"

---

## The End Goal

**You should feel like Mode4 is:**
- ✅ A proactive assistant who knows your workspace
- ✅ Always watching your back (new replies, upcoming deadlines)
- ✅ Helpful without being annoying (smart suggestions, not spam)
- ✅ Easy to talk to (natural language, remembers context)
- ✅ Reducing your cognitive load (you worry less about "what am I forgetting")

**Mode4 should NOT feel like:**
- ❌ Another thing to manage
- ❌ A bot that needs constant commands
- ❌ Something that misunderstands you
- ❌ Spam machine with too many alerts

---

## Next Steps

1. Review this doc - make sure vision aligns
2. Run Phase 1 code (workspace foundation)
3. Test with 3-5 real emails
4. Iterate based on what feels good/annoying
5. Move to Phase 2 once comfortable

---

**Questions to think about:**
- What time do you want morning digest? (default: 7am)
- How often is "too often" for suggestions? (default: max 1/day per item)
- Which triggers matter most to you? (3-day follow-up? New replies? Urgent items?)
- Do you want bot to auto-detect urgency or let you set it manually?

Let's build this! 🚀
