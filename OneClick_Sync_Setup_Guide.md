# MCP One-Click Sync System - Complete Setup Guide

**Version:** 3.0  
**Created:** January 2026  
**What This Does:** One-click button to sync your learning data to Apps Script

---

## 🎯 How It Works

```
YOU:                    DATABASE:               APPS SCRIPT:            YOU:
Process emails    →     Learns patterns   →     Gets updates      →     View dashboard
via Claude              automatically           via sync button         in Google Sheets
```

**The Magic Button:**
```
Double-click icon → Python reads DB → Pushes to Apps Script → Done!
                    (5 seconds)
```

---

## 📋 One-Time Setup (20 Minutes)

### Step 1: Install Python Library (1 minute)

```bash
cd "C:\Users\derek\OneDrive\Desktop\Dilligence\Google Drive DB"
pip install requests
```

Expected output:
```
Successfully installed requests-2.31.0
```

---

### Step 2: Deploy Apps Script as Web App (5 minutes)

1. **Open your Apps Script project**
   - Go to https://script.google.com
   - Open your MCP Batch Processor project

2. **Replace the code**
   - Delete existing code
   - Copy all code from `AppsScript_WithSyncEndpoint.js`
   - Paste into Apps Script editor
   - Click 💾 Save

3. **Deploy as Web App**
   - Click **Deploy** → **New deployment**
   - Click ⚙️ icon next to "Select type"
   - Choose **"Web app"**
   - Configure:
     * Description: "MCP Sync Endpoint"
     * Execute as: **Me (derek@oldcitycapital.com)**
     * Who has access: **Anyone**
   - Click **Deploy**
   - Click **Authorize access**
   - Choose your account
   - Click **Allow**
   - **COPY THE WEB APP URL** (looks like: https://script.google.com/macros/s/ABC123.../exec)
   - Click **Done**

---

### Step 3: Configure Python Script (2 minutes)

1. **Open `sync_to_apps_script.py` in Notepad**
   ```bash
   notepad sync_to_apps_script.py
   ```

2. **Find these lines near the top:**
   ```python
   APPS_SCRIPT_WEB_APP_URL = 'YOUR_APPS_SCRIPT_WEB_APP_URL_HERE'
   GOOGLE_SHEET_ID = 'YOUR_GOOGLE_SHEET_ID_HERE'
   ```

3. **Update APPS_SCRIPT_WEB_APP_URL:**
   - Paste the URL you copied from Apps Script
   - Should look like:
   ```python
   APPS_SCRIPT_WEB_APP_URL = 'https://script.google.com/macros/s/ABC123DEF456.../exec'
   ```

4. **Update GOOGLE_SHEET_ID (optional):**
   - Create a Google Sheet for your dashboard
   - Name it "MCP Learning Dashboard"
   - Copy the ID from the URL:
     ```
     https://docs.google.com/spreadsheets/d/COPY_THIS_PART/edit
     ```
   - Update the line:
   ```python
   GOOGLE_SHEET_ID = '1ABC123DEF456...'
   ```
   - **Share the sheet with your service account email** (if you set up credentials earlier)

5. **Save and close**

---

### Step 4: Copy Files to Your Folder (1 minute)

Copy these files to: `C:\Users\derek\OneDrive\Desktop\Dilligence\Google Drive DB\`

- ✅ `sync_to_apps_script.py`
- ✅ `Sync_MCP_to_Apps_Script.bat`

Your folder should now have:
```
Google Drive DB/
├── mcp_learning.db
├── orchestrator.py
├── template_processor.py
├── (other Python files...)
├── sync_to_apps_script.py         ← NEW
└── Sync_MCP_to_Apps_Script.bat    ← NEW (your button!)
```

---

### Step 5: Create Desktop Icon (2 minutes)

1. **Right-click on `Sync_MCP_to_Apps_Script.bat`**
2. **Click "Send to" → "Desktop (create shortcut)"**
3. **Go to your Desktop**
4. **Right-click the shortcut** → **Properties**
5. **Change name to:** "Sync MCP Learning"
6. **(Optional) Change icon:**
   - Click **"Change Icon..."**
   - Browse to: `C:\Windows\System32\SHELL32.dll`
   - Pick a sync/refresh icon (try icon #238 or #46)
   - Click **OK**
7. **Click OK**

---

### Step 6: Test It! (1 minute)

1. **Double-click the icon on your desktop**
2. **You should see:**
   ```
   ============================================================
             MCP LEARNING SYNC
   ============================================================
   
   📚 Reading from database...
      ✓ 7 patterns loaded
      ✓ 4 templates loaded
      ✓ Statistics calculated
   
   📤 Pushing to Apps Script...
      ✅ Apps Script updated successfully!
      ✓ Patterns cached in Script Properties
      ✓ Ready for batch processing
   
   📊 Updating Google Sheets dashboard...
      ✅ Dashboard updated!
      → View at: https://docs.google.com/spreadsheets/d/...
   
   ============================================================
   ✅ SYNC COMPLETE!
   
   Your Apps Script now has the latest learning data.
   Batch processing will use updated patterns.
   ============================================================
   
   Press Enter to close...
   ```

3. **Verify in Apps Script:**
   - Go to Apps Script editor
   - Run function: `showSyncStatus`
   - Should show "Last Sync" with recent timestamp

---

## ✅ Setup Complete!

You now have a **one-click button** on your desktop!

---

## 🎯 Daily Use (5 Seconds)

### When to Click the Button:

**Option 1: Weekly Sync (Recommended)**
```
Every Friday evening:
1. Double-click "Sync MCP Learning" icon
2. Wait 5 seconds
3. Done!
```

**Option 2: After Processing Many Emails**
```
After processing 10+ emails via Claude Desktop:
1. Double-click icon
2. Apps Script gets fresh patterns
3. Next batch uses improved data
```

**Option 3: Before Batch Processing**
```
Before Apps Script runs overnight:
1. Click icon at 11 PM
2. Ensures latest patterns are used
3. Batch processing at 11:30 PM uses fresh data
```

---

## 📊 What Happens When You Click

### Step 1: Read Database (1 second)
```
✓ Reads mcp_learning.db
✓ Loads all patterns with confidence scores
✓ Loads all templates with usage stats
✓ Calculates learning statistics
```

### Step 2: Push to Apps Script (2 seconds)
```
✓ Calls Apps Script Web App URL
✓ Sends patterns + templates + stats
✓ Apps Script stores in Script Properties
✓ Cached for fast access during batch processing
```

### Step 3: Update Dashboard (2 seconds)
```
✓ Writes summary to Google Sheet
✓ Shows current patterns & confidence
✓ Displays learning statistics
✓ You can view anytime
```

**Total Time: ~5 seconds**

---

## 📈 What Gets Synced

### Patterns:
```
✓ Pattern names
✓ Keywords
✓ Confidence boost scores (improve over time!)
✓ Usage counts (how many times used)
✓ Success rates (% that worked well)
✓ Notes
```

### Templates:
```
✓ Template IDs
✓ Template bodies
✓ Variables needed
✓ Attachments
✓ Usage statistics
```

### Stats:
```
✓ Total patterns (7 initially, grows to 12+)
✓ Total templates (4 initially)
✓ Contacts learned (0 initially, grows to 20+)
✓ Writing patterns (0 initially, grows to 50+)
✓ Emails processed
✓ Average edit rate (starts 30%, drops to <10%)
```

---

## 🔍 How to Verify It's Working

### Check 1: Window Output
```
Should show:
✅ Apps Script updated successfully!
✅ Dashboard updated!
```

### Check 2: Apps Script
```javascript
// Run in Apps Script editor:
showSyncStatus()

// Should show:
Last Sync: 2026-01-22T23:00:00.000Z
Total Patterns: 7
Cached Patterns: 7
✓ System ready for batch processing
```

### Check 3: Google Sheet Dashboard
```
Open your dashboard sheet
Should see:
- STATISTICS section with current numbers
- ACTIVE PATTERNS with confidence scores
- TEMPLATES with usage counts
- Last Updated: [recent timestamp]
```

### Check 4: Batch Processing
```
Next time Apps Script runs:
- Uses fresh patterns (check logs)
- Improved confidence scores
- Better matching
```

---

## 🎨 Google Sheet Dashboard Example

Your dashboard will look like:
```
MCP LEARNING DASHBOARD
Last Updated: 2026-01-22 23:00:00

STATISTICS
Total Patterns          7
Total Templates         4
Contacts Learned        5
Writing Patterns        23
Emails Processed        47
Average Edit Rate       18.3%

ACTIVE PATTERNS
Pattern                 Confidence  Usage  Success Rate  Keywords
invoice_processing      +32         15     94.2%        invoice, fees, mgmt
w9_wiring_request      +25         8      100.0%       w9, wiring
payment_confirmation   +18         3      100.0%       payment, wire
...

TEMPLATES
Template                Usage Count  Success Rate
W9 & Wiring            8            100.0%
Payment Received       3            100.0%
...
```

---

## 🛠️ Troubleshooting

### "Python not found"
```bash
# Check Python installation:
python --version

# If not found, download from python.org
# Make sure "Add to PATH" is checked during install
```

### "sync_to_apps_script.py not found"
```
Make sure the file is in:
C:\Users\derek\OneDrive\Desktop\Dilligence\Google Drive DB\

Check the .bat file path matches your folder location
```

### "Apps Script update failed"
```
1. Check APPS_SCRIPT_WEB_APP_URL is correct in Python script
2. Make sure Apps Script is deployed as Web App
3. Make sure "Who has access" is set to "Anyone"
4. Try redeploying the Web App
```

### "Network error" or "Timeout"
```
1. Check your internet connection
2. Make sure Apps Script URL is accessible
3. Try clicking the button again
```

### "Dashboard update skipped"
```
This is OK! Dashboard is optional.
Apps Script sync still worked.

To enable dashboard:
1. Update GOOGLE_SHEET_ID in Python script
2. Set up service account credentials (see earlier guide)
```

---

## 🔄 Updating the System

### If You Change Database Schema:
```
No action needed! Sync script reads current schema.
```

### If You Add New Patterns:
```
Just click the button! New patterns sync automatically.
```

### If You Want to Update Sync Frequency:
```
Just click when you want to sync.
No schedule needed - you control it!
```

---

## 💡 Pro Tips

### Tip 1: Pin to Taskbar
```
Drag the desktop icon to your Windows taskbar
One-click access without going to desktop!
```

### Tip 2: Check Dashboard Weekly
```
Every Friday, view your Google Sheet dashboard
See how confidence scores improved
Track learning progress
```

### Tip 3: Sync Before Important Batches
```
Before processing 10+ emails:
1. Click sync button
2. Ensures Apps Script has latest patterns
3. Better results on batch processing
```

### Tip 4: Watch the Numbers Grow
```
Week 1:  7 patterns, 4 templates, 0 contacts
Month 1: 10 patterns, 5 templates, 10 contacts
Month 3: 12 patterns, 6 templates, 25 contacts
↑ Your system getting smarter!
```

---

## ✅ Success Checklist

After setup, you should have:
- [ ] Desktop icon called "Sync MCP Learning"
- [ ] Apps Script deployed as Web App
- [ ] Python script configured with Web App URL
- [ ] Test sync completed successfully
- [ ] Apps Script shows recent sync timestamp
- [ ] (Optional) Dashboard sheet displaying data

After first sync:
- [ ] Apps Script `showSyncStatus()` shows data
- [ ] Dashboard sheet exists and has content
- [ ] Batch processing uses cached patterns

---

## 🎉 You're Done!

**Your complete workflow:**

1. ✅ Process emails via Claude Desktop (database learns)
2. ✅ Click desktop icon weekly (syncs to Apps Script)
3. ✅ Apps Script batch processes with fresh patterns
4. ✅ View dashboard in Google Sheets anytime

**That's it! Simple, automated, no schedules to manage.**

---

## 📞 Quick Help

**"How often should I click the button?"**
→ Weekly is perfect. Or after processing 10+ emails.

**"What if I forget to click?"**
→ No problem! Apps Script uses last synced patterns. System keeps working.

**"Can I automate the button click?"**
→ Yes! Use Windows Task Scheduler. But clicking is so easy, why bother? 😊

**"Where's my dashboard?"**
→ https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID

**"It's not working!"**
→ Run `showSyncStatus()` in Apps Script to see what's cached
→ Check error messages when you click the button
→ Verify Web App URL is correct

---

**Happy syncing!** 🚀
