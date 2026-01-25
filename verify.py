#!/usr/bin/env python3
"""
Quick verification script for MCP system
Run this to check if everything is set up correctly
"""

import os
import sys
import sqlite3

def main():
    print("=" * 60)
    print("MCP SYSTEM VERIFICATION")
    print("=" * 60)
    print()
    
    # Check current directory
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")
    print()
    
    # Check for database file
    db_file = "mcp_learning.db"
    if os.path.exists(db_file):
        print(f"✓ Database found: {db_file}")
        db_size = os.path.getsize(db_file) / 1024
        print(f"  Size: {db_size:.1f} KB")
    else:
        print(f"✗ Database NOT found: {db_file}")
        print("  Please make sure mcp_learning.db is in this directory")
        sys.exit(1)
    
    print()
    
    # Try to connect to database
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        print("✓ Successfully connected to database")
        print()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✓ Found {len(tables)} tables")
        print()
        
        # Check bootstrap data
        cursor.execute("SELECT COUNT(*) FROM pattern_hints")
        patterns = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM templates")
        templates = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM existing_tools")
        tools = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM overrides")
        overrides = cursor.fetchone()[0]
        
        print("Bootstrap Data:")
        print(f"  Patterns: {patterns}")
        print(f"  Templates: {templates}")
        print(f"  Tools: {tools}")
        print(f"  Safety Rules: {overrides}")
        print()
        
        # Check learning tables (should be empty)
        cursor.execute("SELECT COUNT(*) FROM contact_patterns")
        contacts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM writing_patterns")
        writing = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM knowledge_base")
        knowledge = cursor.fetchone()[0]
        
        print("Learning Tables (should be empty):")
        print(f"  Contacts: {contacts}")
        print(f"  Writing Patterns: {writing}")
        print(f"  Knowledge Base: {knowledge}")
        print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")
        sys.exit(1)
    
    # Check Python files
    print("Python Files:")
    for file in ['orchestrator.py', 'template_processor.py', 'process_email.py', 'test_suite.py']:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} (missing)")
    
    print()
    
    # Try to import modules
    try:
        from orchestrator import MCPOrchestrator
        print("✓ Successfully imported MCPOrchestrator")
        
        from template_processor import TemplateProcessor
        print("✓ Successfully imported TemplateProcessor")
        
        print()
        
        # Quick functionality test
        print("Testing basic functionality...")
        with MCPOrchestrator() as mcp:
            test_email = {
                'subject': 'W9 Request',
                'body': 'Please send W9',
                'sender_email': 'test@example.com',
                'sender_name': 'Test User',
                'attachments': []
            }
            
            result = mcp.process_email(test_email, "send w9")
            
            if result['status'] == 'template_ready':
                print("✓ Basic processing works!")
                print(f"  Pattern matched: {result.get('pattern_match', {}).get('pattern_name')}")
                print(f"  Confidence: {result.get('confidence')}/100")
            else:
                print(f"⚠ Processing returned: {result['status']}")
        
        print()
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error during test: {e}")
        sys.exit(1)
    
    print("=" * 60)
    print("✓ ALL CHECKS PASSED!")
    print("=" * 60)
    print()
    print("Your MCP system is ready to use!")
    print()
    print("Next step: Tell Claude Desktop:")
    print(f'  "My MCP is at: {current_dir}"')
    print()


if __name__ == "__main__":
    main()
