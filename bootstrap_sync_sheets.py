#!/usr/bin/env python3
"""
Bootstrap Sync - SQLite to Google Sheets
Syncs patterns, templates, and contacts from SQLite (source of truth) to Google Sheets
for Mode 4 (M1) to read.

Usage:
    python bootstrap_sync_sheets.py

This script pushes data from mcp_learning.db to the Google Sheet so that
the M1 MacBook can read patterns/templates without accessing SQLite directly.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

# Import the Sheets client
from sheets_client import GoogleSheetsClient, SheetsClientError

# ============================================
# CONFIGURATION
# ============================================

# Path to SQLite database (same directory as this script)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_learning.db")

# Path to service account credentials
CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "claude-mcp-484702-9f05ed595764.json"
)

# Google Sheet ID - UPDATE THIS with your actual spreadsheet ID
# Found in URL: https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit
SPREADSHEET_ID = "10HUq9V3tzQQXJvHaAmCIyvhMamX1FxYu4qQPxn9Qql0"

# Sheet names and ranges
PATTERNS_SHEET = "Patterns"
PATTERNS_RANGE = f"{PATTERNS_SHEET}!A:F"  # pattern_name, keywords, confidence_boost, usage_count, success_rate, notes

TEMPLATES_SHEET = "Templates"
TEMPLATES_RANGE = f"{TEMPLATES_SHEET}!A:F"  # template_id, template_name, template_body, variables, attachments, usage_count

CONTACTS_SHEET = "Contacts"
CONTACTS_RANGE = f"{CONTACTS_SHEET}!A:G"  # email, name, relationship, preferred_tone, common_topics, interactions, last_contact


# ============================================
# DATABASE READER
# ============================================

class MCPDatabaseReader:
    """Reads learning data from SQLite database."""

    def __init__(self, db_path: str = None):
        """Initialize with database path."""
        self.db_path = db_path or DB_PATH

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database not found: {self.db_path}")

    def get_patterns(self) -> List[Dict]:
        """Read all patterns from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT pattern_name, keywords, confidence_boost, usage_count,
                   success_rate, notes
            FROM pattern_hints
            ORDER BY confidence_boost DESC
        """)

        patterns = []
        for row in cursor.fetchall():
            # Parse keywords JSON
            keywords = row[1]
            if keywords:
                try:
                    keywords_list = json.loads(keywords)
                    keywords_str = ", ".join(keywords_list) if isinstance(keywords_list, list) else str(keywords_list)
                except:
                    keywords_str = str(keywords)
            else:
                keywords_str = ""

            patterns.append({
                'pattern_name': row[0] or "",
                'keywords': keywords_str,
                'confidence_boost': row[2] or 0,
                'usage_count': row[3] or 0,
                'success_rate': round((row[4] or 0) * 100, 1),
                'notes': row[5] or ""
            })

        conn.close()
        return patterns

    def get_templates(self) -> List[Dict]:
        """Read all templates from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT template_id, template_name, template_body, variables,
                   attachments, usage_count
            FROM templates
            ORDER BY usage_count DESC
        """)

        templates = []
        for row in cursor.fetchall():
            # Parse variables JSON
            variables = row[3]
            if variables:
                try:
                    variables_list = json.loads(variables)
                    variables_str = ", ".join(variables_list) if isinstance(variables_list, list) else str(variables_list)
                except:
                    variables_str = str(variables)
            else:
                variables_str = ""

            # Parse attachments JSON
            attachments = row[4]
            if attachments:
                try:
                    attachments_list = json.loads(attachments)
                    attachments_str = ", ".join(attachments_list) if isinstance(attachments_list, list) else str(attachments_list)
                except:
                    attachments_str = str(attachments)
            else:
                attachments_str = ""

            templates.append({
                'template_id': row[0] or "",
                'template_name': row[1] or "",
                'template_body': row[2] or "",
                'variables': variables_str,
                'attachments': attachments_str,
                'usage_count': row[5] or 0
            })

        conn.close()
        return templates

    def get_contacts(self) -> List[Dict]:
        """Read all contacts from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT contact_email, contact_name, relationship_type, preferred_tone,
                   common_topics, interaction_count, last_interaction
            FROM contact_patterns
            ORDER BY interaction_count DESC
        """)

        contacts = []
        for row in cursor.fetchall():
            # Parse common_topics JSON
            topics = row[4]
            if topics:
                try:
                    topics_list = json.loads(topics)
                    topics_str = ", ".join(topics_list) if isinstance(topics_list, list) else str(topics_list)
                except:
                    topics_str = str(topics)
            else:
                topics_str = ""

            contacts.append({
                'email': row[0] or "",
                'name': row[1] or "",
                'relationship': row[2] or "",
                'preferred_tone': row[3] or "",
                'common_topics': topics_str,
                'interactions': row[5] or 0,
                'last_contact': row[6] or ""
            })

        conn.close()
        return contacts

    def get_stats(self) -> Dict:
        """Calculate summary statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) FROM pattern_hints")
        stats['total_patterns'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM templates")
        stats['total_templates'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM contact_patterns")
        stats['contacts_learned'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM writing_patterns")
        stats['writing_patterns'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM responses WHERE sent = 1")
        stats['emails_processed'] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT AVG(edit_percentage)
            FROM responses
            WHERE sent = 1 AND edit_percentage IS NOT NULL
        """)
        avg_edit = cursor.fetchone()[0]
        stats['avg_edit_rate'] = round(avg_edit, 1) if avg_edit else 0.0

        conn.close()
        return stats


# ============================================
# SHEETS SYNC FUNCTIONS
# ============================================

def sync_patterns_to_sheets(
    client: GoogleSheetsClient,
    spreadsheet_id: str,
    patterns: List[Dict]
) -> Dict:
    """
    Sync patterns from SQLite to Google Sheets.
    Clears existing data and writes fresh patterns.
    """
    # Header row
    header = ["Pattern Name", "Keywords", "Confidence Boost", "Usage Count", "Success Rate %", "Notes"]

    # Convert patterns to rows
    rows = [header]
    for p in patterns:
        rows.append([
            p['pattern_name'],
            p['keywords'],
            p['confidence_boost'],
            p['usage_count'],
            p['success_rate'],
            p['notes']
        ])

    # Write to sheet (overwrite existing data)
    result = client.write_range(
        spreadsheet_id,
        f"{PATTERNS_SHEET}!A1",
        rows
    )

    return result


def sync_templates_to_sheets(
    client: GoogleSheetsClient,
    spreadsheet_id: str,
    templates: List[Dict]
) -> Dict:
    """
    Sync templates from SQLite to Google Sheets.
    """
    # Header row
    header = ["Template ID", "Template Name", "Template Body", "Variables", "Attachments", "Usage Count"]

    # Convert templates to rows
    rows = [header]
    for t in templates:
        rows.append([
            t['template_id'],
            t['template_name'],
            t['template_body'],
            t['variables'],
            t['attachments'],
            t['usage_count']
        ])

    # Write to sheet
    result = client.write_range(
        spreadsheet_id,
        f"{TEMPLATES_SHEET}!A1",
        rows
    )

    return result


def sync_contacts_to_sheets(
    client: GoogleSheetsClient,
    spreadsheet_id: str,
    contacts: List[Dict]
) -> Dict:
    """
    Sync contacts from SQLite to Google Sheets.
    """
    # Header row
    header = ["Email", "Name", "Relationship", "Preferred Tone", "Common Topics", "Interactions", "Last Contact"]

    # Convert contacts to rows
    rows = [header]
    for c in contacts:
        rows.append([
            c['email'],
            c['name'],
            c['relationship'],
            c['preferred_tone'],
            c['common_topics'],
            c['interactions'],
            c['last_contact']
        ])

    # Write to sheet
    result = client.write_range(
        spreadsheet_id,
        f"{CONTACTS_SHEET}!A1",
        rows
    )

    return result


# ============================================
# MAIN SYNC FUNCTION
# ============================================

def main():
    """Main sync function."""

    print()
    print("=" * 70)
    print("  BOOTSTRAP SYNC: SQLite -> Google Sheets")
    print("  For Mode 4 (M1) to read patterns/templates")
    print("=" * 70)
    print()

    # Check configuration
    if SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
        print("ERROR: Please configure SPREADSHEET_ID in this script.")
        print()
        print("To find your spreadsheet ID:")
        print("  1. Open your Google Sheet")
        print("  2. Copy the ID from the URL:")
        print("     https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit")
        print("  3. Update SPREADSHEET_ID at the top of this script")
        print()
        input("Press Enter to exit...")
        return

    # Step 1: Read from SQLite
    print("Step 1: Reading from SQLite database...")
    print(f"  Database: {DB_PATH}")

    try:
        reader = MCPDatabaseReader()

        patterns = reader.get_patterns()
        print(f"  Loaded {len(patterns)} patterns")

        templates = reader.get_templates()
        print(f"  Loaded {len(templates)} templates")

        contacts = reader.get_contacts()
        print(f"  Loaded {len(contacts)} contacts")

        stats = reader.get_stats()
        print(f"  Stats: {stats['emails_processed']} emails processed, "
              f"{stats['avg_edit_rate']}% avg edit rate")
        print()

    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        print()
        input("Press Enter to exit...")
        return
    except Exception as e:
        print(f"  ERROR reading database: {e}")
        print()
        input("Press Enter to exit...")
        return

    # Step 2: Connect to Google Sheets
    print("Step 2: Connecting to Google Sheets...")
    print(f"  Credentials: {CREDENTIALS_PATH}")

    if not os.path.exists(CREDENTIALS_PATH):
        print(f"  ERROR: Credentials file not found!")
        print()
        print("  Please ensure your service account JSON file is at:")
        print(f"    {CREDENTIALS_PATH}")
        print()
        input("Press Enter to exit...")
        return

    try:
        client = GoogleSheetsClient(CREDENTIALS_PATH)
        client.connect()
        print("  Connected successfully!")
        print()

    except SheetsClientError as e:
        print(f"  ERROR: {e}")
        print()
        input("Press Enter to exit...")
        return

    # Step 3: Sync to Sheets
    print("Step 3: Syncing to Google Sheets...")
    print(f"  Spreadsheet ID: {SPREADSHEET_ID}")
    print()

    try:
        # Sync patterns
        print(f"  Syncing patterns to '{PATTERNS_SHEET}' sheet...")
        result = sync_patterns_to_sheets(client, SPREADSHEET_ID, patterns)
        if result.get('success'):
            print(f"    Updated {result.get('updated_rows', 0)} rows")
        else:
            print(f"    ERROR: {result.get('error')}")
            print(f"    Details: {result.get('details', 'None')}")

        # Sync templates
        print(f"  Syncing templates to '{TEMPLATES_SHEET}' sheet...")
        result = sync_templates_to_sheets(client, SPREADSHEET_ID, templates)
        if result.get('success'):
            print(f"    Updated {result.get('updated_rows', 0)} rows")
        else:
            print(f"    ERROR: {result.get('error')}")
            print(f"    Details: {result.get('details', 'None')}")

        # Sync contacts
        print(f"  Syncing contacts to '{CONTACTS_SHEET}' sheet...")
        result = sync_contacts_to_sheets(client, SPREADSHEET_ID, contacts)
        if result.get('success'):
            print(f"    Updated {result.get('updated_rows', 0)} rows")
        else:
            print(f"    ERROR: {result.get('error')}")
            print(f"    Details: {result.get('details', 'None')}")

        print()

    except Exception as e:
        print(f"  ERROR during sync: {e}")
        print()
        input("Press Enter to exit...")
        return
    finally:
        client.close()

    # Summary
    print("=" * 70)
    print("  SYNC COMPLETE!")
    print("=" * 70)
    print()
    print(f"  Synced to Google Sheet:")
    print(f"    - {len(patterns)} patterns")
    print(f"    - {len(templates)} templates")
    print(f"    - {len(contacts)} contacts")
    print()
    print("  M1 (Mode 4) can now read this data from Sheets.")
    print()
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print()
    print("=" * 70)
    print()

    input("Press Enter to close...")


if __name__ == "__main__":
    main()
