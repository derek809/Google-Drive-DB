# DEPRECATED: Replaced by OneNote (active/onenote_client.py)
# Retained for rollback safety. Do not add new features to this file.
"""
Google Docs Client - Service Account Authentication
Provides operations for the Master Doc (skill/idea storage).

Usage:
    from google_docs_client import GoogleDocsClient

    client = GoogleDocsClient()
    client.authenticate()

    # Append a skill entry
    client.append_to_storage(doc_id, formatted_entry)

    # Read inbox for processing
    inbox_content = client.read_inbox(doc_id)
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Google API imports
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class GoogleDocsClientError(Exception):
    """Custom exception for Google Docs client errors."""
    pass


class GoogleDocsClient:
    """
    Google Docs API wrapper for Master Doc operations.
    Uses service account authentication (same as sheets_client.py).

    The Master Doc has this structure:

    ## INBOX
    (Raw ideas dumped here for processing)

    ---

    ## STORAGE

    # slug_name_20250205_1430
    Type: Task
    Context: context_name
    Status: Pending
    Tags: tag1, tag2

    Body content here...

    Action Items:
    - Item 1
    - Item 2

    ---
    """

    SCOPES = [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive.readonly'  # For checking doc access
    ]

    def __init__(self, credentials_path: str = None):
        """
        Initialize the Docs client with service account credentials.

        Args:
            credentials_path: Path to service account JSON file.
                             If None, uses path from m1_config.py
        """
        if not GOOGLE_API_AVAILABLE:
            raise GoogleDocsClientError(
                "Google API packages not installed. Run:\n"
                "pip install google-auth google-api-python-client"
            )

        self.credentials_path = credentials_path
        self.service = None
        self._credentials = None

    def authenticate(self):
        """Establish connection to Google Docs API."""
        if self.credentials_path is None:
            try:
                from m1_config import SHEETS_CREDENTIALS_PATH
                self.credentials_path = SHEETS_CREDENTIALS_PATH
            except ImportError:
                raise GoogleDocsClientError(
                    "No credentials path provided and SHEETS_CREDENTIALS_PATH "
                    "not found in m1_config.py"
                )

        if not os.path.exists(self.credentials_path):
            raise GoogleDocsClientError(
                f"Service account file not found: {self.credentials_path}\n"
                "Please ensure the credentials file exists."
            )

        try:
            self._credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            self.service = build('docs', 'v1', credentials=self._credentials)
            logger.info("Google Docs API authenticated successfully")
        except Exception as e:
            raise GoogleDocsClientError(f"Failed to authenticate: {str(e)}")

    def _ensure_authenticated(self):
        """Ensure we have an authenticated service."""
        if self.service is None:
            self.authenticate()

    # ==================
    # CORE OPERATIONS
    # ==================

    def get_doc_content(self, doc_id: str) -> str:
        """
        Read the full document content as plain text.

        Args:
            doc_id: Google Doc ID

        Returns:
            Plain text content of the document
        """
        self._ensure_authenticated()

        try:
            document = self.service.documents().get(documentId=doc_id).execute()

            # Extract text from document body
            content = []
            for element in document.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    for text_run in element['paragraph'].get('elements', []):
                        if 'textRun' in text_run:
                            content.append(text_run['textRun'].get('content', ''))

            return ''.join(content)

        except HttpError as e:
            return self._handle_http_error(e, "get_doc_content")
        except Exception as e:
            logger.error(f"Error reading document: {e}")
            raise GoogleDocsClientError(f"Failed to read document: {str(e)}")

    def get_doc_info(self, doc_id: str) -> Dict[str, Any]:
        """
        Get document metadata to verify access.

        Args:
            doc_id: Google Doc ID

        Returns:
            Dict with document title and other metadata
        """
        self._ensure_authenticated()

        try:
            document = self.service.documents().get(documentId=doc_id).execute()
            return {
                "success": True,
                "document_id": document.get('documentId'),
                "title": document.get('title'),
                "revision_id": document.get('revisionId')
            }
        except HttpError as e:
            error_info = self._handle_http_error(e, "get_doc_info")
            return {"success": False, "error": error_info}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def append_to_storage(self, doc_id: str, formatted_entry: str) -> Dict[str, Any]:
        """
        Append a formatted skill entry to the ## STORAGE section.

        The entry should already be formatted with slug header and delimiter.
        This method finds the ## STORAGE section and appends after it.

        Args:
            doc_id: Google Doc ID
            formatted_entry: Pre-formatted entry (with # slug and ---)

        Returns:
            Dict with success status and position info
        """
        self._ensure_authenticated()

        try:
            # Get current document content to find insertion point
            document = self.service.documents().get(documentId=doc_id).execute()

            # Find the ## STORAGE section
            storage_index = self._find_storage_section(document)

            if storage_index is None:
                # Create ## STORAGE section at end of document
                end_index = self._get_document_end_index(document)
                requests = [
                    {
                        'insertText': {
                            'location': {'index': end_index},
                            'text': '\n\n## STORAGE\n\n'
                        }
                    }
                ]
                self.service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()

                # Re-fetch document to get updated indices
                document = self.service.documents().get(documentId=doc_id).execute()
                storage_index = self._find_storage_section(document)

            # Find the insertion point (right after ## STORAGE heading)
            insert_index = self._find_insert_position_after_storage(document, storage_index)

            # Ensure entry starts with newline and ends with delimiter
            entry_text = formatted_entry
            if not entry_text.startswith('\n'):
                entry_text = '\n' + entry_text
            if not entry_text.endswith('\n---\n'):
                entry_text = entry_text.rstrip() + '\n\n---\n'

            # Insert the entry
            requests = [
                {
                    'insertText': {
                        'location': {'index': insert_index},
                        'text': entry_text
                    }
                }
            ]

            result = self.service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            logger.info(f"Appended skill to document {doc_id}")

            return {
                "success": True,
                "document_id": doc_id,
                "insert_index": insert_index,
                "revision_id": result.get('writeControl', {}).get('requiredRevisionId')
            }

        except HttpError as e:
            return {"success": False, "error": self._handle_http_error(e, "append_to_storage")}
        except Exception as e:
            logger.error(f"Error appending to storage: {e}")
            return {"success": False, "error": str(e)}

    def read_inbox(self, doc_id: str) -> Dict[str, Any]:
        """
        Read content from the ## INBOX section.

        Args:
            doc_id: Google Doc ID

        Returns:
            Dict with inbox content and metadata
        """
        self._ensure_authenticated()

        try:
            content = self.get_doc_content(doc_id)

            # Find ## INBOX section
            inbox_match = re.search(r'##\s*INBOX\s*\n(.*?)(?=\n##|\n---|\Z)',
                                    content, re.DOTALL | re.IGNORECASE)

            if inbox_match:
                inbox_content = inbox_match.group(1).strip()
                return {
                    "success": True,
                    "has_content": bool(inbox_content),
                    "content": inbox_content,
                    "start_pos": inbox_match.start(1),
                    "end_pos": inbox_match.end(1)
                }

            return {
                "success": True,
                "has_content": False,
                "content": "",
                "note": "No ## INBOX section found"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def clear_inbox(self, doc_id: str) -> Dict[str, Any]:
        """
        Clear the content of the ## INBOX section.

        Args:
            doc_id: Google Doc ID

        Returns:
            Dict with success status
        """
        self._ensure_authenticated()

        try:
            document = self.service.documents().get(documentId=doc_id).execute()

            # Find ## INBOX section boundaries
            inbox_range = self._find_inbox_content_range(document)

            if inbox_range is None:
                return {
                    "success": True,
                    "note": "No ## INBOX section found or already empty"
                }

            start_index, end_index = inbox_range

            if start_index >= end_index:
                return {
                    "success": True,
                    "note": "INBOX already empty"
                }

            # Delete the inbox content (keep the heading)
            requests = [
                {
                    'deleteContentRange': {
                        'range': {
                            'startIndex': start_index,
                            'endIndex': end_index
                        }
                    }
                }
            ]

            self.service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            logger.info(f"Cleared INBOX section in document {doc_id}")

            return {"success": True}

        except HttpError as e:
            return {"success": False, "error": self._handle_http_error(e, "clear_inbox")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def find_by_slug(self, doc_id: str, slug: str) -> Dict[str, Any]:
        """
        Find an entry by its slug in the document.

        Args:
            doc_id: Google Doc ID
            slug: The slug to search for (e.g., "idea_rr_onboarding_20250205_1430")

        Returns:
            Dict with entry content if found
        """
        self._ensure_authenticated()

        try:
            content = self.get_doc_content(doc_id)

            # Pattern: # slug_name\n...content...\n---
            pattern = rf'#\s*{re.escape(slug)}\s*\n(.*?)(?=\n#\s|\n---|\Z)'
            match = re.search(pattern, content, re.DOTALL)

            if match:
                entry_content = match.group(1).strip()

                # Parse the entry metadata
                parsed = self._parse_entry(entry_content)

                return {
                    "success": True,
                    "found": True,
                    "slug": slug,
                    "raw_content": entry_content,
                    "parsed": parsed
                }

            return {
                "success": True,
                "found": False,
                "slug": slug
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_status(self, doc_id: str, slug: str, new_status: str) -> Dict[str, Any]:
        """
        Update the Status field for an entry.

        Args:
            doc_id: Google Doc ID
            slug: The entry slug
            new_status: New status value (e.g., "Done", "In Progress")

        Returns:
            Dict with success status
        """
        self._ensure_authenticated()

        try:
            document = self.service.documents().get(documentId=doc_id).execute()

            # Find the status line for this slug
            status_range = self._find_status_range(document, slug)

            if status_range is None:
                return {
                    "success": False,
                    "error": f"Could not find Status field for slug: {slug}"
                }

            start_index, end_index = status_range

            # Replace the status value
            requests = [
                {
                    'deleteContentRange': {
                        'range': {
                            'startIndex': start_index,
                            'endIndex': end_index
                        }
                    }
                },
                {
                    'insertText': {
                        'location': {'index': start_index},
                        'text': f'Status: {new_status}'
                    }
                }
            ]

            self.service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            logger.info(f"Updated status for {slug} to {new_status}")

            return {
                "success": True,
                "slug": slug,
                "new_status": new_status
            }

        except HttpError as e:
            return {"success": False, "error": self._handle_http_error(e, "update_status")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_all_slugs(self, doc_id: str) -> Dict[str, Any]:
        """
        List all slugs in the document.

        Args:
            doc_id: Google Doc ID

        Returns:
            Dict with list of slugs and their basic info
        """
        self._ensure_authenticated()

        try:
            content = self.get_doc_content(doc_id)

            # Find all slugs (# some_slug_name_20250205_1430)
            slug_pattern = r'#\s*([a-z0-9_]+_\d{8}_\d{4})\s*\n'
            matches = re.findall(slug_pattern, content, re.IGNORECASE)

            slugs = []
            for slug in matches:
                # Get quick info for each
                entry_result = self.find_by_slug(doc_id, slug)
                if entry_result.get('found'):
                    parsed = entry_result.get('parsed', {})
                    slugs.append({
                        "slug": slug,
                        "type": parsed.get('type', 'Unknown'),
                        "status": parsed.get('status', 'Unknown'),
                        "title": parsed.get('title', slug)[:50]
                    })

            return {
                "success": True,
                "count": len(slugs),
                "slugs": slugs
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================
    # BRAINSTORM OPERATIONS
    # ==================

    def append_brainstorm(self, doc_id: str, idea_text: str) -> Dict[str, Any]:
        """
        Append a timestamped brainstorm entry to the ## BRAINSTORM section.

        Format: [YYYY-MM-DD HH:MM] idea_text

        Args:
            doc_id: Google Doc ID
            idea_text: The brainstorm idea text

        Returns:
            Dict with success status
        """
        self._ensure_authenticated()
        from datetime import datetime

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        entry_text = f"[{timestamp}] {idea_text}\n"

        try:
            document = self.service.documents().get(documentId=doc_id).execute()

            # Find or create ## BRAINSTORM section
            brainstorm_index = self._find_section(document, 'BRAINSTORM')

            if brainstorm_index is None:
                # Create ## BRAINSTORM section at end of document
                end_index = self._get_document_end_index(document)
                requests = [
                    {
                        'insertText': {
                            'location': {'index': end_index},
                            'text': '\n\n## BRAINSTORM\n\n'
                        }
                    }
                ]
                self.service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()

                # Re-fetch document
                document = self.service.documents().get(documentId=doc_id).execute()
                brainstorm_index = self._find_section(document, 'BRAINSTORM')

            # Find insertion point (after the ## BRAINSTORM heading)
            insert_index = self._find_insert_position_after_section(
                document, brainstorm_index
            )

            # Insert the entry
            requests = [
                {
                    'insertText': {
                        'location': {'index': insert_index},
                        'text': entry_text
                    }
                }
            ]

            self.service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            logger.info(f"Appended brainstorm to document {doc_id}: {idea_text[:50]}")

            return {
                "success": True,
                "document_id": doc_id,
                "entry": entry_text.strip()
            }

        except HttpError as e:
            return {"success": False, "error": self._handle_http_error(e, "append_brainstorm")}
        except Exception as e:
            logger.error(f"Error appending brainstorm: {e}")
            return {"success": False, "error": str(e)}

    def read_brainstorms(self, doc_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        Read recent brainstorm entries from the ## BRAINSTORM section.

        Args:
            doc_id: Google Doc ID
            limit: Maximum entries to return

        Returns:
            Dict with list of brainstorm entries
        """
        self._ensure_authenticated()

        try:
            content = self.get_doc_content(doc_id)

            # Find ## BRAINSTORM section
            brainstorm_match = re.search(
                r'##\s*BRAINSTORM\s*\n(.*?)(?=\n##|\Z)',
                content, re.DOTALL | re.IGNORECASE
            )

            if not brainstorm_match:
                return {
                    "success": True,
                    "entries": [],
                    "count": 0,
                    "note": "No ## BRAINSTORM section found"
                }

            brainstorm_content = brainstorm_match.group(1).strip()

            if not brainstorm_content:
                return {
                    "success": True,
                    "entries": [],
                    "count": 0
                }

            # Parse entries: [YYYY-MM-DD HH:MM] text
            entries = []
            for line in brainstorm_content.split('\n'):
                line = line.strip()
                if not line:
                    continue

                entry_match = re.match(
                    r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]\s*(.+)',
                    line
                )
                if entry_match:
                    entries.append({
                        'timestamp': entry_match.group(1),
                        'idea': entry_match.group(2)
                    })
                elif line:
                    # Non-timestamped line, include as-is
                    entries.append({
                        'timestamp': '',
                        'idea': line
                    })

            # Return most recent entries (last N)
            recent = entries[-limit:] if len(entries) > limit else entries

            return {
                "success": True,
                "entries": recent,
                "count": len(entries),
                "showing": len(recent)
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================
    # INTERNAL HELPERS
    # ==================

    def _find_section(self, document: Dict, section_name: str) -> Optional[int]:
        """Find the start index of a ## SECTION_NAME section."""
        body = document.get('body', {})

        for element in body.get('content', []):
            if 'paragraph' in element:
                text = ''
                for text_run in element['paragraph'].get('elements', []):
                    if 'textRun' in text_run:
                        text += text_run['textRun'].get('content', '')

                if re.match(rf'##\s*{re.escape(section_name)}', text, re.IGNORECASE):
                    return element.get('startIndex')

        return None

    def _find_insert_position_after_section(
        self, document: Dict, section_start: int
    ) -> int:
        """Find the position right after a section heading line."""
        body = document.get('body', {})

        found_section = False
        for element in body.get('content', []):
            start = element.get('startIndex', 0)

            if start >= section_start:
                found_section = True

            if found_section and 'paragraph' in element:
                return element.get('endIndex', start + 1)

        return self._get_document_end_index(document)

    def _get_document_end_index(self, document: Dict) -> int:
        """Get the index of the document end."""
        body = document.get('body', {})
        content = body.get('content', [])

        if content:
            last_element = content[-1]
            return last_element.get('endIndex', 1) - 1
        return 1

    def _find_storage_section(self, document: Dict) -> Optional[int]:
        """Find the start index of ## STORAGE section."""
        body = document.get('body', {})

        for element in body.get('content', []):
            if 'paragraph' in element:
                text = ''
                for text_run in element['paragraph'].get('elements', []):
                    if 'textRun' in text_run:
                        text += text_run['textRun'].get('content', '')

                if re.match(r'##\s*STORAGE', text, re.IGNORECASE):
                    return element.get('startIndex')

        return None

    def _find_insert_position_after_storage(self, document: Dict, storage_start: int) -> int:
        """Find the position right after the ## STORAGE heading line."""
        body = document.get('body', {})

        found_storage = False
        for element in body.get('content', []):
            start = element.get('startIndex', 0)

            if start >= storage_start:
                found_storage = True

            if found_storage and 'paragraph' in element:
                # Return the end of this paragraph (the ## STORAGE line)
                return element.get('endIndex', start + 1)

        return self._get_document_end_index(document)

    def _find_inbox_content_range(self, document: Dict) -> Optional[tuple]:
        """Find the start and end indices of INBOX content (not heading)."""
        body = document.get('body', {})
        content = body.get('content', [])

        inbox_found = False
        content_start = None
        content_end = None

        for i, element in enumerate(content):
            if 'paragraph' in element:
                text = ''
                for text_run in element['paragraph'].get('elements', []):
                    if 'textRun' in text_run:
                        text += text_run['textRun'].get('content', '')

                if re.match(r'##\s*INBOX', text, re.IGNORECASE):
                    inbox_found = True
                    # Content starts after this heading
                    content_start = element.get('endIndex')
                    continue

                if inbox_found:
                    # Check if we hit another section or delimiter
                    if re.match(r'##\s', text) or text.strip() == '---':
                        content_end = element.get('startIndex')
                        break

        if content_start is not None:
            if content_end is None:
                content_end = self._get_document_end_index(document)
            return (content_start, content_end)

        return None

    def _find_status_range(self, document: Dict, slug: str) -> Optional[tuple]:
        """Find the range of the Status: line for a given slug."""
        body = document.get('body', {})

        slug_found = False
        for element in body.get('content', []):
            if 'paragraph' in element:
                text = ''
                for text_run in element['paragraph'].get('elements', []):
                    if 'textRun' in text_run:
                        text += text_run['textRun'].get('content', '')

                # Check if this is our slug
                if re.match(rf'#\s*{re.escape(slug)}', text, re.IGNORECASE):
                    slug_found = True
                    continue

                # Check if we hit another slug (entry boundary)
                if slug_found and re.match(r'#\s*[a-z0-9_]+_\d{8}_\d{4}', text, re.IGNORECASE):
                    break

                # Check for Status: line
                if slug_found and re.match(r'Status:', text, re.IGNORECASE):
                    start = element.get('startIndex')
                    end = element.get('endIndex') - 1  # Exclude newline
                    return (start, end)

        return None

    def _parse_entry(self, content: str) -> Dict[str, Any]:
        """Parse an entry's content into structured data."""
        result = {}

        # Extract Type
        type_match = re.search(r'Type:\s*(.+?)(?:\n|$)', content)
        if type_match:
            result['type'] = type_match.group(1).strip()

        # Extract Context
        context_match = re.search(r'Context:\s*(.+?)(?:\n|$)', content)
        if context_match:
            result['context'] = context_match.group(1).strip()

        # Extract Status
        status_match = re.search(r'Status:\s*(.+?)(?:\n|$)', content)
        if status_match:
            result['status'] = status_match.group(1).strip()

        # Extract Tags
        tags_match = re.search(r'Tags:\s*(.+?)(?:\n|$)', content)
        if tags_match:
            tags_str = tags_match.group(1).strip()
            result['tags'] = [t.strip() for t in tags_str.split(',')]

        # Extract Action Items
        action_items_match = re.search(r'Action Items:\s*\n((?:-\s*.+\n?)+)', content)
        if action_items_match:
            items = re.findall(r'-\s*(.+)', action_items_match.group(1))
            result['action_items'] = items

        # Extract body (everything after metadata, before Action Items)
        lines = content.split('\n')
        body_lines = []
        metadata_done = False

        for line in lines:
            if re.match(r'(Type|Context|Status|Tags):', line):
                continue
            if re.match(r'Action Items:', line):
                break
            if line.strip():
                metadata_done = True
            if metadata_done:
                body_lines.append(line)

        result['body'] = '\n'.join(body_lines).strip()

        # Generate title from first line of body or slug
        if result.get('body'):
            first_line = result['body'].split('\n')[0]
            result['title'] = first_line[:100]

        return result

    def _handle_http_error(self, error: HttpError, operation: str) -> str:
        """Handle Google API HTTP errors with helpful messages."""
        status_code = error.resp.status

        error_messages = {
            400: "Bad request - check document ID and parameters",
            401: "Authentication failed - check service account credentials",
            403: "Permission denied - ensure the document is shared with the service account email",
            404: "Document not found - verify the document ID",
            429: "Rate limit exceeded - too many requests, try again later",
            500: "Google Docs server error - try again later"
        }

        message = error_messages.get(status_code, f"HTTP {status_code} error")
        logger.error(f"{operation}: {message} - {error}")
        return message


# ==================
# TESTING
# ==================

def test_docs_client():
    """Test the Google Docs client."""
    print("Testing Google Docs Client...")
    print("=" * 60)

    if not GOOGLE_API_AVAILABLE:
        print("ERROR: Google API packages not installed.")
        print("Run: pip install google-auth google-api-python-client")
        return

    try:
        from m1_config import MASTER_DOC_ID, SHEETS_CREDENTIALS_PATH
        print(f"Master Doc ID: {MASTER_DOC_ID}")
        print(f"Credentials: {SHEETS_CREDENTIALS_PATH}")
    except ImportError as e:
        print(f"ERROR: Could not load config: {e}")
        return

    if not MASTER_DOC_ID:
        print("ERROR: MASTER_DOC_ID not configured in .env")
        print("Add: Docs_ID=your_document_id_here")
        return

    print("\nAttempting to connect...")

    try:
        client = GoogleDocsClient()
        client.authenticate()
        print("Authentication successful!")

        # Test get doc info
        print("\nGetting document info...")
        info = client.get_doc_info(MASTER_DOC_ID)
        if info.get('success'):
            print(f"  Title: {info.get('title')}")
            print(f"  ID: {info.get('document_id')}")
        else:
            print(f"  ERROR: {info.get('error')}")
            print("\nMake sure to share the document with the service account email!")
            return

        # Test reading content
        print("\nReading document content...")
        content = client.get_doc_content(MASTER_DOC_ID)
        print(f"  Content length: {len(content)} characters")
        print(f"  First 200 chars: {content[:200]}...")

        # Test listing slugs
        print("\nListing existing slugs...")
        slugs_result = client.list_all_slugs(MASTER_DOC_ID)
        if slugs_result.get('success'):
            print(f"  Found {slugs_result.get('count')} slugs")
            for slug_info in slugs_result.get('slugs', [])[:5]:
                print(f"    - {slug_info['slug']} ({slug_info['type']})")

        # Test reading inbox
        print("\nReading INBOX section...")
        inbox = client.read_inbox(MASTER_DOC_ID)
        if inbox.get('success'):
            if inbox.get('has_content'):
                print(f"  INBOX has content: {inbox.get('content')[:100]}...")
            else:
                print("  INBOX is empty")

        print("\n" + "=" * 60)
        print("Google Docs client test complete!")

    except GoogleDocsClientError as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    test_docs_client()
