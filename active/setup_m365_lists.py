"""
SharePoint Lists Provisioning Script.

Creates the Action_Items and Idea_Board lists in SharePoint via Graph API.
Run once before enabling M365_ENABLED=true.

Usage:
    python active/setup_m365_lists.py              # create lists
    python active/setup_m365_lists.py --dry-run    # preview payloads only
"""

import asyncio
import json
import os
import sys

# Add project paths for imports
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
sys.path.insert(0, _script_dir)
sys.path.insert(0, os.path.join(_project_root, "core", "Infrastructure"))

from graph_client import GraphClient, GraphAPIError
from async_session_manager import get_session, close

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# ── List Schemas ──────────────────────────────────────────────────────

LISTS_SCHEMA = {
    "Action_Items": {
        "description": "MCP bot action items queue (replaces Google Sheets Queue)",
        "columns": [
            {"name": "Status", "type": "choice",
             "choices": ["Pending", "Processing", "Complete", "Failed"],
             "default": "Pending"},
            {"name": "Priority", "type": "choice",
             "choices": ["High", "Medium", "Low"],
             "default": "Medium"},
            {"name": "ThreadID", "type": "text"},
            {"name": "ConversationID", "type": "text"},
            {"name": "OneNotePageID", "type": "text"},
            {"name": "OneNoteLink", "type": "text"},
            {"name": "FileID", "type": "text"},
            {"name": "Source", "type": "text"},
            {"name": "LastBotHeartbeat", "type": "dateTime"},
            {"name": "RecoveryLog", "type": "note"},
            {"name": "CompletionNotes", "type": "note"},
            {"name": "CompletedAt", "type": "dateTime"},
            {"name": "MessageCount", "type": "number"},
            {"name": "LastSummaryDate", "type": "dateTime"},
        ],
    },
    "Idea_Board": {
        "description": "Ideas and brainstorms with OneNote links",
        "columns": [
            {"name": "Category", "type": "choice",
             "choices": ["brainstorm", "skill", "project", "research"],
             "default": "brainstorm"},
            {"name": "Status", "type": "choice",
             "choices": ["New", "InProgress", "Completed", "Archived"],
             "default": "New"},
            {"name": "Description", "type": "note"},
            {"name": "OneNotePageID", "type": "text"},
            {"name": "OneNoteLink", "type": "text"},
        ],
    },
}


def _build_column_payload(col: dict) -> dict:
    """Build a Graph API column definition from schema shorthand."""
    col_type = col["type"]
    name = col["name"]

    if col_type == "text":
        return {"name": name, "text": {}}
    elif col_type == "note":
        return {"name": name, "text": {"allowMultipleLines": True}}
    elif col_type == "number":
        return {"name": name, "number": {}}
    elif col_type == "dateTime":
        return {"name": name, "dateTime": {"format": "dateTimeTimeZone"}}
    elif col_type == "choice":
        payload = {
            "name": name,
            "choice": {"choices": col["choices"]},
        }
        if "default" in col:
            payload["defaultValue"] = {"value": col["default"]}
        return payload
    elif col_type == "boolean":
        return {"name": name, "boolean": {}}
    else:
        raise ValueError(f"Unknown column type: {col_type}")


def _build_list_payload(list_name: str, schema: dict) -> dict:
    """Build the POST payload for creating a SharePoint list."""
    return {
        "displayName": list_name,
        "description": schema.get("description", ""),
        "list": {"template": "genericList"},
    }


async def create_list(graph: GraphClient, site_id: str, list_name: str,
                      schema: dict, dry_run: bool = False) -> str:
    """
    Create a SharePoint list and add custom columns.

    Returns the new list ID.
    """
    list_payload = _build_list_payload(list_name, schema)

    if dry_run:
        print(f"\n[DRY RUN] Would create list: {list_name}")
        print(f"  POST {GRAPH_BASE}/sites/{site_id}/lists")
        print(f"  Payload: {json.dumps(list_payload, indent=2)}")
        for col in schema["columns"]:
            col_payload = _build_column_payload(col)
            print(f"  Column: {json.dumps(col_payload)}")
        return "<dry-run-id>"

    # Create the list
    url = f"{GRAPH_BASE}/sites/{site_id}/lists"
    print(f"\nCreating list: {list_name}...")

    try:
        result = await graph.post(url, data=list_payload)
    except GraphAPIError as exc:
        if exc.status_code == 409:
            print(f"  List '{list_name}' already exists, skipping creation")
            # Try to get existing list ID
            existing = await graph.get(f"{url}?$filter=displayName eq '{list_name}'")
            items = existing.get("value", [])
            if items:
                list_id = items[0]["id"]
                print(f"  Existing list ID: {list_id}")
                return list_id
            raise
        raise

    list_id = result["id"]
    print(f"  Created! List ID: {list_id}")

    # Add columns
    columns_url = f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/columns"
    for col in schema["columns"]:
        col_payload = _build_column_payload(col)
        try:
            await graph.post(columns_url, data=col_payload)
            print(f"  + Column: {col['name']} ({col['type']})")
        except GraphAPIError as exc:
            if exc.status_code == 409:
                print(f"  ~ Column '{col['name']}' already exists, skipping")
            else:
                print(f"  ! Failed to add column '{col['name']}': {exc}")

    return list_id


async def main(dry_run: bool = False):
    """Provision all SharePoint lists."""
    from m1_config import (
        M365_CLIENT_ID, M365_TENANT_ID, M365_CLIENT_SECRET,
        SHAREPOINT_SITE_ID, M365_TOKEN_CACHE_PATH,
    )

    if not all([M365_CLIENT_ID, M365_TENANT_ID, M365_CLIENT_SECRET, SHAREPOINT_SITE_ID]):
        print("ERROR: Missing M365 credentials. Check .env or credentials/microsoft_login.json")
        sys.exit(1)

    print("=" * 50)
    print("  SharePoint Lists Provisioning")
    print("=" * 50)
    print(f"  Site ID: {SHAREPOINT_SITE_ID[:12]}...")
    if dry_run:
        print("  Mode: DRY RUN (no changes will be made)")
    print()

    session = await get_session()
    graph = GraphClient(
        client_id=M365_CLIENT_ID,
        tenant_id=M365_TENANT_ID,
        client_secret=M365_CLIENT_SECRET,
        session=session,
        token_cache_path=M365_TOKEN_CACHE_PATH,
    )

    results = {}
    try:
        for list_name, schema in LISTS_SCHEMA.items():
            list_id = await create_list(
                graph, SHAREPOINT_SITE_ID, list_name, schema, dry_run
            )
            results[list_name] = list_id

        # Print summary
        print("\n" + "=" * 50)
        print("  RESULTS")
        print("=" * 50)
        for name, lid in results.items():
            print(f"  {name}: {lid}")

        if not dry_run:
            print("\nAdd these to your .env file:")
            if "Action_Items" in results:
                print(f"  ACTION_ITEMS_LIST_ID={results['Action_Items']}")
            if "Idea_Board" in results:
                print(f"  IDEA_BOARD_LIST_ID={results['Idea_Board']}")

    finally:
        await close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry_run))
