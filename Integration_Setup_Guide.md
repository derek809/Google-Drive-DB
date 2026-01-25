# MCP System Integration Guide
## Connecting Google Apps Script to SQLite Database

**Version:** 2.0  
**Created:** January 22, 2026  
**Purpose:** Bridge Apps Script batch processor with Python MCP database

---

## 🎯 What This Integration Does

Connects your two systems so they work together:

```
┌─────────────────────────────────────┐
│   GOOGLE APPS SCRIPT                │
│   (Batch Email Processing)          │
└──────────────┬──────────────────────┘
               │
               │ HTTP API Calls
               ▼
┌─────────────────────────────────────┐
│   PYTHON API SERVER                 │
│   (Flask REST API)                  │
└──────────────┬──────────────────────┘
               │
               │ SQLite Queries
               ▼
┌─────────────────────────────────────┐
│   SQLITE DATABASE                   │
│   (mcp_learning.db)                 │
│   • 7 Patterns                      │
│   • 4 Templates                     │
│   • Learning Data                   │
│   • Contact Preferences             │
└─────────────────────────────────────┘
```

**Benefits:**
- ✅ Apps Script gets real-time access to your patterns
- ✅ Apps Script can use learned contact preferences
- ✅ Usage stats automatically updated in SQLite
- ✅ Single source of truth for all data
- ✅ Automatic fallback if API unavailable

---

## 📋 Prerequisites

### Required:
- [x] Python 3.7+ installed
- [x] SQLite database exists (`mcp_learning.db`)
- [x] Google Apps Script project created
- [x] Basic command line knowledge

### To Install:
- [ ] Flask (Python web framework)
- [ ] Flask-CORS (for API access)

---

## 🚀 Step 1: Install Python Dependencies

### On Windows:

```bash
# Open Command Prompt or PowerShell
cd "C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB"

# Install Flask
pip install flask flask-cors

# Verify installation
python -c "import flask; print('Flask installed:', flask.__version__)"
```

### On Mac/Linux:

```bash
# Open Terminal
cd ~/Documents/MCP

# Install Flask
pip3 install flask flask-cors --break-system-packages

# Verify installation
python3 -c "import flask; print('Flask installed:', flask.__version__)"
```

**Expected Output:**
```
Flask installed: 3.0.0
```

---

## 🔧 Step 2: Set Up Python API Server

### 1. Place API Server File

Put `mcp_api_server.py` in your MCP directory:
```
C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB\
├── mcp_learning.db
├── orchestrator.py
├── template_processor.py
└── mcp_api_server.py  ← New file
```

### 2. Update Database Path (if needed)

Open `mcp_api_server.py` and check line 16:

```python
DB_PATH = os.path.join(os.path.dirname(__file__), 'mcp_learning.db')
```

If your database has a different name or location, update this line.

### 3. Test the API Server

```bash
# Start the server
python mcp_api_server.py
```

**Expected Output:**
```
============================================================
MCP SQLite API Server
============================================================
Database: C:\...\mcp_learning.db
Starting server on http://localhost:5000

Available endpoints:
  GET  /api/health - Health check
  GET  /api/stats - System statistics
  GET  /api/patterns - All patterns
  ... (more endpoints listed)
============================================================

 * Running on http://0.0.0.0:5000
```

### 4. Test Health Endpoint

Open a new terminal/command prompt:

```bash
# Test API (Windows PowerShell)
curl http://localhost:5000/api/health

# Or use browser: http://localhost:5000/api/health
```

**Expected Response:**
```json
{
  "success": true,
  "status": "healthy",
  "database": "connected",
  "patterns_loaded": 7,
  "timestamp": "2026-01-22T..."
}
```

✅ **If you see this, your API is working!**

---

## 🔧 Step 3: Update Google Apps Script

### 1. Add SQLite Integration Code

In your Apps Script project:

1. Create new file: **"SQLiteIntegration.gs"**
2. Paste the contents of `GoogleAppsScript_WithSQLite.js`
3. Click **💾 Save**

### 2. Update Configuration

Find the `CONFIG` object (top of file) and update:

```javascript
var CONFIG = {
  DEREK_EMAIL: 'derek@oldcitycapital.com',
  SEARCH_QUERY: 'label:mcp newer_than:1d',
  MCP_LABEL: 'MCP',
  DONE_LABEL: 'MCP-Done',
  REVIEW_LABEL: 'MCP-Review',
  SCRIPT_URL: ScriptApp.getService().getUrl(),
  
  // IMPORTANT: Update these
  PYTHON_API_URL: 'http://localhost:5000/api',  // ← Your API URL
  USE_PYTHON_API: true  // ← Set to true
};
```

**If API is on different computer:**
```javascript
PYTHON_API_URL: 'http://192.168.1.100:5000/api',  // Use actual IP
```

### 3. Test Connection from Apps Script

In Apps Script editor:

1. Select function: `testPythonAPIConnection`
2. Click **▶️ Run**
3. View > **Execution log**

**Expected Log:**
```
Testing Python API connection...
API URL: http://localhost:5000/api
Calling Python API: GET http://localhost:5000/api/health
✓ Python API call successful
✓ API is healthy
  Database: connected
  Patterns loaded: 7
  Timestamp: 2026-01-22T...
```

---

## 🧪 Step 4: Test Integration

### Test 1: Get Patterns

```javascript
// In Apps Script, run:
function testGetPatterns() {
  var patterns = getSQLitePatterns();
  Logger.log('Loaded patterns: ' + patterns.length);
  patterns.forEach(function(p) {
    Logger.log('  - ' + p.pattern_name + ' (+' + p.confidence_boost + '%)');
  });
}
```

**Expected:**
```
Loaded patterns: 7
  - w9_wiring_request (+20%)
  - invoice_processing (+15%)
  - payment_confirmation (+15%)
  ...
```

### Test 2: Match Pattern

```javascript
// In Apps Script, run:
function testPatternMatch() {
  var emailData = {
    subject: 'W9 Request',
    body: 'Please send your W9 form',
    sender: 'test@example.com'
  };
  
  var match = matchEmailToPattern(emailData, 'send w9');
  
  if (match) {
    Logger.log('Matched pattern: ' + match.pattern_name);
    Logger.log('Confidence boost: +' + match.confidence_boost);
    Logger.log('Matched keywords: ' + match.matched_keywords.join(', '));
  }
}
```

**Expected:**
```
Calling Python API: POST http://localhost:5000/api/match-pattern
✓ Python API call successful
SQLite pattern match: w9_wiring_request
  Confidence boost: +20
  Matched keywords: w9
Matched pattern: w9_wiring_request
```

### Test 3: Get Stats

```javascript
// In Apps Script, run:
testPythonAPIStats();
```

**Expected:**
```
SQLite Database Stats:
  Patterns: 7
  Templates: 4
  Contacts learned: 0
  Writing patterns: 0
  Emails processed: 0
  Average edit rate: 0%
```

---

## 🎯 Step 5: Enable Automatic Fallback

The system automatically falls back to local patterns if API unavailable.

### How it Works:

```javascript
// Apps Script tries Python API first
var patterns = callPythonAPI('/patterns', 'GET');

// If API fails, uses local fallback
if (!patterns) {
  Logger.log('Falling back to local patterns');
  patterns = getLocalPatterns();
}
```

### Update Local Fallback Patterns

Edit `getLocalPatterns()` function to match your SQLite data:

```javascript
function getLocalPatterns() {
  return [
    {
      pattern_name: 'invoice_processing',
      keywords: ['invoice', 'fees', 'mgmt'],
      confidence_boost: 15,
      notes: 'Route to Claude Project'
    },
    // ... add all 7 patterns
  ];
}
```

**When to update:** After adding new patterns to SQLite

---

## 🔒 Step 6: Security & Access

### Option A: Local Development (Simplest)

**Setup:**
- Run API on same computer as browser
- URL: `http://localhost:5000/api`
- Access: Only you can call it

**Use when:**
- Testing and development
- Personal computer only
- Don't need remote access

**Pros:**
- ✅ No network configuration
- ✅ Most secure (only local access)
- ✅ Zero cost

**Cons:**
- ❌ API must be running when batch processes
- ❌ Can't use from different computer

---

### Option B: Local Network (Recommended)

**Setup:**
- Run API on computer that's always on
- URL: `http://192.168.1.XXX:5000/api` (local IP)
- Access: Devices on your network

**Use when:**
- Want to process from any device at home/office
- Have always-on computer

**Pros:**
- ✅ Access from multiple devices
- ✅ Still private (local network only)
- ✅ Zero cost

**Cons:**
- ❌ Need to find computer's IP address
- ❌ Computer must be on

**Find your IP:**
```bash
# Windows
ipconfig

# Mac/Linux
ifconfig
```

---

### Option C: Cloud Hosting (Advanced)

**Setup:**
- Deploy API to cloud service
- URL: `https://your-app.herokuapp.com/api`
- Access: Anywhere with internet

**Options:**
- **Heroku** (free tier available)
- **Google Cloud Run** (pay per use)
- **PythonAnywhere** (free tier)

**Pros:**
- ✅ Access from anywhere
- ✅ Always available
- ✅ No home computer needed

**Cons:**
- ❌ More complex setup
- ❌ May cost money
- ❌ Security considerations

**Recommendation:** Start with Option A, move to Option B if needed

---

## 🔧 Step 7: Running the System

### Daily Operation:

**Morning (Before Batch Processing):**

```bash
# 1. Start Python API server
cd "C:\Users\derek\OneDrive\Desktop\Dilligence\Derek Code\LIVE DB"
python mcp_api_server.py

# Leave this running...
```

**Apps Script Automatically:**
- Generates batch queue at 11 PM
- Calls Python API when processing emails
- Falls back to local patterns if API down

**Evening:**
- Stop API server (Ctrl+C in terminal)
- Or leave running overnight

---

### Alternative: Run API as Background Service

**Windows (using NSSM):**
```bash
# Install NSSM
# Download from nssm.cc

# Install as service
nssm install MCPAPIServer "C:\Python\python.exe" "C:\...\mcp_api_server.py"
nssm start MCPAPIServer
```

**Mac/Linux (using systemd):**
```bash
# Create service file
sudo nano /etc/systemd/system/mcp-api.service

# Start service
sudo systemctl start mcp-api
sudo systemctl enable mcp-api  # Auto-start on boot
```

---

## 🧪 Step 8: Test Complete Integration

### End-to-End Test:

1. **Start API server:**
   ```bash
   python mcp_api_server.py
   ```

2. **In Apps Script, run:**
   ```javascript
   manualTest_GenerateTestQueue()
   ```

3. **Check email for batch queue**

4. **Fill in instructions and process**

5. **Verify in API logs:**
   ```
   127.0.0.1 - - [timestamp] "POST /api/match-pattern HTTP/1.1" 200
   127.0.0.1 - - [timestamp] "POST /api/patterns/w9_wiring_request/use HTTP/1.1" 200
   ```

6. **Check SQLite database:**
   ```bash
   sqlite3 mcp_learning.db "SELECT pattern_name, usage_count FROM pattern_hints;"
   ```

✅ **If usage_count increased, integration is working!**

---

## 📊 Monitoring & Maintenance

### Check API Status:

```bash
# Health check
curl http://localhost:5000/api/health

# Get stats
curl http://localhost:5000/api/stats

# View patterns
curl http://localhost:5000/api/patterns
```

### View API Logs:

API server prints logs to terminal:
```
Calling Python API: GET /api/health
✓ Python API call successful
Loaded 7 patterns from SQLite
SQLite pattern match: invoice_processing
```

### Check Database Updates:

```bash
sqlite3 mcp_learning.db
```

```sql
-- Check pattern usage
SELECT pattern_name, usage_count, last_updated 
FROM pattern_hints 
ORDER BY usage_count DESC;

-- Check template usage
SELECT template_id, usage_count, last_used 
FROM templates 
ORDER BY usage_count DESC;
```

---

## 🐛 Troubleshooting

### "Python API error: Connection refused"

**Problem:** API server not running

**Fix:**
```bash
python mcp_api_server.py
```

---

### "Module not found: flask"

**Problem:** Flask not installed

**Fix:**
```bash
pip install flask flask-cors
```

---

### "Database file not found"

**Problem:** DB_PATH incorrect in `mcp_api_server.py`

**Fix:**
```python
# Update line 16:
DB_PATH = r'C:\full\path\to\mcp_learning.db'
```

---

### "Apps Script can't reach API"

**Problem:** Firewall blocking or wrong URL

**Fix:**
1. Check API is running: `curl http://localhost:5000/api/health`
2. Check URL in Apps Script CONFIG matches
3. Try different port: Change `5000` to `8000` in both places

---

### "Patterns not loading from SQLite"

**Problem:** API working but no data

**Fix:**
1. Check database has data:
   ```bash
   sqlite3 mcp_learning.db "SELECT COUNT(*) FROM pattern_hints;"
   ```
2. Should return 7 or more
3. If 0, run bootstrap SQL again

---

## ✅ Integration Complete Checklist

- [ ] Flask installed (`pip install flask flask-cors`)
- [ ] `mcp_api_server.py` in MCP directory
- [ ] Database path correct in API server
- [ ] API server starts without errors
- [ ] Health endpoint returns 200 OK
- [ ] Apps Script updated with integration code
- [ ] `testPythonAPIConnection()` passes
- [ ] Pattern matching works via API
- [ ] Stats endpoint returns data
- [ ] End-to-end test successful
- [ ] Usage counts increment in database

---

## 🎯 What You've Achieved

✅ **Real Integration:** Apps Script now reads from your SQLite database  
✅ **Automatic Learning:** Usage stats update automatically  
✅ **Fallback System:** Works even if API down  
✅ **Single Source:** All data in one place (SQLite)  
✅ **Easy Updates:** Change patterns in SQLite, Apps Script sees them instantly  

**Your systems are now fully connected!** 🎉

---

## 📚 API Endpoints Reference

### GET /api/health
Health check

### GET /api/stats
System statistics

### GET /api/patterns
All patterns

### GET /api/patterns/{name}
Specific pattern

### GET /api/templates
All templates

### GET /api/templates/{id}
Specific template

### GET /api/tools
All tools

### GET /api/contacts
All contacts

### GET /api/contacts/{email}
Specific contact

### GET /api/writing-patterns
Writing patterns

### GET /api/overrides
Safety overrides

### POST /api/match-pattern
Match email to pattern
```json
{
  "subject": "...",
  "body": "...",
  "instruction": "..."
}
```

### POST /api/check-override
Check safety override
```json
{
  "subject": "...",
  "sender": "..."
}
```

### POST /api/patterns/{name}/use
Update pattern usage

### POST /api/templates/{id}/use
Update template usage

---

**Integration guide complete!** Your MCP system is now fully connected. 🚀
