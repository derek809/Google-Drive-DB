I'll refine your prompt into a clean, structured format optimized for Claude Code. This removes conversational filler, tightens requirements, and ensures precise execution.
Claude Code Prompt: Hybrid MCP System Migration
Migrate an existing Gmail + Google Sheets automation system to a hybrid Microsoft 365 backend while preserving Gmail and Google Docs functionality.
Architecture
Current State:
•  Email: Gmail with [MCP] label triggers
•  Database: Google Sheets (Queue, Patterns, Contacts)
•  Storage: Google Drive
•  Processing: Local Python bot (M1 Mac, Ollama)
•  Documents: Google Docs API (full CRUD)
Target State:
•  Email: Gmail (unchanged)
•  Database: Microsoft Lists (replaces Sheets)
•  Storage: SharePoint primary, Google Drive fallback
•  Processing: Local Python bot (Graph API integration)
•  Documents: Power Automate creates Google Docs; bot reads/updates only
Phase 1: Directory Structure
Create exactly this structure:
project_root/
├── active/
│   ├── graph_client.py              # NEW: MSAL auth, Graph API client
│   ├── sharepoint_list_reader.py    # NEW: List operations
│   ├── file_fetcher.py              # MODIFIED: Hybrid SharePoint + Drive
│   ├── google_docs_client.py        # MODIFIED: Read/update only, no create
│   ├── mode4_processor.py           # MODIFIED: Polls Lists, not Gmail
│   └── m1_config.py                 # MODIFIED: Add M365 credentials
├── possibly_deprecating/
│   ├── sheets_client.py             # ARCHIVE: Full Sheets client
│   ├── file_fetcher.py              # ARCHIVE: Drive-only version
│   ├── google_docs_client.py        # ARCHIVE: Full CRUD version
│   └── mode4_processor.py           # ARCHIVE: Gmail polling version
├── flows/                           # NEW: Power Automate JSON templates
├── tests/                           # NEW: Unit test stubs
├── setup_m365_lists.py              # NEW: List provisioning script
├── migration_validator.py           # NEW: Data integrity checker
├── rollback.py                      # NEW: Reversion script
├── .env.template                    # NEW: Environment variables
└── README_MIGRATION.md              # NEW: Migration documentation
File Handling Rules:
•  Copy (don't move) existing files to possibly_deprecating/
•  Add header to all archived files: # DEPRECATED: See active/[new_file].py
•  Mark all modified functions with: # MODIFIED: [YYYY-MM-DD] - [description]
Phase 2: Microsoft Lists Schema
Create these lists via Graph API in setup_m365_lists.py:
1.  Action_Items (replaces Queue sheet)
Column	Type	Notes
TaskName	Title	Primary identifier
Status	Choice	Pending, Processing, Complete, Failed
Source	Choice	Email, Manual, API
EmailID	Text	Gmail message ID
Priority	Choice	High, Normal, Low
FileLink	Hyperlink	SharePoint file URL
FileID	Text	Critical: SharePoint drive item ID for content retrieval
CreatedDate	DateTime	Auto-set
2.  Brain_Rules (replaces Patterns sheet)
Column	Type
RuleName	Title
Keywords	Text
ConfidenceScore	Number
ActionType	Choice
3.  VIP_Network (replaces Contacts sheet)
Column	Type
Name	Title
Email	Text
Context	MultiLineText
LastContact	DateTime
4.  Idea_Board (new)
Column	Type
IdeaName	Title
Status	Choice
GoogleDocLink	Hyperlink
Notes	MultiLineText
CreatedDate	DateTime
----
Phase 3: Core Components
3.1 graph_client.py
Requirements:
•  MSAL client credentials flow
•  Auto token refresh (check expiry before each call)
•  Methods:
•  get_access_token() → str
•  get_list_items(list_name, filter_query=None) → List[Dict]
•  create_list_item(list_name, fields) → Dict
•  update_list_item(list_name, item_id, fields) → Dict
•  delete_list_item(list_name, item_id) → bool
•  Critical: get_file_content(file_id) → bytes (uses /content endpoint, not metadata)
•  Environment variables: TENANT_ID, CLIENT_ID, CLIENT_SECRET, SHAREPOINT_SITE_ID
•  Error handling: Specific exceptions per endpoint with full URL in message
3.2 sharepoint_list_reader.py
Requirements:
•  get_pending_actions() → Query Action_Items where Status = 'Pending', return list
•  get_brain_rules() → Fetch all Brain_Rules, return list
•  get_vip_context(email) → Lookup VIP_Network by Email, return Context string
•  update_action_status(item_id, new_status) → Patch Action_Items, return success bool
•  get_action_with_file(item_id) → Return action dict including FileID for download
3.3 file_fetcher.py (Modified)
Requirements:
•  get_file(file_path_or_id, source='auto') → bytes
•  If source='sharepoint' or source='auto': Try SharePoint first using FileID
•  If source='drive' or SharePoint fails: Fall back to Google Drive
•  Preserve existing Google Drive search functionality
•  Critical: Never return webUrl; always return content bytes
3.4 google_docs_client.py (Modified)
Requirements:
•  REMOVE: All document creation functions
•  read_doc_by_url(url) → str (existing)
•  update_doc_content(url, content) → bool (existing)
•  read_doc_by_list_item(sharepoint_item) → str (extracts GoogleDocLink from SharePoint dict)
•  Add deprecation warnings if creation methods called
3.5 mode4_processor.py (Modified)
Requirements:
•  REPLACE: check_gmail() → check_action_items_list()
•  Polling loop targets SharePoint Action_Items, not Gmail API
•  Processing flow:
1.  Get pending actions
2.  Update status to 'Processing'
3.  If FileID present: graph_client.get_file_content() → bytes
4.  If GoogleDocLink present: google_docs_client.read_doc_by_list_item()
5.  Process with Ollama (unchanged)
6.  Draft email (unchanged)
7.  Update action status to 'Complete' or 'Failed'
•  Keep Ollama integration exactly as-is
•  Keep email drafting logic exactly as-is
----
Phase 4: Power Automate Flows
Generate JSON templates in /flows/:
Flow A: Email Onboarding
•  Trigger: Gmail label [MCP] added
•  Actions:
1.  Save attachment to SharePoint /Temporary_Staging/ with naming pattern: {Subject}{MessageID}{Timestamp}.{ext}
2.  Create Action_Items item:
•  TaskName = Subject
•  EmailID = MessageID
•  FileLink = SharePoint webUrl
•  FileID = SharePoint driveItemId (critical for bot retrieval)
•  Status = Pending
•  Source = Email
Flow B: Email Offboarding
•  Trigger: Gmail label [MCP] removed
•  Actions:
3.  Get Action_Items where EmailID = MessageID
4.  Delete list item(s)
5.  Delete file from /Temporary_Staging/
Flow C: Idea Board Bridge
•  Trigger: New item in Idea_Board
•  Actions:
6.  Create Google Doc in /MCP_Project_Brains/ named {IdeaName}.html
7.  Content: HTML template with title, creation date, placeholder body
8.  Update Idea_Board item: GoogleDocLink = Doc URL
Flow D: 60-Day Reaper
•  Trigger: Daily recurrence
•  Logic:
•  /Temporary_Staging/ files > 30 days → Move to /Garbage_Folder/
•  /Garbage_Folder/ files > 60 days → Permanent delete
----
Phase 5: Configuration & Environment
.env.template:
Microsoft 365
TENANT_ID=
CLIENT_ID=
CLIENT_SECRET=
SHAREPOINT_SITE_ID=
SHAREPOINT_SITE_URL=
Google (existing)
GOOGLE_CREDENTIALS_PATH=
GMAIL_USER_ID=
Ollama (existing)
OLLAMA_BASE_URL=
----
Code Quality Standards
All new/modified files must include:
•  Type hints (Python 3.9+)
•  Google-style docstrings
•  Specific exception handling with endpoint URLs in messages
•  Python logging module (not print)
•  Unit test stubs in /tests/
Migration Safety
migration_validator.py requirements:
•  Compare Google Sheets row counts to SharePoint List counts
•  Validate all Gmail [MCP] labels have corresponding Action_Items
•  Check for orphaned files in staging folders
•  Output: Checklist format with ✓/✗ per item
rollback.py requirements:
•  Restore Google-only mode
•  Disable Power Automate flows (documentation only, manual step)
•  Revert to v1-google-only git tag
Critical Technical Constraints
1.  File Content vs. Metadata: Always use /content endpoint for file bytes, never webUrl
2.  Token Refresh: Check token expiry before every Graph API call; auto-refresh if <5 min remaining
3.  File Naming: Power Automate must append MessageID + Timestamp to prevent collisions
4.  Size Limits: Support files up to 4MB via standard download; document chunked approach for larger files
5.  FileID Storage: Action_Items must store SharePoint driveItemId (FileID), not just URL
----
Deliverables Checklist
•  [ ] All files in /active/ with modification headers
•  [ ] All archived files in /possibly_deprecating/ with deprecation notices
•  [ ] Power Automate JSON templates in /flows/
•  [ ] README_MIGRATION.md with architecture diagram
•  [ ] .env.template with all variables
•  [ ] setup_m365_lists.py (idempotent list creation)
•  [ ] migration_validator.py (pre/post flight checks)
•  [ ] rollback.py (emergency revert)
•  [ ] Unit test stubs in /tests/
Testing Requirements
Before deployment, verify:
•  [ ] Graph API authentication with auto-refresh
•  [ ] All 4 SharePoint Lists created programmatically
•  [ ] Action_Items polling detects new items within 5 seconds
•  [ ] File fetch from SharePoint returns bytes, not URL
•  [ ] Google Doc read via SharePoint link succeeds
•  [ ] Status updates propagate to SharePoint
•  [ ] Migration validator runs with zero errors
Error Messages: Must include specific API endpoint that failed (e.g., "Graph API Error: GET https://graph.microsoft.com/v1.0/sites/{id}/lists/Action_Items/items").
Execution Priority
1.  Generate graph_client.py with robust token handling
2.  Generate setup_m365_lists.py for list provisioning
3.  Generate sharepoint_list_reader.py with FileID support
4.  Generate modified file_fetcher.py with hybrid logic
5.  Generate Power Automate Flow A and B JSON
6.  Generate migration_validator.py
7.  Generate remaining files
Do not proceed to next file until previous passes conceptual review.
