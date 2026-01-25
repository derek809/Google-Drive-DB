# MCP LIVE DB - Installation Guide for Windows

**Created:** January 22, 2026  
**Location:** Place in `C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB`

---

## 📦 What's in This Folder

### Core System Files:
- **mcp_learning.db** (132KB) - Your learning database
- **orchestrator.py** (19KB) - Main processing engine
- **template_processor.py** (10KB) - Draft generator
- **process_email.py** (2KB) - Simple interface
- **test_suite.py** (14KB) - Complete test suite

### Documentation:
- **QUICK_START.txt** - Quick reference
- **README.md** - Complete documentation
- **DATABASE_BREAKDOWN.md** - Full database explanation
- **LEARNING_GUIDE.md** - How the learning system works
- **IMPLEMENTATION_SUMMARY.md** - What's built and next steps
- **QUICK_REFERENCE.md** - Daily use guide

### Schema:
- **learning_schema.sql** - Database schema (for reference)

---

## 🚀 Installation Steps

### Step 1: Place Files
✅ You've already done this! Just keep this folder at:
```
C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB
```

### Step 2: Verify Python
Open Command Prompt or PowerShell and run:
```bash
python --version
```

Should show: `Python 3.x.x`

If not installed:
1. Download from https://python.org
2. Install (check "Add to PATH")
3. Restart terminal

### Step 3: Install SQLite (Already Included in Python!)
SQLite comes with Python, so you're good to go!

### Step 4: Test the System
In Command Prompt, navigate to this folder:
```bash
cd "C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB"
python test_suite.py
```

Should show: `🎉 ALL TESTS PASSED!`

---

## 🎯 How to Use with Claude Desktop

### Method 1: Tell Claude the Path (Easiest)
Just say to Claude:
```
My MCP database is at:
C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB

Process this email with MCP: [paste email]
```

### Method 2: Quick Commands
Once Claude knows the path, you can just say:
- "Show me MCP patterns"
- "Process this email with MCP"
- "Check MCP database status"

---

## 📊 Database Contents

**Bootstrap Data (Day 1):**
- ✅ 7 Email Patterns (invoice, W9, payment, etc.)
- ✅ 4 Templates (W9, payment, delegation, turnaround)
- ✅ 3 Existing Tools (Claude Project, Script, NetSuite)
- ✅ 3 Safety Rules (FINRA, SEC, compliance)

**Learning Tables (Empty - Ready to Learn):**
- 📚 Knowledge Base (0 entries)
- 👥 Contact Patterns (0 entries)
- ✍️ Writing Patterns (0 entries)
- 🔍 Discovered Patterns (0 entries)
- 🎯 Observed Actions (0 entries)

---

## 🔧 Quick Reference Commands

### Check Database Status:
```bash
cd "C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB"
python -c "from orchestrator import MCPOrchestrator; print('✅ System working!')"
```

### Run Tests:
```bash
python test_suite.py
```

### View Templates:
```bash
sqlite3 mcp_learning.db "SELECT template_id, template_name FROM templates;"
```

(Note: On Windows, you may need to install sqlite3 command-line tool separately,
but you can always use Python to query the database)

### View Patterns:
```bash
python -c "import sqlite3; conn=sqlite3.connect('mcp_learning.db'); cursor=conn.cursor(); cursor.execute('SELECT pattern_name, confidence_boost FROM pattern_hints'); print('\n'.join([f'{row[0]}: +{row[1]}' for row in cursor.fetchall()]))"
```

---

## 💡 Usage Examples

### Example 1: Process W9 Request
**Say to Claude:**
```
My MCP is at: C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB

Process this email:
Subject: W9 Request
From: john@example.com
Body: Hi Derek, can you send your W9 and wiring instructions?
Prompt: send w9
```

**Claude will:**
1. Load your database
2. Match the W9 pattern
3. Use the w9_response template
4. Generate a draft for you
5. Log everything to the learning database

---

### Example 2: Check What's Learned
**Say to Claude:**
```
Check my MCP database at LIVE DB folder.
How many contacts have been learned?
Show me the writing patterns.
```

---

### Example 3: View a Template
**Say to Claude:**
```
Show me the W9 template from my MCP database in the LIVE DB folder
```

---

## 📁 File Structure

```
LIVE DB/
├── mcp_learning.db          ← Your learning database
├── orchestrator.py           ← Main processor
├── template_processor.py     ← Draft generator
├── process_email.py         ← Simple interface
├── test_suite.py            ← Tests
├── learning_schema.sql      ← Database schema
├── QUICK_START.txt          ← Quick reference
├── README.md                ← Full docs
├── DATABASE_BREAKDOWN.md    ← Database details
├── LEARNING_GUIDE.md        ← How learning works
├── IMPLEMENTATION_SUMMARY.md ← What's built
├── QUICK_REFERENCE.md       ← Daily guide
└── THIS_FILE.md             ← Windows setup
```

---

## 🎓 Next Steps

### Immediate:
1. ✅ Files in place
2. ⏳ Test with: `python test_suite.py`
3. ⏳ Tell Claude the path
4. ⏳ Process your first email

### This Week:
1. Add your wiring instructions to W9 template
2. Process 10 W9 requests
3. Process 5 payment confirmations
4. Watch the learning tables grow!

### This Month:
1. Process 30+ emails
2. Let MCP learn your style
3. Discover new patterns
4. Reduce editing needed

---

## 🛡️ Safety Features

**Active Protections:**
- ❌ FINRA audit emails → Never draft (human only)
- ❌ SEC emails → Always escalate (requires review)
- ❌ Compliance violations → Never draft (legal risk)

**Privacy:**
- ✅ Everything stays local on your computer
- ✅ Database in your OneDrive (backed up automatically)
- ✅ No data sent anywhere except to Claude when you ask

---

## 💾 Backup Strategy

**Good news:** Your database is already in OneDrive!

The folder location means:
- ✅ Auto-synced to OneDrive cloud
- ✅ Accessible from any device with OneDrive
- ✅ Protected from local drive failure

**Additional backup (optional):**
- Copy `mcp_learning.db` weekly to another location
- Or let OneDrive handle it (already doing this!)

---

## 🐛 Troubleshooting

### "Python not found"
**Fix:** Install Python from python.org (check "Add to PATH")

### "Module not found"
**Fix:** You're in the wrong directory. Use:
```bash
cd "C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB"
```

### "Database locked"
**Fix:** Close any other programs using the database (like DB Browser)

### Tests failing
**Fix:** Make sure you're in the LIVE DB folder:
```bash
cd "C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB"
python test_suite.py
```

---

## 📞 Getting Help

**In Claude Desktop, just ask:**
- "Why isn't my MCP working?"
- "Test my MCP database"
- "Show me what's in my MCP database"
- "Process an email with MCP"

**Path to tell Claude:**
```
C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB
```

---

## ✅ Installation Complete!

Your MCP system is ready to use. Just tell Claude:

**"My MCP database is at: C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB"**

Then start processing emails! 🚀

---

**Questions? Just ask Claude - I'm here to help!** 💬
