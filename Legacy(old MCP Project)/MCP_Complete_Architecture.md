# MCP Complete System Architecture

**Version 2.0 - With Batch Processing + Gemini**  
**Created:** January 22, 2026

---

## 🏗️ Complete System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         DEREK                                │
│                                                              │
│  Daily Actions:                                              │
│  • Label emails [MCP] in Gmail                              │
│  • Talk to Claude Desktop for immediate processing          │
│  • Fill batch queue table (morning)                         │
│  • Review results and send (with optional edits)            │
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┬─────────────────┐
        │                         │                 │
        ▼                         ▼                 ▼
┌───────────────┐     ┌────────────────────┐  ┌──────────────┐
│ CLAUDE        │     │ GOOGLE APPS        │  │ LOCAL        │
│ DESKTOP       │     │ SCRIPT             │  │ PYTHON MCP   │
│               │     │ (Batch System)     │  │              │
│ Single email  │     │                    │  │ Database     │
│ processing    │     │ • Generates queue  │  │ Learning     │
│               │     │ • Detects needs    │  │ Patterns     │
│               │     │ • Calls APIs       │  │ Templates    │
│               │     │ • Updates labels   │  │              │
└───────┬───────┘     └─────────┬──────────┘  └──────┬───────┘
        │                       │                    │
        │             ┌─────────┴──────────┐        │
        │             │                    │        │
        │             ▼                    ▼        │
        │     ┌───────────────┐    ┌──────────────┐│
        │     │ GEMINI API    │    │ CLAUDE API   ││
        │     │               │    │              ││
        │     │ • Spreadsheet │    │ • Synthesis  ││
        │     │   analysis    │    │ • Reasoning  ││
        │     │ • Document    │    │ • Drafting   ││
        │     │   search      │    │ • Learning   ││
        │     │ • Data        │    │              ││
        │     │   extraction  │    │              ││
        │     └───────────────┘    └──────────────┘│
        │                                           │
        └───────────────────┬───────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLITE DATABASE                           │
│                  (mcp_learning.db)                           │
│                                                              │
│  • 7 Proven Patterns                                         │
│  • 4 Email Templates                                         │
│  • 3 Existing Tools                                          │
│  • 5 Learning Tables (contact patterns, writing style, etc.) │
│  • Safety Rules & Overrides                                  │
│  • Complete Email History                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Processing Flow Comparison

### Single Email (Claude Desktop):

```
1. Derek receives email
   ↓
2. Derek opens Claude Desktop
   ↓
3. Derek: "Process this MCP email: [content]"
   ↓
4. Claude (me):
   • Reads email
   • Checks local SQLite database
   • Matches patterns
   • Generates draft
   ↓
5. Shows Derek draft immediately
   ↓
6. Derek reviews/edits/sends
   ↓
7. Derek: "I sent this: [final version]"
   ↓
8. Claude updates database with learning
```

**Speed:** Immediate (30 seconds)  
**Best for:** Urgent, complex, or single emails  
**Uses:** Local MCP database only

---

### Batch Processing (Google Apps Script):

```
Throughout Day:
├─ 2:00 PM: Derek labels email #1 [MCP]
├─ 3:30 PM: Derek labels email #2 [MCP]
├─ 4:45 PM: Derek labels email #3 [MCP]
└─ 5:15 PM: Derek labels email #4 [MCP]
         ↓
11:00 PM: Apps Script auto-runs
         ↓
Apps Script:
├─ Searches Gmail for [MCP] emails
├─ Finds 4 emails
├─ Generates HTML table email
└─ Sends to Derek
         ↓
7:30 AM: Derek receives queue email
         ↓
Derek fills in table:
├─ Email 1: "extract invoice data"
├─ Email 2: "send w9"
├─ Email 3: "confirm payment"
└─ Email 4: "reconcile ap"
         ↓
7:40 AM: Derek clicks "Process Queue Now"
         ↓
Apps Script processes each:
         ↓
┌────────┴────────┐
│                 │
▼                 ▼
For Email 1:      For Email 4:
├─ Analyze        ├─ Analyze
├─ Need Gemini?   ├─ Need Gemini?
│  → NO            │  → YES!
├─ Call Claude    ├─ Call Gemini
│  with email     │  → Get spreadsheet data
└─ Get draft      ├─ Call Claude
                  │  with email + Gemini data
                  └─ Get analysis
         ↓
8:00 AM: Derek receives results email
         ↓
Derek reviews all 4 outputs
         ↓
Derek uses outputs as needed
         ↓
Apps Script updates labels:
└─ [MCP] → [MCP-Done]
```

**Speed:** Next morning (overnight prep)  
**Best for:** Routine emails, batch work, invoice processing  
**Uses:** Gemini API (when needed) + Claude API + Apps Script

---

## 🔄 Data Flow Diagram

### Information Sources:

```
┌──────────────────────────────────────────────┐
│            INFORMATION SOURCES               │
├──────────────────────────────────────────────┤
│                                              │
│  1. Gmail (via Connector or Apps Script)     │
│     • Email threads                          │
│     • Attachments                            │
│     • Labels                                 │
│                                              │
│  2. SQLite Database                          │
│     • Patterns                               │
│     • Templates                              │
│     • Learning history                       │
│     • Contact preferences                    │
│                                              │
│  3. Gemini API (when needed)                 │
│     • Google Drive files                     │
│     • Spreadsheet data                       │
│     • Document content                       │
│                                              │
│  4. Derek's Input                            │
│     • Instructions                           │
│     • Edits                                  │
│     • Feedback                               │
│                                              │
└──────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────┐
│         CLAUDE ORCHESTRATION                 │
├──────────────────────────────────────────────┤
│                                              │
│  • Reads all sources                         │
│  • Understands context                       │
│  • Makes decisions                           │
│  • Synthesizes information                   │
│  • Generates actionable outputs              │
│                                              │
└──────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────┐
│               OUTPUTS TO DEREK               │
├──────────────────────────────────────────────┤
│                                              │
│  • Email drafts (ready to send)              │
│  • Data extractions (for NetSuite)           │
│  • Summaries & analysis                      │
│  • Recommendations                           │
│  • Formatted reports                         │
│                                              │
└──────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────┐
│            LEARNING FEEDBACK                 │
├──────────────────────────────────────────────┤
│                                              │
│  • Derek's edits captured                    │
│  • Patterns refined                          │
│  • Confidence adjusted                       │
│  • Templates improved                        │
│  • Contact preferences learned               │
│                                              │
└──────────────────────────────────────────────┘
```

---

## 🎯 Decision Logic: When to Use What

### Use Claude Desktop When:
- ✅ Need immediate response
- ✅ Email requires judgment
- ✅ Want to review step-by-step
- ✅ Complex or sensitive matter
- ✅ One-off processing

### Use Batch Processing When:
- ✅ Multiple routine emails
- ✅ Can wait until morning
- ✅ Invoice processing
- ✅ Template-based responses
- ✅ W9 requests
- ✅ Payment confirmations

### Use Gemini (Auto-detected) When:
- ✅ Spreadsheet analysis needed
- ✅ Document search required
- ✅ Bulk document scanning
- ✅ Data extraction from Drive
- ✅ Financial reconciliation

---

## 🔐 Security & Privacy

### Data Storage:

```
┌─────────────────────────────────────────────┐
│          WHERE YOUR DATA LIVES              │
├─────────────────────────────────────────────┤
│                                             │
│  Local Computer:                            │
│  • SQLite database (encrypted by OneDrive)  │
│  • Python MCP code                          │
│  • All learning data                        │
│                                             │
│  Google Cloud:                              │
│  • Apps Script code (your Google account)   │
│  • Script properties (encrypted)            │
│  • Temporary batch data (deleted after use) │
│                                             │
│  APIs:                                      │
│  • Claude API (processes, doesn't store)    │
│  • Gemini API (processes, doesn't store)    │
│                                             │
│  NOT Stored Anywhere:                       │
│  • API keys visible in code                 │
│  • Email content after processing           │
│  • Personal data in external databases      │
│                                             │
└─────────────────────────────────────────────┘
```

### API Key Security:

```
✅ SECURE:
• Stored in Script Properties (Google encrypts)
• Stored in environment variables (local)
• Never in code
• Never in version control
• Only accessible by you

❌ INSECURE:
• Hardcoded in scripts
• Committed to GitHub
• Shared in emails
• Stored in plain text files
```

---

## 📊 Component Responsibilities

### Google Apps Script:
**Role:** Batch coordinator
- ✅ Generate queue emails
- ✅ Parse instructions
- ✅ Detect data needs
- ✅ Call Gemini when needed
- ✅ Call Claude with context
- ✅ Format results
- ✅ Update Gmail labels
- ❌ Does NOT store learning (that's SQLite)
- ❌ Does NOT make decisions (that's Claude)

### Gemini API:
**Role:** Data fetcher
- ✅ Search Google Drive
- ✅ Extract spreadsheet data
- ✅ Scan documents
- ✅ Return structured JSON
- ❌ Does NOT interpret data
- ❌ Does NOT make recommendations
- ❌ Does NOT generate email text

### Claude API:
**Role:** Synthesizer & writer
- ✅ Understand context
- ✅ Make judgments
- ✅ Draft emails
- ✅ Provide recommendations
- ✅ Format outputs
- ✅ Apply business context
- ❌ Does NOT fetch external data (Gemini does)
- ❌ Does NOT persist memory (SQLite does)

### SQLite Database:
**Role:** Memory & learning
- ✅ Store patterns
- ✅ Store templates
- ✅ Store learning history
- ✅ Store contact preferences
- ✅ Store writing patterns
- ✅ Provide context to Claude
- ❌ Does NOT process emails
- ❌ Does NOT generate text

### Claude Desktop (Local):
**Role:** Interactive processing
- ✅ Direct conversation with Derek
- ✅ Access local SQLite
- ✅ Generate drafts
- ✅ Learn from feedback
- ✅ Test and debug
- ❌ Does NOT batch process
- ❌ Does NOT schedule

---

## 🎓 Learning Loop

### How the System Gets Smarter:

```
Week 1:
┌──────────────────────────────────┐
│ Bootstrap Data Only              │
│ • 7 patterns                     │
│ • 4 templates                    │
│ • No contacts learned            │
│ Edit rate: 30-40%                │
└──────────────────────────────────┘
         ↓ Process 10 emails
Week 2:
┌──────────────────────────────────┐
│ Starting to Learn                │
│ • 7 patterns + 2 discovered      │
│ • 4 templates (refined)          │
│ • 5-10 contacts learned          │
│ • 10-20 phrases captured         │
│ Edit rate: 25-30%                │
└──────────────────────────────────┘
         ↓ Process 20 more emails
Month 1:
┌──────────────────────────────────┐
│ Solid Understanding              │
│ • 10-12 patterns                 │
│ • 6-7 templates                  │
│ • 20-30 contacts known           │
│ • 50+ phrases learned            │
│ Edit rate: 15-20%                │
└──────────────────────────────────┘
         ↓ Process 50 more emails
Month 3:
┌──────────────────────────────────┐
│ True Assistant                   │
│ • 15-20 patterns                 │
│ • 10+ templates                  │
│ • 40+ contacts with preferences  │
│ • 100+ phrases mastered          │
│ Edit rate: <10%                  │
└──────────────────────────────────┘
```

---

## ✅ System Health Checklist

### Daily Health Indicators:

```
✅ GREEN (Healthy):
• Batch queue arrives on time
• Process link works
• Results arrive in 2-3 minutes
• Drafts match Derek's style
• Edit rate declining
• No API errors

⚠️ YELLOW (Attention Needed):
• Occasional API timeouts
• Edit rate stagnant (not improving)
• Some pattern mismatches
• Confidence scores inconsistent

❌ RED (Needs Fix):
• Batch queue not arriving
• Frequent API errors
• High edit rates (>30%) after month 1
• Process link broken
• Results not arriving
```

---

## 🚀 Future Enhancements

### Planned (Not Built Yet):

1. **NetSuite Integration**
   - Direct data push
   - No manual copy-paste

2. **Portal Integration**
   - Auto-update records
   - Pull mandate data

3. **Automated Producer Statements**
   - Weekly export from NetSuite
   - Auto-email distribution

4. **Meeting Transcription Integration**
   - Krisp app integration
   - Auto-summary and action items

5. **Mobile Trigger**
   - Process emails from phone
   - Quick voice commands

---

## 📞 Support & Maintenance

### For Issues:

**Claude Desktop:**
- Just ask me! I can debug the local system

**Apps Script:**
- View > Executions (check logs)
- View > Triggers (verify schedule)

**APIs:**
- Check quotas/limits
- Verify keys in Script Properties

### Monthly Maintenance:

- [ ] Review API costs
- [ ] Check learning stats
- [ ] Update templates if needed
- [ ] Refine pattern keywords
- [ ] Back up SQLite database

---

## 🎯 Success Metrics

### Target Performance (Month 3):

- **Time Saved:** 4-5 hours/week
- **Edit Rate:** <10%
- **Draft Acceptance:** 60%+ sent with <5 edits
- **Pattern Coverage:** 90% of emails matched
- **Confidence Accuracy:** 85%+ (score matches outcome)
- **API Cost:** <$50/month

---

**Your complete MCP system is ready to deploy!** 🎉

**Next Step:** Follow the Implementation Guide to set up Google Apps Script.
