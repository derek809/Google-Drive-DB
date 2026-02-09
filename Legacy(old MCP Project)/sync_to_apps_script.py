#!/usr/bin/env python3
"""
MCP Learning Sync to Apps Script
One-click button script - reads database and updates Apps Script
"""

import sqlite3
import json
import os
import requests
from datetime import datetime
from typing import Dict, List

# ============================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================

# STEP 1: Deploy AppsScript_WithSyncEndpoint.js as Web App
# STEP 2: Copy the Web App URL here (between the quotes)
APPS_SCRIPT_WEB_APP_URL = 'https://script.google.com/macros/s/AKfycbwf7AorGaWuwbbTS3iWQan4z5IRkj6UAma2xaRcCmpJzPolTMsikXiyi1rqNecI8PF7/exec'

# Optional: Google Sheet ID for dashboard (can leave as-is if you don't want dashboard)
GOOGLE_SHEET_ID = 'YOUR_SHEET_ID_HERE'

# ============================================
# DATABASE READER
# ============================================

class MCPDatabaseReader:
    """Reads learning data from SQLite database"""
    
    def __init__(self, db_path: str = None):
        """Initialize with database path"""
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "mcp_learning.db")
        
        self.db_path = db_path
        
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database not found: {self.db_path}")
    
    def get_patterns(self) -> List[Dict]:
        """Read all patterns from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pattern_name, keywords, confidence_boost, usage_count, 
                   success_rate, notes, last_updated
            FROM pattern_hints
            ORDER BY confidence_boost DESC
        """)
        
        patterns = []
        for row in cursor.fetchall():
            # Parse keywords JSON
            keywords = row[1]
            if keywords:
                try:
                    keywords = json.loads(keywords)
                except:
                    keywords = []
            else:
                keywords = []
            
            patterns.append({
                'pattern_name': row[0],
                'keywords': keywords,
                'confidence_boost': row[2] or 0,
                'usage_count': row[3] or 0,
                'success_rate': round((row[4] or 0) * 100, 1),
                'notes': row[5] or '',
                'last_updated': row[6] or ''
            })
        
        conn.close()
        return patterns
    
    def get_templates(self) -> List[Dict]:
        """Read all templates from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT template_id, template_name, template_body, variables,
                   attachments, usage_count, success_rate, last_used
            FROM templates
            ORDER BY usage_count DESC
        """)
        
        templates = []
        for row in cursor.fetchall():
            # Parse variables JSON
            variables = row[3]
            if variables:
                try:
                    variables = json.loads(variables)
                except:
                    variables = []
            else:
                variables = []
            
            # Parse attachments JSON
            attachments = row[4]
            if attachments:
                try:
                    attachments = json.loads(attachments)
                except:
                    attachments = []
            else:
                attachments = []
            
            templates.append({
                'template_id': row[0],
                'template_name': row[1],
                'template_body': row[2],
                'variables': variables,
                'attachments': attachments,
                'usage_count': row[5] or 0,
                'success_rate': round((row[6] or 0) * 100, 1),
                'last_used': row[7] or ''
            })
        
        conn.close()
        return templates
    
    def get_stats(self) -> Dict:
        """Calculate summary statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Count patterns
        cursor.execute("SELECT COUNT(*) FROM pattern_hints")
        stats['total_patterns'] = cursor.fetchone()[0]
        
        # Count templates
        cursor.execute("SELECT COUNT(*) FROM templates")
        stats['total_templates'] = cursor.fetchone()[0]
        
        # Count learned contacts
        cursor.execute("SELECT COUNT(*) FROM contact_patterns")
        stats['contacts_learned'] = cursor.fetchone()[0]
        
        # Count writing patterns
        cursor.execute("SELECT COUNT(*) FROM writing_patterns")
        stats['writing_patterns'] = cursor.fetchone()[0]
        
        # Count processed emails
        cursor.execute("SELECT COUNT(*) FROM responses WHERE sent = 1")
        stats['emails_processed'] = cursor.fetchone()[0]
        
        # Calculate average edit rate
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
# APPS SCRIPT UPDATER
# ============================================

def update_apps_script(patterns: List[Dict], templates: List[Dict], stats: Dict) -> bool:
    """Send data to Apps Script Web App"""
    
    if APPS_SCRIPT_WEB_APP_URL == 'YOUR_WEB_APP_URL_HERE':
        print()
        print("❌ CONFIGURATION NEEDED")
        print("=" * 70)
        print()
        print("Please edit sync_to_apps_script.py and update:")
        print("  APPS_SCRIPT_WEB_APP_URL = 'your_actual_web_app_url_here'")
        print()
        print("To get your Web App URL:")
        print("  1. Open your Apps Script project")
        print("  2. Deploy → New deployment → Web app")
        print("  3. Execute as: Me")
        print("  4. Who has access: Anyone")
        print("  5. Copy the URL")
        print()
        return False
    
    try:
        payload = {
            'action': 'update_patterns',
            'patterns': patterns,
            'templates': templates,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }
        
        print("  Calling Apps Script Web App...")
        response = requests.post(
            APPS_SCRIPT_WEB_APP_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("  ✅ Apps Script updated successfully!")
                print(f"     {result.get('patterns_count', 0)} patterns cached")
                print(f"     {result.get('templates_count', 0)} templates cached")
                return True
            else:
                print(f"  ❌ Apps Script returned error: {result.get('message')}")
                return False
        else:
            print(f"  ❌ HTTP Error {response.status_code}")
            print(f"     Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("  ❌ Request timed out")
        print("     Apps Script may be slow or unreachable")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

# ============================================
# MAIN SYNC FUNCTION
# ============================================

def main():
    """Main sync function"""
    
    print()
    print("=" * 70)
    print("  🔄 MCP LEARNING SYNC TO APPS SCRIPT")
    print("=" * 70)
    print()
    
    # Step 1: Read from database
    print("📖 Step 1: Reading from database...")
    
    try:
        reader = MCPDatabaseReader()
        print(f"  Database: {reader.db_path}")
        print()
        
        patterns = reader.get_patterns()
        print(f"  ✓ Loaded {len(patterns)} patterns")
        
        templates = reader.get_templates()
        print(f"  ✓ Loaded {len(templates)} templates")
        
        stats = reader.get_stats()
        print(f"  ✓ Statistics calculated")
        print()
        
    except FileNotFoundError as e:
        print(f"  ❌ {e}")
        print()
        print("Make sure mcp_learning.db is in the same folder as this script")
        print()
        print("=" * 70)
        input("Press Enter to exit...")
        return
    except Exception as e:
        print(f"  ❌ Error reading database: {e}")
        print()
        print("=" * 70)
        input("Press Enter to exit...")
        return
    
    # Step 2: Update Apps Script
    print("📤 Step 2: Updating Apps Script...")
    print()
    
    success = update_apps_script(patterns, templates, stats)
    print()
    
    # Step 3: Summary
    print("=" * 70)
    
    if success:
        print("✅ SYNC COMPLETE!")
        print()
        print("Your Apps Script now has:")
        print(f"  • {len(patterns)} patterns with latest confidence scores")
        print(f"  • {len(templates)} templates with usage statistics")
        print(f"  • Learning data: {stats['contacts_learned']} contacts, " +
              f"{stats['writing_patterns']} phrases")
        print()
        print("Next batch processing will use this fresh data!")
        
        # Show some interesting stats
        if stats['emails_processed'] > 0:
            print()
            print("📊 Your Progress:")
            print(f"  • Emails processed: {stats['emails_processed']}")
            print(f"  • Average edit rate: {stats['avg_edit_rate']}%")
            
            # Find pattern with highest usage
            if patterns:
                top_pattern = max(patterns, key=lambda p: p['usage_count'])
                if top_pattern['usage_count'] > 0:
                    print(f"  • Most used pattern: {top_pattern['pattern_name']} " +
                          f"({top_pattern['usage_count']} times)")
    else:
        print("⚠️  SYNC INCOMPLETE")
        print()
        print("Apps Script update failed.")
        print("Check the error messages above and try again.")
        print()
        print("Common fixes:")
        print("  • Make sure APPS_SCRIPT_WEB_APP_URL is configured")
        print("  • Check that Apps Script is deployed as Web App")
        print("  • Verify 'Who has access' is set to 'Anyone'")
    
    print()
    print("=" * 70)
    print()
    
    input("Press Enter to close...")

if __name__ == "__main__":
    main()
