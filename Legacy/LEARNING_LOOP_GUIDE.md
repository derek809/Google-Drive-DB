# MCP Learning Loop - Usage Guide

**Created:** January 22, 2026  
**Status:** ✅ READY TO USE

---

## 🎯 What the Learning Loop Does

The learning loop makes your MCP system **get smarter every time you use it** by:

1. **Comparing** what MCP drafted vs. what you actually sent
2. **Measuring** how much you edited (0-100%)
3. **Learning** your writing patterns and phrases
4. **Updating** confidence scores for patterns and templates
5. **Building** institutional knowledge over time

---

## 📊 How Learning Works

### Edit Percentage Classification:

| Edit % | Outcome | Meaning |
|--------|---------|---------|
| 0-10% | ✅ SUCCESS | Near perfect - MCP nailed it |
| 10-30% | ✅ GOOD | Minor tweaks needed |
| 30-50% | ⚠️ NEEDS WORK | Significant changes |
| 50%+ | ❌ FAILURE | Major rewrite |
| Deleted | ❌ MAJOR FAILURE | Draft was useless |

### What Gets Learned:

**✍️ Writing Patterns:**
- Phrases you use frequently
- Your greeting/closing style
- Transition words
- Examples: "Just wanted to...", "Looping in..."

**👥 Contact Patterns:**
- How you talk to each person
- Formal vs. friendly tone
- Topics you discuss with them

**📈 Template Performance:**
- Success rate per template
- How often each is used
- When they work well vs. poorly

**🎯 Pattern Confidence:**
- Which patterns match accurately
- Which need adjustment

---

## 🚀 How to Use

### Workflow 1: Process New Email

```python
from email_processor import EmailProcessor

processor = EmailProcessor()

# Your email data
email = {
    'subject': 'W9 Request',
    'body': 'Please send W9 and wiring instructions',
    'sender_email': 'john@client.com',
    'sender_name': 'John Client',
    'attachments': []
}

# Process it
result = processor.process_new_email(email, "send w9")

# Get the draft
draft = result['draft']
response_id = result['draft_info']['response_id']

# Review draft, edit if needed, send
```

### Workflow 2: Record What You Actually Sent

```python
# After you send (with or without edits)
final_text = """Hi John,

Here's our W9 form (attached).

Our wiring instructions:
Wells Fargo Bank
Account: 1234567890
Routing: 121000248

Thanks!
Derek"""

# Tell MCP what you sent
learning_result = processor.record_sent_email(response_id, final_text)

# See what it learned
print(f"Outcome: {learning_result['outcome']}")
print(f"Edit %: {learning_result['edit_percentage']}")
print(f"Learned: {learning_result['patterns_learned']}")
```

### Workflow 3: Check Learning Progress

```python
# Get overall stats
stats = processor.get_learning_stats()

print(f"Emails processed: {stats['emails_processed']}")
print(f"Average edit rate: {stats['average_edit_rate']}%")
print(f"Patterns learned: {stats['writing_patterns_learned']}")
print(f"Contacts known: {stats['contacts_learned']}")

# Get top writing patterns
patterns = processor.get_writing_patterns(limit=10)
for p in patterns:
    print(f"  '{p['phrase']}' - used {p['frequency']} times")
```

---

## 💡 Using with Claude Desktop

### Step 1: Process Email

**Tell me:**
```
Process this email with MCP:

Subject: W9 Request
From: john@client.com
Body: Please send W9 and wiring instructions
Prompt: send w9

My MCP is at: C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB
```

**I'll:**
1. Load your database
2. Match the pattern
3. Generate draft
4. Give you the response_id
5. Show you the draft

### Step 2: After You Send

**Tell me:**
```
I sent this final version:

[paste what you actually sent]

Response ID: [the ID I gave you]

Record it to MCP learning loop
```

**I'll:**
1. Compare draft vs. sent
2. Calculate edit percentage
3. Extract new patterns
4. Update confidence scores
5. Show you what was learned

### Step 3: Check Progress

**Tell me:**
```
Show me my MCP learning stats
```

**I'll show:**
- How many emails processed
- Average edit rate
- What patterns learned
- Contact information captured

---

## 📈 Expected Learning Curve

### Week 1: Getting Started
```
Emails: 10
Edit Rate: 30-40%
Status: Learning basics
```

### Week 2: Improving
```
Emails: 25
Edit Rate: 20-30%
Status: Understanding your style
```

### Month 1: Good
```
Emails: 50
Edit Rate: 15-20%
Status: Solid performance
```

### Month 3: Excellent
```
Emails: 150+
Edit Rate: <10%
Status: Truly your assistant
```

---

## 🔍 What You Can Query

### View All Contacts Learned:
```sql
SELECT contact_email, contact_name, interaction_count, preferred_tone
FROM contact_patterns
ORDER BY interaction_count DESC;
```

### View Writing Patterns:
```sql
SELECT phrase, frequency, context
FROM writing_patterns
ORDER BY frequency DESC
LIMIT 20;
```

### View Template Performance:
```sql
SELECT template_id, usage_count, 
       ROUND(success_rate * 100, 1) as success_pct
FROM templates
ORDER BY usage_count DESC;
```

### View Recent Responses:
```sql
SELECT t.subject, r.confidence_score, r.edit_percentage, r.sent
FROM responses r
JOIN threads t ON r.thread_id = t.id
ORDER BY r.created_at DESC
LIMIT 10;
```

---

## 🎓 Tips for Better Learning

### ✅ DO:
- Process similar emails in batches
- Be consistent with your edits
- Tell MCP when you send emails
- Review learning stats weekly

### ❌ DON'T:
- Change your mind about style frequently
- Skip recording sent emails
- Expect perfection immediately
- Stop after just a few emails

---

## 🐛 Troubleshooting

### "Response ID not found"
**Fix:** Make sure you're using the response_id from the process result

### "Database locked"
**Fix:** Close any other programs accessing the database

### "No patterns learned"
**Fix:** Need to record more sent emails - learning needs data!

### "Edit rate not improving"
**Fix:** Check if you're using consistent style. System learns from patterns.

---

## 📊 Example Learning Session

```python
# Process 5 W9 requests
for i in range(5):
    result = processor.process_new_email(w9_emails[i], "send w9")
    
    # Edit and send
    final = edit_draft(result['draft'])
    processor.record_sent_email(result['draft_info']['response_id'], final)

# Check progress
stats = processor.get_learning_stats()
print(f"After 5 emails:")
print(f"  Average edit: {stats['average_edit_rate']}%")
print(f"  Patterns: {stats['writing_patterns_learned']}")

# By email 5, edit rate should be dropping!
```

---

## ✅ Your Learning Loop is Ready!

**Files in LIVE DB folder:**
- ✅ `learning_loop.py` - Core learning engine
- ✅ `email_processor.py` - Complete workflow integration
- ✅ All other MCP files

**Next step:** Start processing emails and watch it learn! 🧠

---

## 🎯 Quick Commands

### In Python:
```python
from email_processor import EmailProcessor
p = EmailProcessor()

# Process
r = p.process_new_email(email, prompt)

# Record
p.record_sent_email(r['draft_info']['response_id'], final_text)

# Check
stats = p.get_learning_stats()
```

### In Claude Desktop:
Just tell me to process emails and record sent versions!

---

**The more you use it, the smarter it gets!** 🚀
