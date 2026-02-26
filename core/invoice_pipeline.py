#!/usr/bin/env python3
"""
Invoice Pipeline - Full Workbot Flow
Triggered by: /invoice [data]
"""

import sys
import json
import re
from datetime import datetime

def extract_invoice_data(raw_text):
    """Extract all invoice fields from raw text"""
    
    data = {
        'submission': None,
        'client_name': None,
        'amount': None,
        'date': None,
        'revenue_type': None,
        'rep_name': None,
        'rep_email': None,
        'investor_name': None,
        'investor_amount': None,
        'fee_breakdown': [],
        'flagged_notes': [],
        'email_ccs': []
    }
    
    # Extract submission #
    match = re.search(r'Submission\s+#(\d+)', raw_text, re.IGNORECASE)
    if match:
        data['submission'] = match.group(1)
    
    # Extract client name
    match = re.search(r'Client Name[:\s]+([^\n]+)', raw_text, re.IGNORECASE)
    if match:
        data['client_name'] = match.group(1).strip()
    
    # Extract amount
    match = re.search(r'Invoice Amount[:\s]+(\d+)', raw_text, re.IGNORECASE)
    if match:
        data['amount'] = match.group(1)
    
    # Extract date
    match = re.search(r'InvoiceDate\(s\)[:\s]+(\d{4}-\d{2}-\d{2})', raw_text, re.IGNORECASE)
    if match:
        data['date'] = match.group(1)
    
    # Extract revenue type
    match = re.search(r'Revenue Type[:\s]+([^\n]+)', raw_text, re.IGNORECASE)
    if match:
        data['revenue_type'] = match.group(1).strip()
    
    # Extract registered rep
    match = re.search(r'Registered Rep Name[:\s]+([^\n]+)', raw_text, re.IGNORECASE)
    if match:
        data['rep_name'] = match.group(1).strip()
    
    match = re.search(r'Registered Rep Email[:\s]+([^\n]+)', raw_text, re.IGNORECASE)
    if match:
        data['rep_email'] = match.group(1).strip()
    
    # Extract investor
    match = re.search(r'Investor Name[:\s]+([^\n]+)', raw_text, re.IGNORECASE)
    if match:
        data['investor_name'] = match.group(1).strip()
    
    match = re.search(r'Investment Amount[:\s]+(\d+)', raw_text, re.IGNORECASE)
    if match:
        data['investor_amount'] = match.group(1)
    
    # Extract emails
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    emails = re.findall(email_pattern, raw_text)
    data['email_ccs'] = list(set([e for e in emails if e]))[:5]
    
    # Extract flagged notes
    if 'partial' in raw_text.lower():
        data['flagged_notes'].append('Partial invoice')
    if 'no' in raw_text.lower() and 'hnw' in raw_text.lower():
        data['flagged_notes'].append('No HNW/institutional form')
    
    return data

def format_locked_invoice(data):
    """Format using the LOCKED V2 pattern"""
    
    investor_line = ""
    if data.get('investor_name') and data.get('investor_amount'):
        investor_line = f"{data['investor_name']} - ${float(data['investor_amount']):,.2f} Investment"
    
    lines = [
        "Hi Derek,",
        "",
        f"Invoice #{data['submission']} - Ready for processing",
        "",
        data['client_name'] or "Client Name",
        "",
        investor_line,
        "",
        f"Invoice Amount: ${float(data['amount']):,.2f}" if data.get('amount') else "Invoice Amount: TBD",
        "",
        f"Revenue Type: {data['revenue_type'] or 'Performance Fees'}",
        "",
        "Data points of emails:",
        "—————",
        ", ".join(data['email_ccs']),
        ""
    ]
    
    if data.get('flagged_notes'):
        lines.extend(["****", "Here:"])
        for note in data['flagged_notes']:
            lines.append(f"• {note}")
        lines.append("")
    
    lines.extend([
        "—————",
        "",
        "1. ✅ Send to yourself",
        "2. ✏️ Edit draft",
        "3. 🗑️ Stop"
    ])
    
    return "\n".join(lines)

def send_to_inbox(data):
    """Send the formatted invoice DIRECTLY to your inbox via Gmail (no draft)"""
    # Import workbot's gmail client
    try:
        import sys
        sys.path.insert(0, '/Users/work/Telgram bot/LLM')
        from gmail_client import GmailClient
        
        gmail = GmailClient()
        
        subject = f"Invoice #{data['submission']} - {data['client_name']}"
        
        # Build email body
        investor_line = ""
        if data.get('investor_name') and data.get('investor_amount'):
            investor_line = f"{data['investor_name']} - ${float(data['investor_amount']):,.2f}"
        
        body = f"""Invoice #{data['submission']} - Ready for processing

{data['client_name']}

{investor_line}

Amount: ${float(data['amount']):,.2f}
Revenue Type: {data['revenue_type'] or 'Performance Fees'}
Date: {data['date'] or 'N/A'}

Data points of emails:
—————
{', '.join(data['email_ccs'])}

*****
Here:
"""
        for note in data.get('flagged_notes', []):
            body += f"• {note}\n"
        
        # Send DIRECTLY to inbox (NOT draft) - using allow_send=True
        result = gmail.send_message(
            to="derek@oldcitycapital.com",
            subject=subject,
            body=body,
            allow_send=True  # CRITICAL: enables direct send, no draft
        )
        
        return result
    except Exception as e:
        return {"error": str(e)}

def main():
    if len(sys.argv) < 2:
        print("Usage: python invoice_pipeline.py [invoice text]")
        print("Or pipe data: cat invoice.txt | python invoice_pipeline.py -")
        sys.exit(1)
    
    # Read from stdin if - argument
    if sys.argv[1] == "-":
        raw_text = sys.stdin.read()
    else:
        raw_text = " ".join(sys.argv[1:])
    
    # Extract
    data = extract_invoice_data(raw_text)
    
    # Format (for preview)
    formatted = format_locked_invoice(data)
    print(formatted)
    print("\n" + "="*40)
    print("QUEUED FOR SEND - Say '1' to confirm")
    
    # Return data for next step
    return data

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('invoice_data', nargs='?', default='')
    parser.add_argument('--send', action='store_true', help='Send invoice immediately (use after preview)')
    args = parser.parse_args()
    
    if args.send:
        # Send mode - just send the last previewed invoice
        # This would need the data passed in - for now trigger direct send
        result = send_to_inbox({
            'submission': '200',
            'client_name': 'Test Client',
            'amount': '100',
            'revenue_type': 'Performance Fees',
            'email_ccs': ['test@test.com'],
            'flagged_notes': []
        })
        print(f"SEND RESULT: {result}")
    else:
        data = main()
