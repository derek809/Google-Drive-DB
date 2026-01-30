"""
Gmail Client for Mode 4
Provides email search and draft creation functionality.

Usage:
    from gmail_client import GmailClient

    client = GmailClient()
    client.authenticate()

    # Search for email
    email = client.search_email("W9 Request")

    # Create draft reply
    draft = client.create_draft(
        thread_id=email['thread_id'],
        to=email['sender_email'],
        subject=f"Re: {email['subject']}",
        body="Here is your W9..."
    )
"""

import os
import base64
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Any

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class GmailClientError(Exception):
    """Custom exception for Gmail client errors."""
    pass


class GmailClient:
    """
    Gmail API client for searching emails and creating drafts.

    Supports OAuth2 authentication for user mailbox access.
    """

    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/gmail.modify'
    ]

    def __init__(
        self,
        credentials_path: str = None,
        token_path: str = None
    ):
        """
        Initialize Gmail client.

        Args:
            credentials_path: Path to OAuth credentials JSON (from Google Cloud Console)
            token_path: Path to store/load the OAuth token
        """
        if not GOOGLE_API_AVAILABLE:
            raise GmailClientError(
                "Google API packages not installed. Run:\n"
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )

        # Try to import config for default paths
        try:
            from m1_config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
            self.credentials_path = credentials_path or GMAIL_CREDENTIALS_PATH
            self.token_path = token_path or GMAIL_TOKEN_PATH
        except ImportError:
            self.credentials_path = credentials_path
            self.token_path = token_path

        self.service = None
        self._creds = None

    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth2.

        On first run, opens browser for user consent.
        Subsequent runs use saved token.

        Returns:
            True if authentication successful
        """
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            raise GmailClientError(
                f"OAuth credentials file not found: {self.credentials_path}\n\n"
                "To set up Gmail OAuth:\n"
                "1. Go to console.cloud.google.com\n"
                "2. Create a project and enable Gmail API\n"
                "3. Go to APIs & Services > Credentials\n"
                "4. Create OAuth 2.0 Client ID (Desktop app)\n"
                "5. Download the JSON and save to credentials path"
            )

        # Check if we have a saved token
        if self.token_path and os.path.exists(self.token_path):
            self._creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)

        # If no valid credentials, authenticate
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                self._creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES
                )
                self._creds = flow.run_local_server(port=0)

            # Save the credentials for next run
            if self.token_path:
                os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
                with open(self.token_path, 'w') as token:
                    token.write(self._creds.to_json())

        self.service = build('gmail', 'v1', credentials=self._creds)
        return True

    def _ensure_authenticated(self):
        """Ensure client is authenticated."""
        if self.service is None:
            self.authenticate()

    # ==================
    # EMAIL SEARCH
    # ==================

    def search_email(
        self,
        reference: str,
        search_type: str = "auto",
        max_results: int = 5,
        days_back: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Search for an email matching the reference.

        Args:
            reference: Email reference (subject, sender email, or keyword)
            search_type: How to search - "subject", "sender", "keyword", or "auto"
            max_results: Maximum number of results to return
            days_back: How many days back to search

        Returns:
            Dict with email data if found, None otherwise
        """
        self._ensure_authenticated()

        # Build search query
        query = self._build_search_query(reference, search_type, days_back)

        try:
            # Search for messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                return None

            # Get the first (most recent) match
            msg_id = messages[0]['id']
            return self.get_email(msg_id)

        except HttpError as e:
            raise GmailClientError(f"Gmail API error: {e}")

    def search_emails(
        self,
        reference: str,
        search_type: str = "auto",
        max_results: int = 10,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Search for multiple emails matching the reference.

        Returns:
            List of email dicts
        """
        self._ensure_authenticated()

        query = self._build_search_query(reference, search_type, days_back)

        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            emails = []

            for msg in messages:
                email = self.get_email(msg['id'])
                if email:
                    emails.append(email)

            return emails

        except HttpError as e:
            raise GmailClientError(f"Gmail API error: {e}")

    def _build_search_query(
        self,
        reference: str,
        search_type: str,
        days_back: int
    ) -> str:
        """Build Gmail search query from reference."""
        # Date filter
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
        date_filter = f"after:{after_date}"

        # Determine search type if auto
        if search_type == "auto":
            if "@" in reference:
                search_type = "sender"
            elif reference.lower().startswith("re:") or reference.lower().startswith("subject:"):
                search_type = "subject"
                reference = reference.replace("Re:", "").replace("re:", "").replace("subject:", "").strip()
            else:
                search_type = "keyword"

        # Build query
        if search_type == "subject":
            return f'subject:"{reference}" {date_filter}'
        elif search_type == "sender":
            return f'from:{reference} {date_filter}'
        elif search_type == "keyword":
            return f'{reference} {date_filter}'
        else:
            return f'{reference} {date_filter}'

    def get_email(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full email data by message ID.

        Returns:
            Dict with email details
        """
        self._ensure_authenticated()

        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # Extract headers
            headers = {h['name'].lower(): h['value'] for h in message['payload'].get('headers', [])}

            # Extract body
            body = self._extract_body(message['payload'])

            # Parse sender
            from_header = headers.get('from', '')
            sender_name, sender_email = self._parse_from_header(from_header)

            return {
                'message_id': message_id,
                'thread_id': message.get('threadId'),
                'subject': headers.get('subject', '(no subject)'),
                'sender_email': sender_email,
                'sender_name': sender_name,
                'to': headers.get('to', ''),
                'date': headers.get('date', ''),
                'body': body,
                'snippet': message.get('snippet', ''),
                'labels': message.get('labelIds', [])
            }

        except HttpError as e:
            raise GmailClientError(f"Failed to get email: {e}")

    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from message payload."""
        body = ""

        if 'body' in payload and payload['body'].get('data'):
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

        elif 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')

                if mime_type == 'text/plain':
                    if part['body'].get('data'):
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break

                elif mime_type == 'multipart/alternative':
                    # Recursive for nested parts
                    body = self._extract_body(part)
                    if body:
                        break

        return body

    def _parse_from_header(self, from_header: str) -> tuple:
        """Parse From header into (name, email)."""
        import re

        # Try pattern: "Name <email@example.com>"
        match = re.match(r'"?([^"<]+)"?\s*<([^>]+)>', from_header)
        if match:
            return match.group(1).strip(), match.group(2).strip()

        # Try pattern: "email@example.com"
        match = re.match(r'<?([^<>\s]+@[^<>\s]+)>?', from_header)
        if match:
            email = match.group(1)
            return email.split('@')[0], email

        return "", from_header

    # ==================
    # DRAFT CREATION
    # ==================

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str = None,
        reply_to_message_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a draft email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body text
            thread_id: Optional thread ID (for replies)
            reply_to_message_id: Optional message ID being replied to

        Returns:
            Dict with draft ID and URL
        """
        self._ensure_authenticated()

        # Create message
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject

        # Add reply headers if this is a reply
        if reply_to_message_id:
            # Get the original message to get Message-ID header
            try:
                original = self.service.users().messages().get(
                    userId='me',
                    id=reply_to_message_id,
                    format='metadata',
                    metadataHeaders=['Message-ID']
                ).execute()

                headers = {h['name']: h['value'] for h in original['payload'].get('headers', [])}
                if 'Message-ID' in headers:
                    message['In-Reply-To'] = headers['Message-ID']
                    message['References'] = headers['Message-ID']
            except:
                pass  # Continue without reply headers

        # Encode message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

        # Create draft body
        draft_body = {'message': {'raw': raw}}

        # Add thread ID for replies
        if thread_id:
            draft_body['message']['threadId'] = thread_id

        try:
            draft = self.service.users().drafts().create(
                userId='me',
                body=draft_body
            ).execute()

            draft_id = draft['id']
            draft_message_id = draft['message']['id']

            # Build draft URL
            draft_url = f"https://mail.google.com/mail/u/0/#drafts?compose={draft_message_id}"

            return {
                'success': True,
                'draft_id': draft_id,
                'message_id': draft_message_id,
                'draft_url': draft_url,
                'to': to,
                'subject': subject
            }

        except HttpError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'HttpError'
            }

    def create_reply_draft(
        self,
        email: Dict[str, Any],
        body: str
    ) -> Dict[str, Any]:
        """
        Convenience method to create a reply draft to an email.

        Args:
            email: Email dict from search_email() or get_email()
            body: Reply body text

        Returns:
            Draft creation result
        """
        subject = email.get('subject', '')
        if not subject.lower().startswith('re:'):
            subject = f"Re: {subject}"

        return self.create_draft(
            to=email.get('sender_email', ''),
            subject=subject,
            body=body,
            thread_id=email.get('thread_id'),
            reply_to_message_id=email.get('message_id')
        )

    # ==================
    # LABEL MANAGEMENT
    # ==================

    def get_labels(self) -> List[Dict[str, str]]:
        """Get all Gmail labels."""
        self._ensure_authenticated()

        try:
            results = self.service.users().labels().list(userId='me').execute()
            return results.get('labels', [])
        except HttpError as e:
            raise GmailClientError(f"Failed to get labels: {e}")

    def get_label_id(self, label_name: str) -> Optional[str]:
        """Get label ID by name."""
        labels = self.get_labels()
        for label in labels:
            if label['name'].lower() == label_name.lower():
                return label['id']
        return None

    def search_by_label(
        self,
        label_name: str,
        max_results: int = 10,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Search for emails with a specific label.

        Args:
            label_name: Label name (e.g., "MCP")
            max_results: Maximum results
            days_back: How many days back

        Returns:
            List of email dicts
        """
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
        query = f'label:{label_name} after:{after_date}'

        return self.search_emails(query, search_type="keyword", max_results=max_results)


# ==================
# TESTING
# ==================

def test_gmail_client():
    """Test the Gmail client."""
    print("Testing Gmail Client...")
    print("=" * 60)

    if not GOOGLE_API_AVAILABLE:
        print("ERROR: Google API packages not installed.")
        print("Run: pip install google-auth google-auth-oauthlib google-api-python-client")
        return

    try:
        client = GmailClient()
        print("Authenticating...")
        client.authenticate()
        print("Authentication successful!")
        print()

        # Test search
        print("Testing email search...")
        email = client.search_email("test", search_type="keyword", max_results=1)
        if email:
            print(f"  Found: {email['subject']}")
            print(f"  From: {email['sender_email']}")
        else:
            print("  No emails found")
        print()

        # Test labels
        print("Getting labels...")
        labels = client.get_labels()
        print(f"  Found {len(labels)} labels")

        print()
        print("Gmail client test complete!")

    except GmailClientError as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    test_gmail_client()
