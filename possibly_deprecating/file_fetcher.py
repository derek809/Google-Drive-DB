# DEPRECATED: Replaced by hybrid fetcher (active/file_fetcher.py)
# Retained for rollback safety. Do not add new features to this file.
"""
File Fetcher Capability for Mode 4
Google Drive file delivery to Telegram.

Commands:
    /file <query> - Search and send file
    /files - List recent/quick-linked files
    /quicklink <name> <file_id> - Save quick link

Usage:
    from file_fetcher import FileFetcher

    fetcher = FileFetcher()
    results = fetcher.search_files("invoice jason")
    fetcher.send_file_to_telegram(file_id, chat_id)
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class FileFetcherError(Exception):
    """Custom exception for file fetcher errors."""
    pass


class FileFetcher:
    """
    Google Drive file fetcher capability for Mode 4.

    Searches Drive and delivers files via Telegram.
    Supports quick links for frequently accessed files.
    """

    def __init__(self):
        """Initialize file fetcher."""
        self._drive = None
        self._db = None
        self._telegram_bot = None

        # Supported file types for direct sending
        self.sendable_types = [
            'application/pdf',
            'image/jpeg',
            'image/png',
            'image/gif',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'text/csv'
        ]

        # Max file size for Telegram (50MB)
        self.max_file_size = 50 * 1024 * 1024

    def _get_drive(self):
        """Lazy load Google Drive client."""
        if self._drive is None:
            try:
                from googleapiclient.discovery import build
                from google.oauth2.credentials import Credentials
                from google.auth.transport.requests import Request
                import pickle

                # Load credentials
                creds = None
                token_path = Path(__file__).parent / 'token.pickle'
                creds_path = Path(__file__).parent / 'credentials.json'

                if token_path.exists():
                    with open(token_path, 'rb') as token:
                        creds = pickle.load(token)

                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        from google_auth_oauthlib.flow import InstalledAppFlow
                        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
                        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                        creds = flow.run_local_server(port=0)

                    with open(token_path, 'wb') as token:
                        pickle.dump(creds, token)

                self._drive = build('drive', 'v3', credentials=creds)

            except Exception as e:
                logger.error(f"Could not initialize Drive client: {e}")

        return self._drive

    def _get_db(self):
        """Lazy load database manager."""
        if self._db is None:
            from db_manager import DatabaseManager
            self._db = DatabaseManager()
        return self._db

    # ==================
    # DRIVE OPERATIONS
    # ==================

    def search_files(
        self,
        query: str,
        max_results: int = 10,
        file_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search Google Drive for files.

        Args:
            query: Search query
            max_results: Maximum results to return
            file_type: Filter by MIME type

        Returns:
            List of file metadata dicts
        """
        drive = self._get_drive()
        if not drive:
            return []

        # Build Drive query
        search_query = f"name contains '{query}' and trashed = false"
        if file_type:
            search_query += f" and mimeType = '{file_type}'"

        try:
            results = drive.files().list(
                q=search_query,
                pageSize=max_results,
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink, parents)"
            ).execute()

            files = results.get('files', [])
            return [
                {
                    'id': f['id'],
                    'name': f['name'],
                    'mime_type': f.get('mimeType', ''),
                    'size': int(f.get('size', 0)),
                    'modified': f.get('modifiedTime', ''),
                    'url': f.get('webViewLink', ''),
                    'parents': f.get('parents', [])
                }
                for f in files
            ]

        except Exception as e:
            logger.error(f"Drive search error: {e}")
            return []

    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by ID."""
        drive = self._get_drive()
        if not drive:
            return None

        try:
            file_meta = drive.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, modifiedTime, webViewLink"
            ).execute()

            return {
                'id': file_meta['id'],
                'name': file_meta['name'],
                'mime_type': file_meta.get('mimeType', ''),
                'size': int(file_meta.get('size', 0)),
                'modified': file_meta.get('modifiedTime', ''),
                'url': file_meta.get('webViewLink', '')
            }

        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return None

    def download_file(self, file_id: str, destination: str = None) -> Optional[str]:
        """
        Download file from Drive.

        Args:
            file_id: Google Drive file ID
            destination: Optional destination path

        Returns:
            Path to downloaded file or None
        """
        drive = self._get_drive()
        if not drive:
            return None

        try:
            # Get file info first
            file_meta = self.get_file_info(file_id)
            if not file_meta:
                return None

            # Check size
            if file_meta['size'] > self.max_file_size:
                logger.warning(f"File too large: {file_meta['size']} bytes")
                return None

            # Determine destination
            if not destination:
                import tempfile
                temp_dir = tempfile.mkdtemp()
                destination = os.path.join(temp_dir, file_meta['name'])

            # Download
            from googleapiclient.http import MediaIoBaseDownload
            import io

            request = drive.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            # Write to file
            with open(destination, 'wb') as f:
                f.write(fh.getvalue())

            return destination

        except Exception as e:
            logger.error(f"Download error: {e}")
            return None

    # ==================
    # QUICK LINKS
    # ==================

    def add_quick_link(self, name: str, file_id: str, user_id: int) -> bool:
        """
        Save a quick link for fast access.

        Args:
            name: Quick link name
            file_id: Google Drive file ID
            user_id: Telegram user ID

        Returns:
            True if saved
        """
        db = self._get_db()

        # Verify file exists
        file_info = self.get_file_info(file_id)
        if not file_info:
            return False

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO quick_links
                    (name, file_id, file_name, user_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (name.lower(), file_id, file_info['name'], user_id, datetime.now()))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving quick link: {e}")
            return False

    def get_quick_link(self, name: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Get a quick link by name."""
        db = self._get_db()

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM quick_links
                    WHERE name = ? AND user_id = ?
                """, (name.lower(), user_id))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting quick link: {e}")
            return None

    def list_quick_links(self, user_id: int) -> List[Dict[str, Any]]:
        """List all quick links for a user."""
        db = self._get_db()

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM quick_links
                    WHERE user_id = ?
                    ORDER BY name
                """, (user_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error listing quick links: {e}")
            return []

    def delete_quick_link(self, name: str, user_id: int) -> bool:
        """Delete a quick link."""
        db = self._get_db()

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM quick_links
                    WHERE name = ? AND user_id = ?
                """, (name.lower(), user_id))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting quick link: {e}")
            return False

    # ==================
    # COMMAND HANDLERS
    # ==================

    def handle_command(self, command: str, args: str, user_id: int) -> str:
        """
        Handle file command and return response text.

        Args:
            command: Command name (/file, /files, /quicklink)
            args: Command arguments
            user_id: Telegram user ID

        Returns:
            Response message text (or file path for sending)
        """
        try:
            if command == '/file':
                return self._cmd_search_file(args, user_id)
            elif command == '/files':
                return self._cmd_list_files(args, user_id)
            elif command == '/quicklink':
                return self._cmd_quick_link(args, user_id)
            elif command == '/getfile':
                return self._cmd_get_file(args, user_id)
            else:
                return f"Unknown command: {command}"
        except Exception as e:
            logger.error(f"File command error: {e}")
            return f"Error: {str(e)}"

    def _cmd_search_file(self, args: str, user_id: int) -> str:
        """Handle /file command."""
        if not args.strip():
            return (
                "File Search & Delivery\n\n"
                "Usage: /file <search query>\n"
                "Example: /file invoice jason 2024\n\n"
                "Or use a quick link: /file @mylink"
            )

        query = args.strip()

        # Check for quick link (@name)
        if query.startswith('@'):
            link_name = query[1:]
            link = self.get_quick_link(link_name, user_id)
            if link:
                file_info = self.get_file_info(link['file_id'])
                if file_info:
                    return (
                        f"FILE_SEND:{link['file_id']}\n"
                        f"Name: {file_info['name']}\n"
                        f"Size: {self._format_size(file_info['size'])}"
                    )
                return f"Quick link '{link_name}' file no longer exists."
            return f"Quick link '@{link_name}' not found."

        # Search Drive
        results = self.search_files(query, max_results=5)

        if not results:
            return f"No files found matching '{query}'."

        lines = [f"Found {len(results)} files:\n"]
        for i, f in enumerate(results, 1):
            size_str = self._format_size(f['size'])
            lines.append(f"{i}. {f['name']}")
            lines.append(f"   Size: {size_str} | ID: {f['id'][:12]}...")

        lines.append(f"\nTo get a file: /getfile <number or ID>")
        lines.append("To save quick link: /quicklink <name> <ID>")

        # Store search results in session for /getfile
        self._last_search = {user_id: results}

        return '\n'.join(lines)

    def _cmd_get_file(self, args: str, user_id: int) -> str:
        """Handle /getfile command."""
        if not args.strip():
            return "Usage: /getfile <number or file_id>"

        arg = args.strip()

        # Check if it's a number from recent search
        if arg.isdigit():
            num = int(arg)
            if hasattr(self, '_last_search') and user_id in self._last_search:
                results = self._last_search[user_id]
                if 1 <= num <= len(results):
                    file_info = results[num - 1]
                    return (
                        f"FILE_SEND:{file_info['id']}\n"
                        f"Name: {file_info['name']}\n"
                        f"Size: {self._format_size(file_info['size'])}"
                    )
            return f"No recent search result #{num}. Use /file to search first."

        # Treat as file ID
        file_info = self.get_file_info(arg)
        if file_info:
            return (
                f"FILE_SEND:{file_info['id']}\n"
                f"Name: {file_info['name']}\n"
                f"Size: {self._format_size(file_info['size'])}"
            )

        return f"File not found: {arg}"

    def _cmd_list_files(self, args: str, user_id: int) -> str:
        """Handle /files command."""
        links = self.list_quick_links(user_id)

        if not links:
            return (
                "No quick links saved.\n\n"
                "Quick links provide fast access to files.\n"
                "Usage: /quicklink <name> <file_id>\n"
                "Then: /file @name"
            )

        lines = ["Your Quick Links:\n"]
        for link in links:
            lines.append(f"  @{link['name']} - {link['file_name']}")

        lines.append(f"\nUse: /file @<name> to get a file")
        return '\n'.join(lines)

    def _cmd_quick_link(self, args: str, user_id: int) -> str:
        """Handle /quicklink command."""
        parts = args.strip().split()

        if len(parts) < 2:
            return (
                "Quick Link Management\n\n"
                "Create: /quicklink <name> <file_id>\n"
                "Delete: /quicklink delete <name>\n"
                "List: /files"
            )

        if parts[0].lower() == 'delete':
            if len(parts) < 2:
                return "Usage: /quicklink delete <name>"
            name = parts[1]
            if self.delete_quick_link(name, user_id):
                return f"Quick link '@{name}' deleted."
            return f"Quick link '@{name}' not found."

        name = parts[0]
        file_id = parts[1]

        if self.add_quick_link(name, file_id, user_id):
            return f"Quick link '@{name}' saved!"
        return f"Could not save quick link. File ID may be invalid."

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def cleanup(self):
        """Cleanup resources."""
        if self._drive:
            del self._drive
            self._drive = None
        if self._db:
            del self._db
            self._db = None


# ==================
# TESTING
# ==================

def test_file_fetcher():
    """Test file fetcher."""
    print("Testing File Fetcher...")
    print("=" * 60)

    fetcher = FileFetcher()

    # Test size formatting
    print("\nTesting size formatting...")
    test_sizes = [500, 5000, 5000000, 50000000]
    for size in test_sizes:
        print(f"  {size} bytes -> {fetcher._format_size(size)}")

    # Note: Actual testing requires Drive credentials
    print("\nTo test with Google Drive:")
    print("  1. Ensure credentials.json is in mode4/")
    print("  2. Run: fetcher.search_files('test')")

    fetcher.cleanup()
    print("\nFile fetcher test complete!")


if __name__ == "__main__":
    test_file_fetcher()
