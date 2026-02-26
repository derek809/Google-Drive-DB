#!/usr/bin/env python3
"""
STANDARD EMAIL OUTPUT FORMAT - Jarvis Work Bot
This is the default format for displaying emails when user says "show me my emails"
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from LLM.gmail_client import GmailClient

def show_emails(label_filter=None, max_results=5):
    """Display emails in standard Jarvis format"""
    
    # Set paths
    credentials_path = os.path.join(os.path.dirname(__file__), "credentials/gmail_credentials.json")
    token_path = os.path.join(os.path.dirname(__file__), "credentials/gmail_token.json")
    
    gc = GmailClient(credentials_path=credentials_path, token_path=token_path)
    gc.authenticate()
    
    # Get labels
    labels = gc.service.users().labels().list(userId='me').execute()['labels']
    
    # Find MCP or requested label
    if label_filter:
        mcp_labels = [l for l in labels if label_filter.lower() in l['name'].lower()]
    else:
        mcp_labels = [l for l in labels if 'mcp' in l['name'].lower()]
    
    if mcp_labels:
        messages = gc.service.users().messages().list(
            userId='me', 
            labelIds=[mcp_labels[0]['id']], 
            maxResults=max_results
        ).execute()
        label_name = mcp_labels[0]['name']
    else:
        # Fallback to inbox
        messages = gc.service.users().messages().list(
            userId='me', 
            maxResults=max_results
        ).execute()
        label_name = "INBOX"
    
    # Display in standard format
    print(f"\n🎯 THESE ARE YOUR REAL EMAILS!")
    print(f"📧 YOUR {label_name.upper()} EMAILS:\n")
    
    for i, msg in enumerate(messages.get('messages', []), 1):
        email = gc.service.users().messages().get(
            userId='me', 
            id=msg['id'], 
            format='metadata'
        ).execute()
        
        headers = dict([(h['name'], h['value']) for h in email['payload']['headers']])
        
        sender = headers.get('From', 'Unknown')
        subject = headers.get('Subject', 'No Subject')
        date = headers.get('Date', '')
        snippet = email.get('snippet', '')[:80]
        
        print(f"{i}. 📞 {sender}")
        print(f"   📝 {subject}")
        print(f"   📅 {date}")
        print(f"   💬 {snippet}...")
        print()
    
    return len(messages.get('messages', []))

if __name__ == "__main__":
    # Run with optional label filter
    label = sys.argv[1] if len(sys.argv) > 1 else None
    count = show_emails(label_filter=label)
    print(f"✅ Jarvis work bot - {count} emails displayed")
