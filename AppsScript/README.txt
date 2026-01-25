MCP EMAIL PROCESSOR - GOOGLE APPS SCRIPT
========================================

DEPLOYMENT INSTRUCTIONS
-----------------------

1. Go to: script.google.com

2. Click "New Project"

3. Name it: "MCP Email Processor"

4. Create these files (copy content from each .gs file):
   - 1_Config.gs
   - 2_Sheets.gs
   - 3_Patterns.gs
   - 4_Queue.gs
   - 5_Processing.gs
   - 6_Utils.gs

   TIP: The numbers ensure files load in correct order.
   In Apps Script, click the "+" next to Files, select "Script"

5. Save the project (Ctrl+S)

6. Run "setupMCP" function:
   - Select "setupMCP" from dropdown
   - Click "Run"
   - Authorize when prompted

7. Go to your Google Sheet:
   - You should see "MCP Queue" menu
   - Click MCP Queue > API Keys > Set Claude API Key
   - Click MCP Queue > API Keys > Set Gemini API Key


FILE STRUCTURE
--------------

1_Config.gs   - Configuration constants, API key management
2_Sheets.gs   - Sheet creation, menu, setup functions
3_Patterns.gs - Pattern matching, templates, contacts
4_Queue.gs    - Email population, manual tasks, archiving
5_Processing.gs - Claude/Gemini API calls, processing logic
6_Utils.gs    - Statistics, history cleanup, testing


SHEET STRUCTURE (created by setup)
----------------------------------

MCP sheet:
  Columns A-H: Queue (emails/tasks to process)
  Column I: Separator
  Columns J-O: Patterns (your 7 patterns)

Templates sheet:
  Your 4 email templates

Contacts sheet:
  Learned contacts (grows over time)

History sheet:
  Archived processed items


USAGE
-----

1. Label emails with [MCP] in Gmail

2. Run "Populate from Emails" from menu

3. Fill in Prompt column (what you want done)

4. Check "Gemini?" if data fetching needed

5. Check "Ready?" for items to process

6. Run "Process Ready Items"

7. Check cell notes for results (right-click Prompt cells)

8. Run "Archive Completed" to clean up


PATTERNS (editable in MCP sheet, columns J-O)
---------------------------------------------

invoice_processing    - Invoice/fee related (+15)
w9_wiring_request     - W9 and wiring info (+20)
payment_confirmation  - Payment received (+15)
producer_statements   - Producer reports (+10)
delegation_eytan      - Loop in Eytan (+0)
turnaround_expectation - Timeline questions (+5)
journal_entry_reminder - JE/compensation (+0)

You can add more patterns directly in the sheet!


TEMPLATES (editable in Templates sheet)
---------------------------------------

w9_response          - W9 and wiring reply
payment_confirmation - Payment received reply
delegation_eytan     - Forward to Eytan
turnaround_time      - Timeline expectations

Variables use {name} syntax.
You can add more templates directly in the sheet!


TROUBLESHOOTING
---------------

"API key not set"
  -> MCP Queue > API Keys > Set Claude/Gemini API Key

"Gmail label not found"
  -> Run Setup again, or manually create [MCP] label in Gmail

"No emails found"
  -> Make sure emails are labeled [MCP] in Gmail
  -> Check SEARCH_DAYS setting in Config (default: 7 days)

Processing errors
  -> Check Logs: View > Logs in Apps Script editor
  -> Cell notes contain error details


TESTING
-------

Run these from Apps Script to test:

testPatternMatch()  - Test pattern matching
testLearning()      - Test learning functions
testClaudeAPI()     - Test Claude connection
testGeminiAPI()     - Test Gemini connection
debugShowPatterns() - List all patterns
debugShowTemplates() - List all templates


LEARNING
--------

The system learns from usage:
- Pattern usage counts update in column M
- Template usage counts update in column F
- New contacts added to Contacts sheet
- All learning persists in Google Sheets
