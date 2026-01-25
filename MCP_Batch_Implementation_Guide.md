# MCP Batch Processing System - Implementation Guide

**Created:** January 22, 2026  
**Status:** Ready to Deploy  
**Components:** Google Apps Script + Gemini + Claude API + Your Existing MCP Database

---

## 🎯 What This Does

This Google Apps Script system:
1. **Generates batch queue emails** (11 PM nightly)
2. **Let's you fill in instructions** in an HTML table
3. **Intelligently routes to Gemini** when spreadsheet/document data needed
4. **Calls Claude API** with all context pre-gathered
5. **Sends formatted results** back to you
6. **Updates Gmail labels** automatically

---

## 📋 Step-by-Step Setup

### Step 1: Create Google Apps Script Project

1. Go to https://script.google.com
2. Click **"New Project"**
3. Name it: **"MCP Batch Processor"**
4. Delete the default `myFunction()` code
5. Paste the entire contents of `GoogleAppsScript_MCP_Batch.js`
6. Click **💾 Save**

---

### Step 2: Get API Keys

#### Claude API Key:
1. Go to https://console.anthropic.com
2. Navigate to API Keys
3. Create new key
4. Copy the key (starts with `sk-ant-...`)

#### Gemini API Key:
1. Go to https://aistudio.google.com/app/apikey
2. Click **"Create API Key"**
3. Select your Google Cloud project (or create one)
4. Copy the key

---

### Step 3: Configure API Keys in Apps Script

In the Apps Script editor:

1. Click the **▶️ Run** dropdown
2. Select **`setupMCP`**
3. Click **Run**
4. **Authorize** the script (click "Review permissions", then "Allow")

Then, in the Apps Script editor, click **View** > **Logs** to see setup instructions.

Alternatively, run these commands in the Apps Script editor:

```javascript
// Set Claude API key
PropertiesService.getScriptProperties().setProperty(
  'CLAUDE_API_KEY', 
  'sk-ant-your-key-here'
);

// Set Gemini API key
PropertiesService.getScriptProperties().setProperty(
  'GEMINI_API_KEY', 
  'your-gemini-key-here'
);
```

To run these:
1. Paste into the editor temporarily
2. Select the code
3. Click **▶️ Run**
4. Delete the code after running (keys are now stored securely)

---

### Step 4: Deploy as Web App

1. Click **Deploy** > **New deployment**
2. Click the gear icon ⚙️ next to "Select type"
3. Select **"Web app"**
4. Configure:
   - **Description:** MCP Batch Processor
   - **Execute as:** Me (derek@oldcitycapital.com)
   - **Who has access:** Anyone (don't worry, batch ID is unique)
5. Click **Deploy**
6. **Copy the Web App URL** (you'll need it for testing)
7. Click **Done**

---

### Step 5: Set Up Triggers

1. In Apps Script editor, click the **⏰ clock icon** (Triggers) on the left
2. Click **+ Add Trigger** (bottom right)
3. Configure:
   - **Function:** `generateBatchQueue`
   - **Event source:** Time-driven
   - **Type:** Day timer
   - **Time:** 11 PM to 12 AM
4. Click **Save**

This will run the batch queue generator every night at 11 PM.

---

### Step 6: Create Gmail Labels

Run this in Apps Script (or do manually in Gmail):

1. Select the code in editor
2. Select function: **`setupMCP`**
3. Click **▶️ Run**

This creates:
- `[MCP]` - For emails to process
- `[MCP-Done]` - For processed emails
- `[MCP-Review]` - For low-confidence results

Or create manually in Gmail:
1. Click the gear icon > **"See all settings"**
2. Go to **"Labels"** tab
3. Click **"Create new label"**
4. Create: `MCP`, `MCP-Done`, `MCP-Review`

---

## 🧪 Testing the System

### Test 1: Generate Test Batch Queue

1. Label 2-3 test emails with `[MCP]`
2. In Apps Script, select function: **`generateBatchQueue`**
3. Click **▶️ Run**
4. Check your inbox for the batch queue email

### Test 2: Process Test Batch

1. Open the batch queue email
2. Click in the instruction cells
3. Type test instructions:
   - "summarize"
   - "extract key points"
4. Click **"Process Queue Now"** link
5. Wait 2-3 minutes
6. Check inbox for results email

### Test 3: Verify Gemini Integration

Create a test email mentioning "reconcile AP aging" and process it.
Check the logs to verify Gemini was called.

To view logs:
1. Apps Script editor
2. Click **View** > **Executions**
3. Click on latest execution
4. Review logs

---

## 🔧 How It Works

### Architecture Flow:

```
11 PM: Apps Script generates batch queue email
       ↓
7:30 AM: Derek fills in instructions in HTML table
       ↓
7:40 AM: Derek clicks "Process Queue Now" link
       ↓
Apps Script analyzes each email:
  ├─ Needs spreadsheet data? → Call Gemini API
  ├─ Needs document search? → Call Gemini API
  └─ Just email content? → Skip Gemini
       ↓
Apps Script packages everything:
  ├─ Email content
  ├─ Gemini data (if fetched)
  └─ Derek's instruction
       ↓
Call Claude API with complete context
       ↓
Claude synthesizes and responds
       ↓
8:00 AM: Derek receives formatted results email
```

---

## 📊 Gemini Integration

### When Gemini is Called:

**Spreadsheet keywords detected:**
- reconcile, AP aging, AR aging, balance sheet
- compare spreadsheet, analyze budget
- calculate fees, financial data

**Document search keywords:**
- find documents, locate files, search drive
- all mandates, compliance audit, review documents

**Bulk scanning keywords:**
- audit, review all, check compliance

### What Gemini Returns:

Structured JSON data that Claude then interprets:

```json
{
  "files_found": [...],
  "data_extracted": [...],
  "analysis": {...}
}
```

Claude receives this and adds:
- Business context
- Recommendations
- Formatted output for Derek

---

## 🎨 Customization Options

### Change Batch Queue Timing:

Edit the trigger:
1. Click ⏰ Triggers icon
2. Click on existing trigger
3. Change time
4. Save

### Change Email Search Query:

In the code, find:
```javascript
SEARCH_QUERY: 'label:mcp newer_than:1d'
```

Change to:
```javascript
SEARCH_QUERY: 'label:mcp newer_than:2d'  // Last 2 days
```

### Add More Pattern Detection:

In `analyzeDataNeeds()` function, add new keyword arrays:

```javascript
var yourNewKeywords = [
  'keyword1', 'keyword2', 'keyword3'
];

for (var i = 0; i < yourNewKeywords.length; i++) {
  if (instrLower.indexOf(yourNewKeywords[i]) !== -1) {
    needs.needsGemini = true;
    needs.geminiTask = 'your_task_type';
    return needs;
  }
}
```

---

## 🐛 Troubleshooting

### "Authorization required"
**Fix:** Run `setupMCP()` and authorize the script

### "API key not configured"
**Fix:** Run the API key setup commands in Step 3

### "Web app URL not working"
**Fix:** Redeploy the web app (Deploy > Manage deployments > Edit > Version = New)

### "Batch queue email not sending"
**Fix:** 
1. Check trigger is set up correctly
2. Verify Gmail labels exist
3. Check Apps Script execution logs

### "Gemini not being called"
**Fix:**
1. Check Gemini API key is set
2. Verify keywords in email match detection patterns
3. Review logs to see what was detected

### "Claude API errors"
**Fix:**
1. Verify Claude API key is correct
2. Check API quota/limits
3. Review error message in logs

---

## 📈 Expected Performance

### API Usage (per batch run):

**For 5 emails:**
- Gemini calls: 0-2 (only when needed)
- Claude calls: 5 (one per email)
- Total cost: ~$0.15-0.25

**For 10 emails:**
- Gemini calls: 0-4
- Claude calls: 10
- Total cost: ~$0.30-0.50

### Processing Time:

- Queue generation: 5-10 seconds
- Processing 5 emails: 2-3 minutes
- Processing 10 emails: 4-5 minutes

---

## 🔐 Security Notes

### API Keys:
- Stored in Script Properties (encrypted by Google)
- Not visible in code
- Only accessible by your account

### Email Access:
- Script can only access your Gmail
- Runs as you (derek@oldcitycapital.com)
- No one else can trigger it

### Web App Access:
- Unique batch IDs prevent unauthorized access
- Batch data expires after processing
- Only Derek receives results

---

## 📚 Integration with Existing MCP

### Your Python MCP System:

Your existing system (`orchestrator.py`, `learning_loop.py`, etc.) will continue to work for:
- Single email processing in Claude Desktop
- Manual email handling
- Learning from sent emails
- Building knowledge base

### This Apps Script System:

Handles batch processing with:
- Scheduled overnight queue generation
- Gemini integration for data fetching
- Claude API calls for synthesis
- Automated results delivery

### Both Systems Share:

- Same patterns and rules (via your knowledge)
- Same safety overrides
- Same templates
- Compatible output formats

---

## 🎯 Next Steps

### Immediate (This Week):
1. ✅ Complete setup steps above
2. ⏳ Test with 2-3 sample emails
3. ⏳ Verify batch queue email formatting
4. ⏳ Test "Process Queue Now" link
5. ⏳ Review results email format

### Week 2:
1. Process 5-10 real emails
2. Refine Gemini prompts if needed
3. Adjust pattern detection keywords
4. Monitor API costs

### Week 3:
1. Enable overnight batch runs
2. Process 10-20 emails per batch
3. Fine-tune confidence thresholds
4. Optimize for common patterns

---

## 📞 Support

### Check Logs:
Apps Script editor > View > Executions

### Test Individual Functions:
Select function from dropdown > Click Run

### View Stored Properties:
```javascript
var props = PropertiesService.getScriptProperties().getProperties();
Logger.log(props);
```

---

## ✅ Setup Checklist

- [ ] Apps Script project created
- [ ] Code pasted and saved
- [ ] Claude API key configured
- [ ] Gemini API key configured  
- [ ] Deployed as web app
- [ ] Trigger created (11 PM daily)
- [ ] Gmail labels created
- [ ] Test batch queue generated
- [ ] Test processing completed
- [ ] Results email received

---

**Once checklist is complete, your MCP batch system is ready!** 🎉

---

## 🔄 Daily Workflow (Once Set Up)

### Evening:
1. Label emails with `[MCP]` throughout the day
2. System auto-generates queue at 11 PM

### Morning:
1. Open batch queue email (in inbox at 7 AM)
2. Fill in instructions in table
3. Click "Process Queue Now"
4. Wait 2-3 minutes
5. Review results email
6. Use outputs as needed

**That's it!** System handles the rest automatically.
