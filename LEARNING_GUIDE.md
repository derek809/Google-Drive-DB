# MCP Learning Database - How It Works

**Created:** January 22, 2026  
**Philosophy:** Start with minimal assumptions, learn from every interaction

---

## 🎯 What Makes This "Learning-First"?

### ✅ What Starts WITH Data (Day 1)
**Only proven patterns from your 97-email analysis:**

1. **7 Email Patterns** (28% invoice, W9 requests, payments, etc.)
2. **4 Templates** (W9, payment, delegation, turnaround)
3. **3 Existing Tools** (Claude Project, Google Script, NetSuite)
4. **3 Safety Rules** (FINRA, SEC, compliance blocks)

**That's it!** Just the essentials.

### ✅ What Starts EMPTY (Learns from use)

**5 Learning Tables** that build automatically:

1. **knowledge_base** - Learns answers to questions
   - Example: "When do I create a JE for partner compensation?"
   - Learns from Derek's actual responses

2. **contact_patterns** - Learns about each person
   - Tom Smith: Formal tone, bullet points
   - Mike Riskind: Friendly, detailed
   - Learns from Derek's sent emails to each person

3. **writing_patterns** - Learns Derek's phrases
   - "Just wanted to make sure..."
   - "Please find..."
   - "Looping in..."
   - Learns from Derek's actual writing

4. **learning_patterns** - Discovers new email types
   - Beyond the initial 7 patterns
   - Finds organic patterns in Derek's workflow

5. **observed_actions** - Learns what Derek does next
   - After invoice request → Updates NetSuite
   - After RR onboarding → Creates calendar event
   - Learns sequences from observation

---

## 📊 Database Status Right Now

```
✅ Bootstrap Data (Loaded):
   Patterns: 7
   Templates: 4
   Tools: 3
   Safety Rules: 3

📚 Learning Tables (Empty - Ready to Learn):
   Knowledge Base: 0
   Contacts: 0
   Writing Patterns: 0
   Discovered Patterns: 0
   Observed Actions: 0
```

---

## 🔄 How Learning Happens

### Step 1: You Process an Email
```
1. You label email [MCP]
2. You add prompt: "[MCP] send w9"
3. MCP generates draft using template
4. You review the draft
```

### Step 2: You Edit (or Don't)
```
Option A: Draft is perfect → You send as-is
Option B: You make minor edits → You send
Option C: You rewrite completely → You send
```

### Step 3: MCP Learns Automatically
```
MCP compares:
- What it generated (draft)
- What you actually sent (final)

Then it learns:
- Edit percentage: 0% = perfect, 50% = needs work
- Pattern success: Updates confidence for this pattern type
- Your phrases: Adds new phrases you used
- Contact tone: Learns how you talk to this person
```

### Step 4: Next Time is Better
```
Next similar email:
- Higher confidence (learned it works)
- Better phrases (uses what you like)
- Right tone (knows this contact)
- Less editing needed
```

---

## 📈 Learning Examples

### Example 1: Contact Learning

**Email 1 to Tom Smith:**
```
Derek's Draft: "Hi Tom, here's the invoice."
Derek's Edit:  "Tom - Invoice attached per our discussion."
```

**MCP Learns:**
- Tom prefers concise, no "Hi"
- Tom likes references to prior discussion
- Stores in contact_patterns table

**Email 2 to Tom Smith:**
```
MCP's Draft: "Tom - Producer statement attached per your request."
Derek's Edit: None needed! ✓
```

---

### Example 2: Pattern Discovery

**Week 1: Derek processes 5 "mandate review" emails**

MCP notices:
- All have keywords: "mandate", "review", "approval"
- All go to George for compliance call
- All use similar response structure

**Week 2: MCP automatically:**
- Creates new pattern: "mandate_review"
- Suggests template
- Routes to George correctly

---

### Example 3: Writing Style

**Derek's Sent Emails contain:**
- "Just wanted to make sure..." (12 times)
- "Please find attached..." (8 times)
- "Looping in..." (15 times)

**MCP learns:**
- These are Derek's preferred transitions
- Uses them in future drafts
- Matches Derek's natural style

---

## 🎓 What Gets Learned Over Time

### Week 1-2 (Phase 1)
- ✅ Contact names and relationships
- ✅ Which templates work best
- ✅ Edit patterns per email type
- ✅ Derek's common phrases

### Week 3-4 (Phase 2)
- ✅ New email patterns discovered
- ✅ Tool routing preferences
- ✅ Confidence adjustments working
- ✅ Tone preferences per contact

### Week 5-8 (Phase 3)
- ✅ Action sequences (what Derek does after each type)
- ✅ Escalation triggers (when to ask vs. handle)
- ✅ Complex decision patterns
- ✅ Context-specific responses

### Week 9-12 (Phase 4)
- ✅ Full institutional knowledge built
- ✅ Minimal editing needed (<5%)
- ✅ Handles novel situations well
- ✅ True "assistant" behavior

---

## 🔍 How to See What's Been Learned

### Check Contact Learnings
```sql
SELECT contact_email, contact_name, preferred_tone, interaction_count 
FROM contact_patterns 
ORDER BY interaction_count DESC;
```

### Check Writing Patterns
```sql
SELECT phrase, frequency, context 
FROM writing_patterns 
ORDER BY frequency DESC 
LIMIT 10;
```

### Check Discovered Patterns
```sql
SELECT pattern_text, times_reinforced, confidence 
FROM learning_patterns 
ORDER BY times_reinforced DESC;
```

### Check Knowledge Base
```sql
SELECT topic, question, answer, confidence 
FROM knowledge_base 
ORDER BY usage_count DESC;
```

---

## 📊 Success Metrics

### Edit Rate (Primary Metric)
- **Week 1:** 30-50% edits (expected - still learning)
- **Week 4:** 20-30% edits (improving)
- **Week 8:** 10-20% edits (good)
- **Week 12:** <10% edits (excellent)

### Confidence Score Accuracy
- **Week 1:** 60% match (confidence vs. outcome)
- **Week 4:** 70% match
- **Week 8:** 80% match
- **Week 12:** 85%+ match

### Pattern Recognition
- **Week 1:** 7 patterns (bootstrap)
- **Week 4:** 10-12 patterns (discovered 3-5 new)
- **Week 8:** 15-18 patterns
- **Week 12:** 20+ patterns (covers 90% of emails)

---

## 🛡️ What Doesn't Change

### Safety Rules (Never Learn)
- FINRA compliance blocks
- SEC regulatory blocks
- Financial data handling
- Legal matter escalation

### Template Structure (Stable)
- Basic template format stays consistent
- Variables can be added
- But core structure doesn't drift

### Core Patterns (Stable)
- The 7 proven patterns stay
- New patterns add to them
- Old patterns don't disappear

---

## 🎯 Data Retention Strategy

### Keep FOREVER
- Pattern hints (learned patterns)
- Templates (proven formats)
- Knowledge base (institutional memory)
- Contact patterns (relationship data)
- Writing patterns (Derek's style)

### Keep 90 DAYS
- Email threads
- Messages
- Response drafts
- What Derek actually sent

### Keep 30 DAYS
- Debug logs
- Error messages
- Processing metadata

**Why?** 
- Forever data = learning that compounds
- 90 day data = operational context
- 30 day data = troubleshooting only

---

## 🚀 How to Use the Learning System

### You Don't Have to Do Anything Special!

**Just use [MCP] labels normally:**
1. Label email
2. Add prompt
3. Review draft
4. Edit if needed
5. Send

**MCP learns automatically from:**
- What you kept in the draft
- What you changed
- What you added
- What you removed
- Who the email was to
- What type of email it was

**You can speed up learning by:**
- Processing similar emails in batches
- Being consistent with edits
- Adding notes when you escalate
- Telling MCP when something works well

---

## 💡 Tips for Better Learning

### DO:
✅ Be consistent with your edits
✅ Process similar emails together
✅ Use templates when they match
✅ Let MCP try (even if confidence is medium)

### DON'T:
❌ Change your mind about tone frequently
❌ Skip feedback on why you edited
❌ Delete without telling MCP why
❌ Expect perfection immediately

---

## 🎓 Learning Feedback Options

### Implicit (Automatic)
MCP learns from:
- Edit percentage
- What you changed
- Whether you sent it
- Time to review/edit

### Explicit (Optional Tags)
You can add:
- `[TEMPLATE]` - "This should be a template"
- `[LEARN-TONE]` - "Remember this tone for this person"
- `[ONE-TIME]` - "Don't learn from this, it's unusual"

---

## 📈 Expected Learning Curve

```
Week 1: 🌱 Seedling
- MCP knows 7 patterns
- Uses 4 templates
- 40% edit rate
- Learning basics

Week 4: 🌿 Growing
- MCP knows 12 patterns
- Uses 6-7 templates
- 25% edit rate
- Understanding context

Week 8: 🌳 Mature
- MCP knows 18 patterns
- Uses 10+ templates
- 15% edit rate
- Handles complexity

Week 12: 🌲 Expert
- MCP knows 20+ patterns
- Creates custom responses
- <10% edit rate
- True assistant
```

---

## ✅ Your Database is Ready!

**Location:** `~/MCP/mcp_learning.db`

**Status:**
- ✅ 13 tables created
- ✅ 7 patterns loaded
- ✅ 4 templates ready
- ✅ 5 learning tables empty (ready to learn)
- ✅ Safety rules active
- ✅ Indexes optimized

**Next Step:** Start processing emails with [MCP] labels!

Every email you process makes the system smarter. 🧠
