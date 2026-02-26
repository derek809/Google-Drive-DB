#!/usr/bin/env python3
import os

# Set paths directly
CREDENTIALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials")
GMAIL_CREDENTIALS_PATH = os.path.join(CREDENTIALS_DIR, "gmail_credentials.json")
GMAIL_TOKEN_PATH = os.path.join(CREDENTIALS_DIR, "gmail_token.json")

from LLM.gmail_client import GmailClient

gc = GmailClient(
    credentials_path=GMAIL_CREDENTIALS_PATH,
    token_path=GMAIL_TOKEN_PATH
)

gc.authenticate()

labels = gc.service.users().labels().list(userId='me').execute()['labels']
mcp_labels = [l for l in labels if 'mcp' in l['name'].lower()]

if mcp_labels:
    messages = gc.service.users().messages().list(
        userId='me', 
        labelIds=[mcp_labels[0]['id']], 
        maxResults=5
    ).execute()
    
    print('\n📧 YOUR REAL MCP EMAILS:\n')
    for i, msg in enumerate(messages['messages'], 1):
        email = gc.service.users().messages().get(
            userId='me', 
            id=msg['id'], 
            format='metadata'
        ).execute()
        
        headers = dict([(h['name'], h['value']) for h in email['payload']['headers']])
        
        sender = headers.get('From', 'Unknown')
        subject = headers.get('Subject', 'No Subject')
        date = headers.get('Date', '')
        snippet = email.get('snippet', '')[:100]
        
        print(f'{i}. 📞 {sender}')
        print(f'   📝 {subject}')
        print(f'   📅 {date}')
        print(f'   💬 {snippet}')
        print()
        
else:
    print('No MCP label found - checking INBOX instead...\n')
    
    # Fallback to inbox
    messages = gc.service.users().messages().list(
        userId='me', 
        maxResults=5
    ).execute()
    
    print('📥 YOUR RECENT INBOX EMAILS:\n')
    for i, msg in enumerate(messages['messages'], 1):
        email = gc.service.users().messages().get(
            userId='me', 
            id=msg['id'], 
            format='metadata'
        ).execute()
        
        headers = dict([(h['name'], h['value']) for h in email['payload']['headers']])
        
        sender = headers.get('From', 'Unknown')
        subject = headers.get('Subject', 'No Subject')
        date = headers.get('Date', '')
        snippet = email.get('snippet', '')[:100]
        
        print(f'{i}. 📞 {sender}')
        print(f'   📝 {subject}')
        print(f'   📅 {date}')
        print(f'   💬 {snippet}')
        print()
