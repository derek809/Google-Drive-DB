# MCP Database - Complete Breakdown

**Database:** `mcp_learning.db`  
**Total Tables:** 13  
**Bootstrap Data:** 17 entries  
**Learning Tables:** 5 (empty, ready to learn)

---

## 📊 COMPLETE TABLE STRUCTURE

### ═══════════════════════════════════════════
### CORE WORKFLOW TABLES (3)
### ═══════════════════════════════════════════

#### 1. **threads**
**Purpose:** Tracks email conversations you process with [MCP]

**Columns:**
- `id` - Unique ID
- `gmail_thread_id` - Link to Gmail thread
- `subject` - Email subject line
- `participants` - Who's involved (JSON array)
- `status` - queue/processing/resolved/needs_review/error
- `priority` - high/normal/low
- `needs_escalation` - Flag if human needed
- `mcp_prompt` - Your instruction (e.g., "send w9")
- `created_at` - When you labeled it [MCP]
- `last_updated` - Last activity

**Current Data:** 0 entries (fills as you use it)

---

#### 2. **messages**
**Purpose:** Individual emails within threads

**Columns:**
- `id` - Unique ID
- `thread_id` - Links to threads table
- `gmail_message_id` - Link to Gmail message
- `sender_email` - Who sent it
- `sender_name` - Their name
- `body` - Email content
- `attachments` - Files attached (JSON)
- `received_at` - When they sent it

**Current Data:** 0 entries (fills as you use it)

---

#### 3. **responses**
**Purpose:** Drafts MCP generates and what you actually sent

**Columns:**
- `id` - Unique ID
- `thread_id` - Links to thread
- `template_id` - Which template used (if any)
- `model_used` - Claude/Gemini/Claude_Project
- `draft_text` - What MCP generated
- `confidence_score` - How confident (0-100)
- `user_edited` - Did you edit it? (0/1)
- `edit_percentage` - How much you changed (0-100)
- `sent` - Did you send it? (0/1)
- `final_text` - What you actually sent
- `created_at` - When draft was made
- `sent_at` - When you sent it

**Current Data:** 0 entries (fills as you use it)

---

### ═══════════════════════════════════════════
### BOOTSTRAP PATTERN TABLES (3)
### ═══════════════════════════════════════════

#### 4. **pattern_hints**
**Purpose:** The 7 proven email patterns from your analysis

**Columns:**
- `pattern_id` - Unique ID
- `pattern_name` - Name of pattern
- `keywords` - Words to look for (JSON)
- `trigger_subjects` - Subject lines that match
- `confidence_boost` - Points added when matched
- `usage_count` - How many times used
- `success_rate` - % that worked well
- `last_updated` - Last modified
- `notes` - What to do with this pattern

**Current Data:** 7 entries ✅

---

#### ⭐ THE 7 PROVEN PATTERNS:

##### 1. **W9/Wiring Request** (+20 confidence)
- **Keywords:** w9, w-9, wiring instructions, wire details
- **Action:** Use w9_response template
- **Frequency:** Recurring (exact count unknown)
- **ROI:** ~30 min/week

##### 2. **Invoice Processing** (+15 confidence)
- **Keywords:** invoice, fees, mgmt, Q3, Q4, quarterly
- **Action:** Route to Claude Project or Google Script (CSV vs. body text)
- **Frequency:** 27/97 emails (28%)
- **ROI:** ~2 hours/week

##### 3. **Payment Confirmation** (+15 confidence)
- **Keywords:** payment, wire, received, OCS Payment
- **Action:** Use payment_confirmation template
- **Frequency:** 3/97 emails
- **ROI:** ~30 min/week

##### 4. **Producer Statements** (+10 confidence)
- **Keywords:** producer statements, producer report
- **Action:** Reminder to run NetSuite export
- **Frequency:** 3/97 emails (weekly Friday)
- **ROI:** ~1 hour/week

##### 5. **Turnaround Expectation** (+5 confidence)
- **Keywords:** how long, timeline, when, deadline
- **Action:** Use turnaround_time template
- **Frequency:** Recurring need
- **ROI:** Time-saver for timeline questions

##### 6. **Delegation to Eytan** (0 confidence - learns)
- **Keywords:** insufficient info, not sure, need eytan, loop in eytan
- **Action:** Use delegation_eytan template
- **Frequency:** Low (but you want to use MORE)
- **ROI:** Reduces back-and-forth

##### 7. **Journal Entry Reminder** (0 confidence - learns)
- **Keywords:** JE, journal entry, partner compensation
- **Action:** Look up in knowledge base
- **Frequency:** 1/97 emails
- **ROI:** Prevents errors

---

#### 5. **templates**
**Purpose:** The 4 email templates you requested

**Columns:**
- `template_id` - Unique identifier
- `template_name` - Display name
- `template_body` - The actual email text with {variables}
- `variables` - What needs to be filled in (JSON)
- `attachments` - Files to attach (JSON)
- `usage_count` - Times used
- `success_rate` - % sent without major edits
- `created_at` - When created
- `last_used` - Most recent use

**Current Data:** 4 entries ✅

---

#### ⭐ THE 4 TEMPLATES:

##### 1. **w9_response** - W9 & Wiring Instructions
**Variables:** `{name}`, `{wiring_details}`  
**Attachments:** OldCity_W9.pdf

**Template:**
```
Hi {name},

Here's our W9 form (attached).

Our wiring instructions:
{wiring_details}

Let me know if you need anything else!

Best,
Derek
```

**Use for:** W9 and wiring instruction requests  
**Edit rate target:** <10%

---

##### 2. **payment_confirmation** - Payment Received
**Variables:** `{name}`, `{amount}`, `{date}`  
**Attachments:** None

**Template:**
```
Hi {name},

Confirmed - we received payment of ${amount} on {date}.

Thank you!

Best,
Derek
```

**Use for:** Confirming payments received  
**Edit rate target:** <15%

---

##### 3. **delegation_eytan** - Loop in Eytan
**Variables:** `{name}`, `{context}`  
**Attachments:** None

**Template:**
```
Hi {name},

Looping in Eytan for his input on this.

Eytan - {context}

Thanks,
Derek
```

**Use for:** When you need Eytan's input  
**Edit rate target:** <20%

---

##### 4. **turnaround_time** - Timeline Response
**Variables:** `{name}`, `{request_type}`, `{timeline}`, `{specific_date}`  
**Attachments:** None

**Template:**
```
Hi {name},

Our typical turnaround for {request_type} is {timeline}.

I'll have this back to you by {specific_date}.

Let me know if you need it sooner.

Best,
Derek
```

**Use for:** When people ask "how long will this take?"  
**Edit rate target:** <20%

---

#### 6. **existing_tools**
**Purpose:** Your 3 existing automation tools

**Columns:**
- `tool_id` - Unique ID
- `tool_name` - Name of tool
- `tool_type` - claude_project/script/api/manual
- `use_case` - What it does
- `trigger_condition` - When to use it
- `success_count` - Times it worked
- `failure_count` - Times it failed
- `last_used` - Most recent use
- `notes` - Additional info

**Current Data:** 3 entries ✅

---

#### ⭐ THE 3 EXISTING TOOLS:

##### 1. **Claude Project - Invoice Generator**
- **Type:** claude_project
- **Use:** Generate invoices from email body text
- **When:** Invoice request AND body contains deal details
- **Success Rate:** 14 uses, 95% success
- **Status:** Primary invoice tool

##### 2. **Google Script - Invoice CSV**
- **Type:** script
- **Use:** Generate invoices from CSV attachments
- **When:** Invoice request AND CSV file attached
- **Success Rate:** 11 uses, 90% success
- **Status:** Secondary invoice tool (for CSV data)

##### 3. **NetSuite Export**
- **Type:** manual
- **Use:** Producer statements weekly report
- **When:** Producer statements request AND Friday
- **Success Rate:** Manual process (not tracked yet)
- **Status:** Should automate in future

---

### ═══════════════════════════════════════════
### LEARNING TABLES (5) - START EMPTY
### ═══════════════════════════════════════════

#### 7. **knowledge_base**
**Purpose:** Learns answers to questions you get repeatedly

**Columns:**
- `kb_id` - Unique ID
- `topic` - Subject area
- `question` - The question
- `answer` - Your answer (learned from your responses)
- `source_thread_id` - Where this was learned
- `confidence` - How sure we are (0-1)
- `usage_count` - Times this answer was used
- `times_reinforced` - Times you confirmed it's right
- `last_updated` - Last modified
- `created_at` - When learned

**Current Data:** 0 entries (learns from your emails)

**Will Learn Examples:**
- "When do I create a JE for partner compensation?"
- "Where to find Frank B / Nera mandate details?"
- "What's our typical turnaround for mandate reviews?"
- "Who approves non-standard fee structures?"

---

#### 8. **contact_patterns**
**Purpose:** Learns about each person you email

**Columns:**
- `id` - Unique ID
- `contact_email` - Their email address
- `contact_name` - Their name
- `relationship_type` - rr/deal_manager/managing_partner/compliance_officer
- `preferred_tone` - How you talk to them (formal/friendly/concise)
- `response_time_preference` - urgent/normal/low_priority
- `common_topics` - What you usually discuss (JSON)
- `interaction_count` - How many emails exchanged
- `last_interaction` - Most recent email
- `created_at` - When first learned

**Current Data:** 0 entries (learns from your emails)

**Will Learn Examples:**
- Tom Smith: Concise, formal, bullet points preferred
- Mike Riskind: Friendly, detailed, conversational
- George: Formal, compliance-focused, thorough
- Eytan: Technical, prefers context, collaborative

---

#### 9. **writing_patterns**
**Purpose:** Learns your favorite phrases and writing style

**Columns:**
- `id` - Unique ID
- `phrase` - Your phrase
- `context` - When you use it
- `recipient_type` - Who you use it with
- `frequency` - How often you use it
- `last_used` - Most recent use
- `created_at` - When first observed

**Current Data:** 0 entries (learns from your sent emails)

**Will Learn Examples:**
- "Just wanted to make sure..."
- "Please find attached..."
- "Looping in..."
- "No rush on this request but..."
- "Happy Friday!"
- "Have a great day!"

---

#### 10. **learning_patterns**
**Purpose:** Discovers new email types beyond the initial 7

**Columns:**
- `id` - Unique ID
- `thread_id` - Example thread
- `pattern_type` - phrasing/decision/action_sequence/escalation_trigger
- `pattern_text` - Description of pattern
- `context` - Details (JSON)
- `confidence` - How sure we are (0-1)
- `times_reinforced` - How many times we've seen it
- `last_reinforced` - Most recent occurrence
- `created_at` - When discovered

**Current Data:** 0 entries (discovers from your usage)

**Will Discover Examples:**
- Mandate review requests (if frequent enough)
- RR onboarding sequences
- Due diligence requests
- Portal access issues
- Contract review requests

---

#### 11. **observed_actions**
**Purpose:** Learns what you do AFTER each email type

**Columns:**
- `observation_id` - Unique ID
- `email_pattern` - Type of email
- `action_taken` - What you did next
- `action_details` - Specifics (JSON)
- `frequency` - How often you do this
- `last_observed` - Most recent time

**Current Data:** 0 entries (observes from your workflow)

**Will Learn Examples:**
- After invoice request → Update NetSuite
- After RR onboarding → Create calendar reminder
- After payment → Check QuickBooks
- After W9 request → Attach W9 PDF
- After mandate review → Schedule compliance call

---

### ═══════════════════════════════════════════
### SAFETY & CONTROL TABLES (2)
### ═══════════════════════════════════════════

#### 12. **overrides**
**Purpose:** Hard safety rules that never change

**Columns:**
- `id` - Unique ID
- `rule_type` - sender/subject_keyword/thread_id
- `rule_value` - What to match
- `action` - never_draft/always_escalate/require_high_confidence
- `reason` - Why this rule exists
- `is_active` - Enabled? (0/1)
- `created_at` - When created

**Current Data:** 3 entries ✅

---

#### ⭐ THE 3 SAFETY RULES:

##### 1. **FINRA Audit Block**
- **Matches:** Subject contains "FINRA audit"
- **Action:** NEVER DRAFT (human only)
- **Reason:** Compliance risk

##### 2. **SEC Escalation**
- **Matches:** Subject contains "SEC"
- **Action:** ALWAYS ESCALATE (requires review)
- **Reason:** Regulatory matter

##### 3. **Compliance Violation Block**
- **Matches:** Subject contains "compliance violation"
- **Action:** NEVER DRAFT (human only)
- **Reason:** Legal risk

---

#### 13. **confidence_rules**
**Purpose:** Adjusts confidence scores based on email characteristics

**Columns:**
- `id` - Unique ID
- `rule_name` - Display name
- `condition_type` - What to check
- `condition_value` - What value
- `score_modifier` - Points to add/subtract
- `priority` - Order to apply rules
- `is_active` - Enabled? (0/1)
- `times_applied` - Usage count
- `success_rate` - How often it's right
- `created_at` - When created

**Current Data:** 2 entries (minimal, learns more)

**Starting Rules:**
1. **Unknown Sender Penalty:** -20 points
2. **Known Contact Bonus:** +10 points

**Will Learn More Rules:**
- Urgent keyword → +5 points
- Long email thread → -5 points
- Multiple attachments → -10 points
- Reply within 1 hour → +15 points

---

## 📈 SUMMARY

### Bootstrap Data (Day 1):
```
✅ 7 Patterns      (28% invoice, W9, payment, etc.)
✅ 4 Templates     (W9, payment, delegation, turnaround)
✅ 3 Tools         (Claude Project, Script, NetSuite)
✅ 3 Safety Rules  (FINRA, SEC, compliance)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   17 Total Entries Ready for Use
```

### Learning Tables (Empty):
```
📚 Knowledge Base      0 entries → Learns Q&A
👥 Contact Patterns    0 entries → Learns relationships  
✍️ Writing Patterns    0 entries → Learns your phrases
🔍 Discovered Patterns 0 entries → Finds new types
🎯 Observed Actions    0 entries → Learns sequences
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   5 Learning Systems Ready to Start
```

### Database Size:
- **Current:** 132 KB
- **After 100 emails:** ~500 KB
- **After 1,000 emails:** ~2-3 MB

---

## 🎯 EXPECTED GROWTH

### After 10 Emails:
- 10 threads tracked
- 10+ messages logged
- 10 responses generated
- 3-5 contacts learned
- 5-10 phrases captured

### After 50 Emails:
- 15-20 contacts known
- 30-50 writing patterns
- 2-3 new patterns discovered
- 80% confidence on known types

### After 100 Emails:
- 30+ contacts with preferences
- 100+ writing patterns
- 5+ new patterns discovered
- Knowledge base has 20+ Q&As
- 90% confidence on known types

---

## 🚀 NEXT STEP

**Your database is ready!**

To start using it, you just need to:
1. Label an email [MCP]
2. Add a prompt
3. Let me process it

Every email makes the system smarter! 🧠
