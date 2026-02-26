#!/usr/bin/env python3
"""
IMMEDIATE MCP EMAIL PULL - On Demand
Usage: python3 pull_mcp.py
Grabs MCP emails instantly - no waiting for 2-hour check
"""

import os
import sys
import json
from datetime import datetime

# Add bot to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from LLM.gmail_client import GmailClient

def pull_mcp_emails():
    """Immediately fetch MCP emails on demand"""
    
    print("⚡ IMMEDIATE MCP PULL - Executing now...\n")
    
    # Load credentials
    credentials_path = os.path.join(os.path.dirname(__file__), "credentials/gmail_credentials.json")
    token_path = os.path.join(os.path.dirname(__file__), "credentials/gmail_token.json")
    
    gc = GmailClient(credentials_path=credentials_path, token_path=token_path)
    gc.authenticate()
    
    # Get labels
    labels = gc.service.users().labels().list(userId='me').execute()['labels']
    mcp_labels = [l for l in labels if 'mcp' in l['name'].lower()]
    
    if not mcp_labels:
        print("❌ No MCP label found")
        return
    
    # Fetch MCP emails immediately
    mcp_label = mcp_labels[0]
    messages = gc.service.users().messages().list(
        userId='me', 
        labelIds=[mcp_label['id']], 
        maxResults=10
    ).execute()
    
    email_count = len(messages.get('messages', []))
    
    print(f"⚡ PULLED {email_count} MCP EMAILS FROM GMAIL\n")
    print(f"📧 Label: {mcp_label['name']}")
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Display emails
    for i, msg in enumerate(messages.get('messages', []), 1):
        email = gc.service.users().messages().get(
            userId='me', 
            id=msg['id'], 
            format='full'
        ).execute()
        
        headers = dict([(h['name'], h['value']) for h in email['payload']['headers']])
        
        sender = headers.get('From', 'Unknown')
        subject = headers.get('Subject', 'No Subject')
        date = headers.get('Date', '')
        snippet = email.get('snippet', '')
        
        print(f"\n{i}. 📞 {sender}")
        print(f"   📝 {subject}")
        print(f"   📅 {date}")
        print(f"   💬 {snippet[:100]}...")
    
    print("\n" + "=" * 50)
    print(f"✅ IMMEDIATE PULL COMPLETE - {email_count} emails fetched")
    
    return messages.get('messages', [])

if __name__ == "__main__":
    pull_mcp_emails()
