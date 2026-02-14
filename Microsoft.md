I understand. You're replacing Google Docs with OneNote for the Idea Board workflow. Since you're downloading the OneNote app, the hybrid architecture simplifies: Power Automate creates OneNote pages instead of Google Docs, and your bot reads/updates OneNote content via Graph API rather than Google Docs.
Here's the updated prompt:
Claude Code Prompt: Hybrid MCP System Migration
Migrate an existing Gmail + Google Sheets automation system to a hybrid Microsoft 365 backend, using OneNote for idea documentation (replacing Google Docs).
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
•  Documents: OneNote (Power Automate creates pages; bot reads/updates via Graph API)
Phase 1: Directory Structure
project_root/
├── active/
│   ├── graph_client.py              # NEW: MSAL auth, Graph API client
│   ├── sharepoint_list_reader.py    # NEW: List operations
│   ├── file_fetcher.py              # MODIFIED: Hybrid SharePoint + Drive
│   ├── onenote_client.py            # NEW: Read/update OneNote pages
│   ├── mode4_processor.py           # MODIFIED: Polls Lists, uses OneNote
│   └── m1_config.py                 # MODIFIED: Add M365 credentials
├── possibly_deprecating/
│   ├── sheets_client.py             # ARCHIVE: Full Sheets client
│   ├── file_fetcher.py              # ARCHIVE: Drive-only version
│   ├── google_docs_client.py        # ARCHIVE: Full CRUD version (DEPRECATED)
│   └── mode4_processor.py           # ARCHIVE: Gmail polling version
├── flows/                           # NEW: Power Automate JSON templates
├── tests/                           # NEW: Unit test stubs
├── setup_m365_lists.py              # NEW: List provisioning script
├── setup_onenote.py                 # NEW: OneNote notebook provisioning
├── migration_validator.py           # NEW: Data integrity checker
├── rollback.py                      # NEW: Reversion script
├── .env.template                    # NEW: Environment variables
└── README_MIGRATION.md              # NEW: Migration documentation
File Handling Rules:
•  Copy existing files to possibly_deprecating/
•  Add header to archived files: # DEPRECATED: See active/[new_file].py
•  Mark modified functions: # MODIFIED: [YYYY-MM-DD] - [description]
Phase 2: Microsoft Lists Schema
1.  Action_Items (replaces Queue sheet)
Column	Type	Notes
TaskName	Title	Primary identifier
Status	Choice	Pending, Processing, Complete, Failed
Source	Choice	Email, Manual, API
EmailID	Text	Gmail message ID
Priority	Choice	High, Normal, Low
FileLink	Hyperlink	SharePoint file URL
FileID	Text	SharePoint drive item ID for content retrieval
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
Column	Type	Notes
IdeaName	Title
Status	Choice	Draft, Developing, Archived
OneNoteLink	Hyperlink	URL to OneNote page
OneNotePageID	Text	Graph API page identifier
Notes	MultiLineText
CreatedDate	DateTime	Auto-set
----
Phase 3: Core Components
3.1 graph_client.py
•  MSAL client credentials flow with auto token refresh
•  Methods:
•  get_access_token(), get_list_items(), create_list_item(), update_list_item(), delete_list_item()
•  Critical: get_file_content(file_id) → bytes (uses /content endpoint)
•  NEW: get_onenote_page_content(page_id) → HTML str
•  NEW: update_onenote_page_content(page_id, html_content) → bool
•  Environment: TENANT_ID, CLIENT_ID, CLIENT_SECRET, SHAREPOINT_SITE_ID, ONENOTE_NOTEBOOK_ID
•  Error handling: Specific exceptions with full endpoint URLs
3.2 sharepoint_list_reader.py
•  get_pending_actions(), get_brain_rules(), get_vip_context(email), update_action_status(item_id, new_status)
•  get_action_with_file(item_id) → includes FileID
•  NEW: get_idea_board_item(item_id) → includes OneNotePageID
3.3 file_fetcher.py (Modified)
•  get_file(file_path_or_id, source='auto') → bytes
•  Try SharePoint first (using FileID), fall back to Google Drive
•  Never return webUrl; always content bytes
3.4 onenote_client.py (NEW)
Requirements:
•  get_page_by_url(url) → page dict with ID and content
•  get_page_by_id(page_id) → HTML content
•  update_page_content(page_id, html_content) → bool (appends/updates content)
•  read_page_from_list_item(sharepoint_item) → str (extracts OneNoteLink, fetches content)
•  Note: OneNote pages are immutable; updates create new revisions. Handle by appending content or creating new pages for major changes.
3.5 mode4_processor.py (Modified)
•  REPLACE: check_gmail() → check_action_items_list()
•  Polling loop targets SharePoint Action_Items
•  Processing flow:
1.  Get pending actions
2.  Update status to 'Processing'
3.  If FileID: graph_client.get_file_content() → bytes
4.  If OneNoteLink present: onenote_client.read_page_from_list_item()
5.  Process with Ollama (unchanged)
6.  Draft email (unchanged)
7.  If idea processed: Update OneNote page with results/summary
8.  Update action status to 'Complete' or 'Failed'
----
Phase 4: Power Automate Flows
Flow A: Email Onboarding (unchanged)
•  Trigger: Gmail label [MCP] added
•  Save attachment to /Temporary_Staging/ with {Subject}{MessageID}{Timestamp}.{ext}
•  Create Action_Items with FileID and FileLink
Flow B: Email Offboarding (unchanged)
•  Trigger: Gmail label [MCP] removed
•  Delete Action_Items and staging files
Flow C: Idea Board → OneNote Bridge (MODIFIED)
•  Trigger: New item in Idea_Board
•  Actions:
1.  Create OneNote page in designated notebook (e.g., "MCP Ideas")
•  Title: {IdeaName}
•  Initial content: Template with title, creation date, status, and placeholder for bot input
2.  Update Idea_Board item:
•  OneNoteLink = Page URL (webUrl)
•  OneNotePageID = Page ID (for Graph API access)
Flow D: 60-Day Reaper (unchanged)
•  Daily cleanup of staging and garbage folders
----
Phase 5: Configuration & Environment
.env.template:
Microsoft 365
TENANT_ID=
CLIENT_ID=
CLIENT_SECRET=
SHAREPOINT_SITE_ID=
SHAREPOINT_SITE_URL=
ONENOTE_NOTEBOOK_ID=          # NEW: Target notebook for ideas
ONENOTE_NOTEBOOK_NAME=        # NEW: Display name
Google (existing - Drive only, no Docs)
GOOGLE_CREDENTIALS_PATH=
GMAIL_USER_ID=
Ollama (existing)
OLLAMA_BASE_URL=
----
Code Quality Standards
•  Type hints, Google docstrings, specific error handling with endpoint URLs
•  Python logging module
•  Unit test stubs in /tests/
Migration Safety
migration_validator.py:
•  Compare Google Sheets to SharePoint Lists
•  Validate Gmail [MCP] labels match Action_Items
•  NEW: Verify OneNote notebook accessible via Graph API
•  Check for orphaned files
rollback.py:
•  Restore Google-only mode (including Google Docs if needed)
•  Document manual OneNote export procedure if reverting
Critical Technical Constraints
1.  File Content: Always use /content endpoint for bytes, never metadata URLs
2.  Token Refresh: Auto-refresh if <5 min remaining
3.  File Naming: Append MessageID + Timestamp in Power Automate
4.  OneNote Immutability: Pages are append-only; design workflow around creating new pages or appending sections rather than overwriting
5.  OneNote Page IDs: Store both webUrl (for human access) and Graph API page ID (for bot access) in Idea_Board
----
Deliverables Checklist
•  [ ] All files in /active/ including onenote_client.py
•  [ ] setup_onenote.py for notebook provisioning
•  [ ] Power Automate Flow C updated for OneNote (not Google Docs)
•  [ ] Archived google_docs_client.py marked deprecated
•  [ ] Migration validator checks OneNote connectivity
•  [ ] Documentation updated for OneNote app workflow
Testing Requirements
•  [ ] Graph API authentication
•  [ ] All 4 SharePoint Lists created
•  [ ] OneNote notebook created and accessible
•  [ ] Power Automate creates OneNote page and stores PageID
•  [ ] Bot reads OneNote content via Graph API
•  [ ] Bot updates/appends OneNote content
•  [ ] Migration validator passes
Execution Priority
1.  graph_client.py (include OneNote methods)
2.  setup_m365_lists.py
3.  setup_onenote.py (provision notebook)
4.  sharepoint_list_reader.py
5.  onenote_client.py
6.  file_fetcher.py
7.  Power Automate Flow C (OneNote version)
8.  mode4_processor.py
9.  migration_validator.py
Do not proceed to next file until previous passes conceptual review.
