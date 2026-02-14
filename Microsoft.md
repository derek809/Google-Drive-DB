Claude Code Prompt: Hybrid MCP System Migration

I need to migrate my existing Gmail + Google Sheets automation system to a hybrid architecture using Microsoft 365 as the backend while preserving Gmail and Google Docs functionality.

## Current System Architecture
- Email: Gmail with [MCP] label triggers
- Database: Google Sheets (Queue, Patterns, Contacts)
- Storage: Google Drive for documents and attachments
- Processing: Local Python bot on M1 Mac using Ollama
- Document Creation: Google Docs API

## Target Hybrid Architecture
- Email: Keep Gmail (unchanged)
- Database: Microsoft Lists (replaces Google Sheets)
- Storage: SharePoint + Google Drive hybrid
- Processing: Local Python bot (updated to use Graph API)
- Document Creation: Power Automate → Google Docs (bot reads existing docs)

## Project Requirements

### Phase 1: Create New Directory Structure
Create a new folder structure that preserves the old system:


project_root/
├── active/                    # New hybrid system code
│   ├── graph_client.py       # NEW: Microsoft Graph API client
│   ├── sharepoint_list_reader.py  # NEW: Replaces sheets reader
│   ├── file_fetcher.py       # MODIFIED: Hybrid SharePoint + Drive
│   ├── google_docs_client.py # MODIFIED: Read-only mode
│   ├── mode4_processor.py    # MODIFIED: Uses Lists instead of Sheets
│   └── m1_config.py          # MODIFIED: Add M365 credentials
├── possibly_deprecating/     # Old Google-only code
│   ├── sheets_client.py      # OLD: Google Sheets client
│   ├── file_fetcher.py       # OLD: Drive-only version
│   ├── google_docs_client.py # OLD: Full CRUD version
│   └── mode4_processor.py    # OLD: Gmail polling version
└── README_MIGRATION.md       # Documentation of changes


### Phase 2: Microsoft 365 Backend Setup
Generate code to create these Microsoft Lists via Graph API:

1. **Action_Items** (replaces Queue sheet)
   - Columns: TaskName (Title), Status (Choice), Source (Choice), EmailID (Text), Priority (Choice), FileLink (Hyperlink), CreatedDate (DateTime)

2. **Brain_Rules** (replaces Patterns sheet)
   - Columns: RuleName (Title), Keywords (Text), ConfidenceScore (Number), ActionType (Choice)

3. **VIP_Network** (replaces Contacts sheet)
   - Columns: Name (Title), Email (Text), Context (MultiLineText), LastContact (DateTime)

4. **Idea_Board** (new brainstorming hub)
   - Columns: IdeaName (Title), Status (Choice), GoogleDocLink (Hyperlink), Notes (MultiLineText), CreatedDate (DateTime)

### Phase 3: Core Migration Components

#### 3.1 Authentication Setup
Create `graph_client.py` with:
- MSAL authentication using client credentials flow
- Methods: `get_access_token()`, `get_list_items()`, `create_list_item()`, `update_list_item()`, `delete_list_item()`
- Error handling for token refresh
- Configuration from environment variables

#### 3.2 SharePoint Integration
Create `sharepoint_list_reader.py` with:
- `get_pending_actions()` - Query Action_Items where Status = 'Pending'
- `get_brain_rules()` - Fetch all active rules
- `get_vip_context(email)` - Lookup contact context
- `update_action_status(item_id, new_status)` - Mark items as Processing/Complete

#### 3.3 Hybrid File Fetcher
Modify `file_fetcher.py` to:
- Check SharePoint Document Library first (for Power Automate-saved email attachments)
- Fall back to Google Drive if not found in SharePoint
- Maintain existing Google Drive search functionality
- Add method `get_file_from_sharepoint(file_path)`

#### 3.4 Google Docs Client Update
Modify `google_docs_client.py` to:
- REMOVE: Document creation functions (Power Automate handles this)
- KEEP: Read document content by URL
- KEEP: Update document content
- NEW: Method `read_doc_by_list_link(sharepoint_item)` that extracts Google Doc URL from SharePoint item

#### 3.5 Main Processor Update
Modify `mode4_processor.py` to:
- REPLACE: Gmail polling loop → SharePoint List polling loop
- NEW: `check_action_items_list()` instead of `check_gmail()`
- When processing item with GoogleDocLink: read context from Google Doc
- Update SharePoint item status as work progresses
- KEEP: Ollama integration unchanged
- KEEP: Email drafting logic unchanged

### Phase 4: Power Automate Flow Specifications
Generate JSON templates for these flows:

**Flow A: Email Onboarding (Gmail → SharePoint)**
- Trigger: Gmail label [MCP] added
- Action 1: Save attachment to SharePoint `/Temporary_Staging/`
- Action 2: Create item in Action_Items list
  - Map: Subject → TaskName, MessageID → EmailID, AttachmentLink → FileLink
  - Set Status = 'Pending', Source = 'Email'

**Flow B: Email Offboarding (Label Removal Cleanup)**
- Trigger: Gmail label [MCP] removed
- Action 1: Get items from Action_Items where EmailID = MessageID
- Action 2: Delete SharePoint list item
- Action 3: Delete file from `/Temporary_Staging/`

**Flow C: Idea Board → Google Docs Bridge**
- Trigger: New item created in Idea_Board list
- Action 1: Create Google Doc in `/MCP_Project_Brains/`
  - Filename: `{IdeaName}.html`
  - Content: Basic HTML template with title and creation date
- Action 2: Update SharePoint item's GoogleDocLink field with Doc URL

**Flow D: 60-Day Reaper (Maintenance)**
- Trigger: Recurrence (daily)
- Logic 1: Files in `/Temporary_Staging/` > 30 days → Move to `/Garbage_Folder/`
- Logic 2: Files in `/Garbage_Folder/` > 30 days → Permanent delete

### Phase 5: Configuration & Environment Setup
Create `.env.template` with:


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


### Code Quality Requirements
- All new code must include:
  - Type hints
  - Docstrings (Google style)
  - Error handling with specific exceptions
  - Logging using Python `logging` module
  - Unit test stubs in `/tests/` directory
- Mark all modified functions with `# MODIFIED: [date] - [description]` comments
- Add `# DEPRECATED: See active/[new_file].py` to old files

### Migration Safety
- Do NOT delete any existing files
- Create `migration_validator.py` that:
  - Compares Google Sheets row counts to SharePoint List counts
  - Validates allEmailIDs from Gmail are present in Action_Items
  - Checks for orphaned files in staging folders
- Generate rollback script that can revert to Google-only mode

## Deliverables
1. All new/modified Python files in `/active/`
2. Archived old files in `/possibly_deprecating/` with deprecation notices
3. Power Automate flow JSON templates in `/flows/`
4. Migration guide: `README_MIGRATION.md`
5. Configuration template: `.env.template`
6. Validation script: `migration_validator.py`
7. Setup script: `setup_m365_lists.py` (creates all Lists via Graph API)

## Testing Requirements
Before deployment, the system must:
- [ ] Successfully authenticate to Microsoft Graph API
- [ ] Create all 4 SharePoint Lists programmatically
- [ ] Poll Action_Items list and detect new items
- [ ] Fetch a file from SharePoint Document Library
- [ ] Read a Google Doc via URL stored in SharePoint
- [ ] Update a SharePoint List item status
- [ ] Run migration validator with 0 errors

Use explicit error messages that reference the specific API endpoint that failed.


Your Action Plan (User Steps)
Pre-Code Work (Do These First)
1. Microsoft 365 Setup (30 minutes)
	∙	Go to https://admin.microsoft.com
	∙	Create Team: “Project MCP” (this auto-creates SharePoint site)
	∙	Note your SharePoint site URL (e.g., https://yourtenant.sharepoint.com/sites/ProjectMCP)
	∙	Create these folders in SharePoint Documents:
	∙	/Temporary_Staging/
	∙	/Garbage_Folder/
	∙	/MCP_Project_Brains/ (for Google Docs created by Power Automate)
2. Azure App Registration (20 minutes)
	∙	Go to https://portal.azure.com → Azure Active Directory → App Registrations
	∙	Click “New registration”
	∙	Name: “MCP Bot”
	∙	Supported account types: “Single tenant”
	∙	After creation, copy these values to a secure note:
	∙	Application (client) ID
	∙	Directory (tenant) ID
	∙	Go to “Certificates & secrets” → “New client secret”
	∙	Description: “Bot access token”
	∙	Copy the secret VALUE immediately (you can’t see it again!)
	∙	Go to “API permissions” → “Add permission” → “Microsoft Graph”
	∙	Add these Application permissions:
	∙	Sites.ReadWrite.All
	∙	Files.ReadWrite.All
	∙	Click “Grant admin consent” button
3. Get SharePoint Site ID (5 minutes)
Run this in browser console while on your SharePoint site:

_spPageContextInfo.siteId


Save this GUID for your .env file.
4. Prepare Your Local Environment (10 minutes)

# Create project backup
cd /path/to/your/project
git add -A
git commit -m "Pre-migration checkpoint"
git tag v1-google-only

# Create new branch
git checkout -b hybrid-m365-migration

# Install new dependencies
pip install msal msgraph-sdk azure-identity

# Create directory structure
mkdir -p active possibly_deprecating flows tests


5. Move Existing Files to Archive (5 minutes)

# Copy (don't move yet) existing files
cp sheets_client.py possibly_deprecating/
cp file_fetcher.py possibly_deprecating/
cp google_docs_client.py possibly_deprecating/
cp mode4_processor.py possibly_deprecating/

# Add deprecation notice to tops of archived files
echo "# DEPRECATED: This is the old Google Sheets version. See active/ folder for new hybrid system." | cat - possibly_deprecating/sheets_client.py > temp && mv temp possibly_deprecating/sheets_client.py


Post-Code Work (After Claude Code Runs)
6. Environment Configuration (5 minutes)
	∙	Copy .env.template to .env
	∙	Fill in all Microsoft 365 values from steps 2 & 3
	∙	Verify your existing Google credentials path is correct
	∙	DO NOT commit .env to git
7. Initial Validation (10 minutes)

# Test Microsoft Graph connection
python active/graph_client.py --test-connection

# Create SharePoint Lists
python setup_m365_lists.py

# Verify lists were created
# (Visit your SharePoint site → Site Contents → should see 4 new lists)


8. Power Automate Flow Setup (45 minutes)
For each flow JSON template in /flows/:
	∙	Go to https://make.powerautomate.com
	∙	Click “My flows” → “Import” → “Import Package (Legacy)”
	∙	Upload the JSON file
	∙	Map connections:
	∙	Gmail: Select your Gmail account
	∙	SharePoint: Select your tenant
	∙	Save and turn ON the flow
	∙	Test each flow:
	∙	Flow A: Label an email with [MCP], check if item appears in Action_Items list
	∙	Flow B: Remove [MCP] label, check if item disappears
	∙	Flow C: Add item to Idea_Board, check if Google Doc gets created
9. Migration Validation (15 minutes)

# Run the validator
python migration_validator.py

# Should output:
# ✓ Microsoft Graph API: Connected
# ✓ SharePoint Lists: All 4 created
# ✓ Google Sheets access: Working
# ✓ Gmail label count: 12 emails with [MCP]
# ✓ Action_Items count: 12 items
# ✓ No orphaned files in staging


10. Staged Rollout (Do Over 1 Week)
Day 1-2: Read-only testing
	∙	Let Power Automate flows run
	∙	Monitor SharePoint lists filling up
	∙	Do NOT run the bot yet
	∙	Verify Gmail → SharePoint sync is accurate
Day 3-4: Bot in dry-run mode
	∙	Modify mode4_processor.py to add --dry-run flag
	∙	Run: python active/mode4_processor.py --dry-run
	∙	Check logs to ensure it reads SharePoint correctly
	∙	Verify it can fetch files from SharePoint
	∙	Verify it can read Google Docs via SharePoint links
Day 5: First live run
	∙	Label ONE test email with [MCP]
	∙	Watch the full cycle: Email → SharePoint → Bot processes → Status updated
	∙	Remove label, verify cleanup
Day 6-7: Full production
	∙	Enable bot as background service
	∙	Monitor for 48 hours
	∙	Compare behavior to old system
11. Deprecation Cleanup (After 30 Days)
If system is stable:

# Add final deprecation warnings
rm possibly_deprecating/*.py  # or move to /archive/2026-02/

# Update README
echo "This project now uses Microsoft 365 Lists. Google Sheets code was retired March 2026." >> README.md

git add -A
git commit -m "Complete migration to hybrid M365 system"
git tag v2-hybrid-m365


Emergency Rollback Procedure
If something breaks:

# Switch back to old system
git checkout v1-google-only

# Or just use old files
cp possibly_deprecating/* ./

# Turn OFF Power Automate flows
# (Go to make.powerautomate.com → turn off all 4 flows)

# Resume using Gmail + Google Sheets only


Success Criteria Checklist
You’ll know migration is complete when:
	∙	Email labeled [MCP] creates SharePoint list item within 5 seconds
	∙	Bot processes SharePoint queue instead of polling Gmail
	∙	Files are fetched from SharePoint staging folder
	∙	Ideas added to list auto-create Google Docs
	∙	Removing [MCP] label cleans up staging within 5 seconds
	∙	No Google Sheets are accessed by the bot anymore
	∙	Old sheets_client.py has not been imported in 30 days

Estimated Total Time Investment:
	∙	Pre-code setup: ~80 minutes
	∙	Code execution: ~10 minutes (Claude Code)
	∙	Post-code setup: ~90 minutes
	∙	Testing & validation: ~2 hours over 1 week
	∙	Total: ~5 hours spread over 7-10 days
Would you like me to generate the actual Python code for any of these components now, or do you want to complete the pre-code setup steps first?​​​​​​​​​​​​​​​​


also please not this:

Yes, you've spotted the classic "Cloud Trap." When you ask a system like SharePoint for a file, it defaults to sending a Link (the "address" of the file) rather than the Content Bytes (the "actual paper" inside the envelope).
To attach a real file to a Gmail draft, you have to tell your code to "Open the envelope and read the bits." Here is how you override this in both Power Automate and your Python code.
1. The Power Automate Fix: "Get File Content"
If you are using Power Automate to send the email, you cannot just use the output from the "Create File" step. You must add one specific action in between.
 * The Action: Search for "SharePoint - Get file content".
 * The Input: Use the File Identifier (the ID) from your "Create File" or "Get File Properties" step.
 * The Gmail Action: In the Gmail "Send Email" or "Create Draft" block:
   * Click Show Advanced Options.
   * In the Attachments Name, type the file name (e.g., W9.pdf).
   * In the Attachments Content, choose the File Content (the purple icon) from the "Get file content" step.
   * This forces the flow to grab the actual data of the file, not just the URL.
2. The Python Fix: "Raw Content Download"
Since your bot is on your M1, it needs to download the "binary data" of the file to attach it to a Gmail draft. If you only have the webUrl, you'll just be emailing a link.
In your graph_client.py, you need to use the content endpoint to get the actual bytes:
def get_file_bytes(self, item_id):
    # This specifically asks for the "actual file" rather than just the info
    url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive/items/{item_id}/content"
    token = self.get_token()
    response = requests.get(url, headers={'Authorization': f'Bearer {token}'})
    
    # These are the actual bytes of your PDF/Doc
    return response.content 

3. The "Hybrid Bridge" Shortcut
To make this easy for yourself, have Power Automate store the SharePoint Item ID in your Bot_Queue list instead of just the link.
 * Power Automate: When it creates the file in /Temporary_Staging/, it saves the ID to the SharePoint List.
 * M1 Bot: The bot reads the ID, uses the Python function above to grab the Bytes, and then uses your gmail_client.py to attach those bytes to the draft.
Why this is better:
By using the Content Bytes, your Gmail draft will look exactly like you manually attached a file from your computer. The recipient won't need a SharePoint login or special permissions to see it—it's just a regular PDF attached to the email.
Would you like me to update your gmail_client.py to include the logic that takes these "Bytes" and turns them into a real Gmail attachment?
