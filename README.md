# MCP Email Processing System

**Version:** 1.0  
**Status:** Phase 1 Ready - Manual Processing  
**Created:** January 22, 2026

---

## Overview

An AI-powered email processing system that learns Derek's communication patterns, automates routine responses, and intelligently routes complex tasks to specialized tools.

### What's Working Now

✅ **SQLite Database** - Fully initialized with 13 tables and Day 1 bootstrap data  
✅ **Core Orchestrator** - Pattern matching, intent parsing, confidence scoring  
✅ **Template Processor** - W9, payment confirmation, delegation, turnaround templates  
✅ **7 Bootstrap Patterns** - Invoice, W9, payment, producer statements, delegation, turnaround, JE  
✅ **Safety System** - Compliance overrides, confidence rules

---

## Quick Start Guide

### Step 1: Verify Installation

```bash
cd ~/MCP
ls -la
```

You should see:
- `mcp_workflow.db` - SQLite database
- `orchestrator.py` - Main orchestrator
- `template_processor.py` - Template handler
- `schema.sql` - Database schema

### Step 2: Test the System

```bash
# Test orchestrator
python3 orchestrator.py

# Test template processor
python3 template_processor.py
```

### Step 3: Connect to Gmail

**Using Claude.ai web interface:**

1. Open claude.ai
2. Make sure Gmail connector is enabled
3. Test with: "Can you search my Gmail for emails from the last 7 days?"

### Step 4: Process Your First Email

**Manual Method (Phase 1):**

1. **In Gmail:**
   - Find a W9 request email
   - Label it `[MCP]`
   - Reply to yourself with: `[MCP] send w9`

2. **In Claude.ai or Claude Desktop:**

```
I have an email labeled [MCP] that needs processing.

Please:
1. Search my Gmail for emails labeled [MCP]
2. Read the most recent one
3. Extract: subject, body, sender email, sender name
4. Then tell me - I'll process it with MCP
```

3. **Once you have the email data, say:**

```
Process this email with MCP:

Subject: [paste subject]
Body: [paste body]
Sender: [paste sender]
MCP Prompt: send w9

Use the MCP orchestrator at ~/MCP/orchestrator.py
```

---

## File Structure

```
~/MCP/
├── mcp_workflow.db          # SQLite database (13 tables)
├── orchestrator.py           # Main processing engine
├── template_processor.py     # Template handler
├── schema.sql               # Database schema
├── README.md                # This file
└── [Future files:]
    ├── gmail_connector.py   # Gmail integration
    ├── learning_loop.py     # Edit tracking & learning
    └── batch_processor.py   # Scheduled automation
```

---

## Database Tables

### Core Workflow
1. **threads** - Email thread tracking
2. **messages** - Individual messages
3. **responses** - Generated drafts and outcomes

### Bootstrap Patterns
4. **pattern_hints** - 7 proven email patterns
5. **templates** - 4 email templates
6. **existing_tools** - Claude Projects, Scripts

### Learning System
7. **knowledge_base** - Institutional knowledge
8. **contact_patterns** - Sender-specific learnings
9. **writing_patterns** - Derek's phrases
10. **learning_patterns** - Discovered patterns
11. **observed_actions** - Action sequences

### Safety & Control
12. **overrides** - Safety rules
13. **confidence_rules** - Score adjustments

---

## Available Templates

### 1. W9 Response (`w9_response`)
**Use for:** W9 and wiring instruction requests  
**Variables:** name, wiring_details  
**Attachments:** OldCity_W9.pdf  
**Confidence Boost:** +20

### 2. Payment Confirmation (`payment_confirmation`)
**Use for:** Payment received confirmations  
**Variables:** name, amount, date  
**Confidence Boost:** +15

### 3. Delegation to Eytan (`delegation_eytan`)
**Use for:** Looping in Eytan for input  
**Variables:** name, context  
**Confidence Boost:** 0

### 4. Turnaround Time (`turnaround_time`)
**Use for:** Timeline/deadline questions  
**Variables:** name, request_type, timeline, specific_date  
**Confidence Boost:** +5

---

## Pattern Recognition

### Pattern 1: Invoice Processing (28% of emails)
**Keywords:** invoice, fees, mgmt, Q3, Q4, quarterly  
**Action:** Route to Claude Project or Google Script  
**Confidence:** +15

### Pattern 2: W9/Wiring Request
**Keywords:** w9, w-9, wiring instructions, wire details  
**Action:** Use w9_response template  
**Confidence:** +20

### Pattern 3: Payment Confirmation
**Keywords:** payment, wire, received, OCS Payment  
**Action:** Use payment_confirmation template  
**Confidence:** +15

### Pattern 4: Producer Statements (Weekly)
**Keywords:** producer statements, producer report  
**Action:** Reminder to run NetSuite export  
**Confidence:** +10

### Pattern 5: Delegation
**Keywords:** insufficient info, not sure, need eytan  
**Action:** Use delegation_eytan template  
**Confidence:** 0

### Pattern 6: Turnaround Expectation
**Keywords:** how long, timeline, when, deadline  
**Action:** Use turnaround_time template  
**Confidence:** +5

### Pattern 7: Journal Entry
**Keywords:** JE, journal entry, partner compensation  
**Action:** Knowledge base lookup  
**Confidence:** 0

---

## Confidence Scoring System

**Base Score:** 50

**Bonuses:**
- Pattern match: +5 to +20 (based on pattern)
- Known sender: +10
- High template match: +5

**Penalties:**
- Unknown sender: -20
- Compliance keywords: -30
- Missing critical info: -10

**Ranges:**
- 90-100: Very High Confidence → Auto-suggest draft
- 70-89: High Confidence → Draft with review flag
- 50-69: Medium Confidence → Extract info, suggest template
- 30-49: Low Confidence → Summary only
- 0-29: Very Low Confidence → Escalate to manual review

---

## Safety System

### Automatic Blocks
- ❌ FINRA audit (never draft)
- ❌ SEC (always escalate)
- ❌ Compliance violation (never draft)

### Always Require Review
- Financial account numbers
- Credit card details
- Sensitive HR matters
- Legal issues

---

## Usage Examples

### Example 1: W9 Request

**Email:**
```
From: john@client.com
Subject: W9 Needed
Body: Hi Derek, can you send your W9 and wiring instructions?
```

**Derek's Prompt:** `send w9`

**MCP Output:**
```
============================================================
EMAIL DRAFT GENERATED
============================================================

To: john@client.com
Subject: Re: W9 Needed

📎 ATTACHMENTS:
  • OldCity_W9.pdf

DRAFT:
------------------------------------------------------------
Hi John,

Here's our W9 form (attached).

Our wiring instructions:
[Your wiring details here]

Let me know if you need anything else!

Best,
Derek
------------------------------------------------------------

Confidence: 100%
✓ Ready to review and send
============================================================
```

### Example 2: Information Extraction

**Email:**
```
From: mike@limadvisors.com
Subject: Invoice for Series A
Body: We closed Series A. $2M investment, 3% fee.
Our retainer was $10k. Please invoice.
```

**Derek's Prompt:** `tell me amount and people to email`

**MCP Output:**
```
Extracted from email:

AMOUNT: $2,000,000 ✓
FEE RATE: 3% ✓
RETAINER PAID: $10,000 ✓
NET FEE DUE: $50,000 ✓
PEOPLE TO EMAIL: 
  - mike@limadvisors.com ✓

Ready to generate invoice? Reply "generate invoice" if correct.
```

### Example 3: Payment Confirmation

**Email:**
```
From: accounts@client.com
Subject: OCS Payment Confirmation
Body: Please confirm receipt of $50,000 wire on 1/15/2026
```

**Derek's Prompt:** `confirm payment`

**MCP Output:**
```
============================================================
EMAIL DRAFT GENERATED
============================================================

To: accounts@client.com
Subject: Re: OCS Payment Confirmation

DRAFT:
------------------------------------------------------------
Hi [Name],

Confirmed - we received payment of $50,000 on 1/15/2026.

Thank you!

Best,
Derek
------------------------------------------------------------

Confidence: 90%
✓ Ready to review and send
============================================================
```

---

## Python API Usage

### Basic Processing

```python
from orchestrator import MCPOrchestrator, format_confidence_report

# Email data
email_data = {
    'subject': 'W9 Request',
    'body': 'Hi Derek, please send W9',
    'sender_email': 'john@example.com',
    'sender_name': 'John Smith',
    'attachments': []
}

# Process with MCP
with MCPOrchestrator() as mcp:
    result = mcp.process_email(email_data, "send w9")
    print(format_confidence_report(result))
```

### Generate Draft from Template

```python
from orchestrator import MCPOrchestrator
from template_processor import TemplateProcessor

email_data = {
    'subject': 'W9 Request',
    'body': 'Please send W9 and wiring instructions',
    'sender_email': 'john@example.com',
    'sender_name': 'John Smith',
    'attachments': []
}

with MCPOrchestrator() as mcp:
    processor = TemplateProcessor(mcp)
    
    # Generate draft
    draft_result = processor.generate_draft_from_template(
        'w9_response',
        email_data
    )
    
    # Format output
    output = processor.format_draft_output(draft_result, email_data)
    print(output)
```

---

## Development Roadmap

### ✅ Phase 0: Complete (Week 1)
- [x] Database schema designed
- [x] SQLite database created
- [x] Bootstrap data loaded
- [x] Core orchestrator built
- [x] Template processor built
- [x] Pattern matching implemented
- [x] Confidence scoring working

### 🔄 Phase 1: In Progress (Week 2)
- [ ] Gmail connector integration
- [ ] Manual email processing workflow
- [ ] Test with 10 real W9 requests
- [ ] Measure edit rates
- [ ] Refine templates based on feedback

### 📋 Phase 2: Planned (Week 3)
- [ ] Add invoice processing (Claude Project integration)
- [ ] Data extraction for NetSuite updates
- [ ] Handle "tell me amount and people" requests
- [ ] Process 5-10 invoice emails

### 📋 Phase 3: Planned (Week 4)
- [ ] Learning loop implementation
- [ ] Compare drafts vs. sent versions
- [ ] Update confidence scores
- [ ] Extract writing patterns
- [ ] Process 20+ emails

### 📋 Phase 4: Planned (Week 5-6)
- [ ] Expand to all 7 patterns
- [ ] Handle text modification requests
- [ ] Discover new patterns organically
- [ ] Goal: 30+ emails processed, 2-3 hours saved/week

### 📋 Phase 5: Planned (Week 7-8)
- [ ] Batch processing automation
- [ ] Scheduled triggers (8 AM, 6 PM)
- [ ] TODO list generation
- [ ] Goal: 50+ emails automated

### 📋 Phase 6: Planned (Week 9-12)
- [ ] Production optimization
- [ ] Error handling refinement
- [ ] Performance monitoring
- [ ] Goal: 60% of drafts sent with <5% edits, 4-5 hours saved/week

---

## Open Questions

### Critical (Need Answers to Proceed)

1. **Claude Projects:**
   - What projects exist?
   - How to access them programmatically?
   - When to use vs. direct Claude reasoning?

2. **Prompt Location:**
   - Where should Derek write prompts?
   - Recommendation: Email body reply to self

3. **Wiring Instructions:**
   - What are Derek's actual wiring details?
   - Need to update w9_response template

### Important (Need for Phase 5)

4. **Trigger Method:**
   - Scheduled batch (8 AM, 6 PM)?
   - Real-time processing?
   - Manual button?
   - Recommendation: Start manual, add automation later

5. **Priority Handling:**
   - How to prioritize multiple [MCP] emails?
   - Chronological? Keywords? Complexity?

6. **TODO List:**
   - Where to send? (Email, Notion, Google Doc)
   - Recommendation: Start with email

### Nice to Have

7. **Mobile Access:**
   - Does Derek need mobile triggers?
   - Gmail app should work initially

8. **Gemini Usage:**
   - When to use Gemini vs. Claude?
   - Recommendation: Claude only initially for consistency

---

## Success Metrics

### Phase 1-2 (Week 2-3)
- ✅ 10 successful template-based drafts
- 🎯 W9 responses require <10% edits
- 🎯 Payment confirmations require <20% edits
- 🎯 Derek comfortable with workflow

### Phase 3-4 (Week 4-6)
- 🎯 30+ emails processed total
- 🎯 Invoice routing works correctly
- 🎯 Learning loop capturing patterns
- 🎯 2-3 hours/week saved

### Phase 5-6 (Week 7-12)
- 🎯 Batch processing reliable
- 🎯 50+ emails automated
- 🎯 60% drafts require <5% edits
- 🎯 4-5 hours/week saved
- 🎯 System operates autonomously

---

## Troubleshooting

### Database Issues

**Problem:** Can't connect to database

```bash
# Check database exists
ls -la ~/MCP/mcp_workflow.db

# Test connection
sqlite3 ~/MCP/mcp_workflow.db ".tables"

# Rebuild if needed
cd ~/MCP
sqlite3 mcp_workflow.db < schema.sql
```

### Template Issues

**Problem:** Template not found

```bash
# Check templates
sqlite3 ~/MCP/mcp_workflow.db "SELECT template_id, template_name FROM templates;"

# Verify template ID is correct
```

### Pattern Matching Issues

**Problem:** Pattern not matching

```bash
# Check patterns
sqlite3 ~/MCP/mcp_workflow.db "SELECT pattern_name, keywords FROM pattern_hints;"

# Test pattern matching with orchestrator
python3 ~/MCP/orchestrator.py
```

---

## Support & Feedback

### Report Issues
1. Check database connection
2. Verify Python environment
3. Test with example data
4. Document exact error message

### Request Features
1. Describe use case
2. Provide email examples
3. Suggest desired behavior

### Track Progress
- Use this README to track completed phases
- Update open questions as they're answered
- Document lessons learned

---

## Version History

**v1.0 (Jan 22, 2026)**
- Initial release
- Database schema finalized
- Core orchestrator complete
- Template processor working
- 7 bootstrap patterns loaded
- 4 templates ready
- Safety system implemented

---

**Document Status:** READY FOR PHASE 1 TESTING

**Next Steps:**
1. Test Gmail connector
2. Process first W9 request
3. Get feedback on draft quality
4. Refine templates as needed
5. Add wiring details to w9_response

---

**END OF README**
