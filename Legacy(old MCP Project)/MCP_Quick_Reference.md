# MCP System - Quick Reference Card

**For Daily Use**

---

## 🚀 Two Ways to Use MCP

### Option 1: Single Email (Claude Desktop)
**When:** Need immediate processing  
**How:** Talk to me in Claude Desktop

```
"Process this MCP email:
Subject: [paste]
From: [paste]
Body: [paste]
Instruction: [what you want]"
```

**I'll:** Use your local MCP database, generate draft, learn from edits

---

### Option 2: Batch Processing (Google Apps Script)
**When:** Multiple emails to process  
**How:** Label emails throughout the day

```
1. Label email with [MCP] in Gmail
2. Next morning: receive batch queue email
3. Fill in instructions in table
4. Click "Process Queue Now"
5. Receive results in 2-3 minutes
```

**System:** Automatically calls Gemini when needed, Claude for synthesis

---

## 📝 Example Instructions

### For Invoices:
- `extract invoice data`
- `generate invoice`
- `tell me amount and recipients`

### For Templates:
- `send w9`
- `confirm payment`
- `loop in eytan`

### For Analysis:
- `reconcile ap`
- `find documents`
- `summarize`
- `check compliance`

### Special:
- `SKIP` - Don't process
- Leave blank - Auto-determine

---

## 🤖 When Gemini Gets Involved

Automatically called when you mention:
- Spreadsheets (reconcile, AP aging, balance sheet)
- Document search (find documents, locate files)
- Bulk operations (audit, review all)

You don't need to ask for it - system decides automatically!

---

## 📊 Your MCP Database

**Location (Windows):**
```
C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB\mcp_learning.db
```

**Contains:**
- 7 proven patterns
- 4 email templates
- Learning from your sent emails
- Contact preferences
- Writing patterns

**Gets Smarter:** Every email you process and send

---

## 🎯 Common Commands (Claude Desktop)

### Check Status:
```
"Show me my MCP database status"
"What patterns has MCP learned?"
"How many contacts in MCP?"
```

### Process Email:
```
"Process this MCP email: [paste content]"
```

### View Templates:
```
"Show me the W9 template"
"List all MCP templates"
```

### Learning Stats:
```
"Show MCP learning stats"
"What writing patterns have been learned?"
```

---

## 🏷️ Gmail Labels

**You Apply:**
- `[MCP]` - Email needs processing

**System Applies:**
- `[MCP-Done]` - Successfully processed
- `[MCP-Review]` - Low confidence, check carefully

---

## ⚡ Quick Tips

### DO:
- ✅ Label emails throughout the day
- ✅ Be specific with instructions
- ✅ Review drafts before sending
- ✅ Tell MCP when you send (for learning)

### DON'T:
- ❌ Label FINRA/SEC emails (system blocks)
- ❌ Skip recording sent emails (learning needs this)
- ❌ Expect perfection immediately (learns over time)

---

## 🔧 Troubleshooting

### "Can't find database"
**Tell me:** 
```
"My MCP is at: C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB"
```

### "Batch queue not received"
**Check:**
1. Emails labeled `[MCP]` yesterday?
2. Trigger set up in Apps Script?
3. Check spam folder

### "Low confidence warning"
**Means:** MCP is unsure - review carefully before using

---

## 📈 Expected Performance

### Week 1:
- Edit rate: 30-40%
- Processing: Learning basics

### Month 1:
- Edit rate: 15-20%
- Processing: Solid performance

### Month 3:
- Edit rate: <10%
- Processing: True assistant

---

## 🎓 Learning Features

### Automatic Learning:
- Your writing style
- Contact preferences
- Common patterns
- What works / doesn't work

### You Can Speed Learning:
- Process similar emails together
- Be consistent with edits
- Add notes when unusual

---

## 📞 Need Help?

### In Claude Desktop:
Just ask me! I can:
- Check database status
- Process emails
- Show templates
- Explain patterns
- Debug issues

### Common Questions:

**"Process isn't working"**
```
"Test my MCP system"
"Check MCP database connection"
```

**"Want to see what's learned"**
```
"Show MCP learning stats"
"List MCP contacts"
"Show writing patterns"
```

**"Need to update template"**
```
"Update the W9 template with new wiring info"
```

---

## 🎯 Daily Workflow

### Morning:
1. Check batch results email (if used overnight)
2. Review and use outputs
3. Mark any issues for review

### Throughout Day:
1. Label emails `[MCP]` as they come in
2. Or process immediately in Claude Desktop
3. Send drafts (after review)

### Evening:
- System auto-generates queue at 11 PM
- Nothing for you to do!

### Next Morning:
- Receive queue email
- Fill instructions
- Click process
- Get results

---

## 💡 Pro Tips

### Batch Processing:
- Use for routine emails
- Great for invoice batches
- Perfect for W9 requests

### Single Processing:
- Use for urgent emails
- Use for complex decisions
- Use when you want immediate results

### Best Results:
- Combine both methods
- Process similar types together
- Let system learn your patterns

---

## ✅ Quick Health Check

**System is working if:**
- ✅ Can process test email in Claude Desktop
- ✅ Batch queue email arrives at 11 PM
- ✅ "Process Now" link works
- ✅ Results email arrives in 2-3 minutes
- ✅ Drafts match your style

**System needs attention if:**
- ❌ High edit rates (>30%) after month 1
- ❌ Frequent errors in results
- ❌ Missing batch queue emails
- ❌ API errors in logs

---

## 🚀 You're Ready!

**Remember:**
1. Label emails `[MCP]`
2. System processes (batch or immediate)
3. Review outputs
4. Use as needed
5. System learns and improves

**Every email makes it smarter!** 🧠

---

**Keep this card handy for daily reference!**
