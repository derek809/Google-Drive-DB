"""
Google Sheets Client - Service Account Authentication
Provides CRUD operations for Google Sheets integration with MCP server.

Usage:
    from sheets_client import GoogleSheetsClient

    with GoogleSheetsClient() as client:
        data = client.read_range('spreadsheet_id', 'Sheet1!A1:D10')
        client.append_rows('spreadsheet_id', 'Sheet1!A:D', [['new', 'row', 'data']])
"""
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError  # ← This line is probably missing
from google.oauth2 import service_account
import json
import os
from typing import Dict, List, Optional, Any

# Google API imports
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class SheetsClientError(Exception):
    """Custom exception for Sheets client errors."""
    pass


class GoogleSheetsClient:
    """
    Google Sheets API wrapper with service account authentication.

    Usage:
        client = GoogleSheetsClient('/path/to/service_account.json')
        # Or use context manager:
        with GoogleSheetsClient() as client:
            data = client.read_range('spreadsheet_id', 'Sheet1!A1:D10')
    """

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    def __init__(self, credentials_path: str = None):
        """
        Initialize the Sheets client with service account credentials.

        Args:
            credentials_path: Path to service account JSON file.
                             If None, uses GOOGLE_SERVICE_ACCOUNT_PATH from config.
        """
        if not GOOGLE_API_AVAILABLE:
            raise SheetsClientError(
                "Google API packages not installed. Run:\n"
                "pip install google-auth google-api-python-client"
            )

        self.credentials_path = credentials_path
        self.service = None
        self._credentials = None

    def connect(self):
        """Establish connection to Google Sheets API."""
        if self.credentials_path is None:
            # Try to load from config
            try:
                from config import GOOGLE_SERVICE_ACCOUNT_PATH
                self.credentials_path = GOOGLE_SERVICE_ACCOUNT_PATH
            except ImportError:
                raise SheetsClientError(
                    "No credentials path provided and GOOGLE_SERVICE_ACCOUNT_PATH "
                    "not found in config.py"
                )

        if not os.path.exists(self.credentials_path):
            raise SheetsClientError(
                f"Service account file not found: {self.credentials_path}\n"
                "Please download your service account JSON from Google Cloud Console."
            )

        try:
            self._credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            self.service = build('sheets', 'v4', credentials=self._credentials)
        except Exception as e:
            raise SheetsClientError(f"Failed to authenticate: {str(e)}")

    def close(self):
        """Close the service connection."""
        self.service = None
        self._credentials = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def _ensure_connected(self):
        """Ensure service is connected."""
        if self.service is None:
            self.connect()

    # ==================
    # CORE OPERATIONS
    # ==================

    def read_range(
        self,
        spreadsheet_id: str,
        range_notation: str,
        value_render_option: str = "FORMATTED_VALUE"
    ) -> Dict[str, Any]:
        """
        Read values from a spreadsheet range.

        Args:
            spreadsheet_id: The ID of the spreadsheet (from URL)
            range_notation: A1 notation (e.g., 'Sheet1!A1:D10')
            value_render_option: How values are rendered
                - FORMATTED_VALUE: Values as they appear in the UI
                - UNFORMATTED_VALUE: Raw values without formatting
                - FORMULA: Formulas instead of calculated values

        Returns:
            Dict with 'values' (2D array), 'range', and metadata
        """
        self._ensure_connected()

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_notation,
                valueRenderOption=value_render_option
            ).execute()

            return {
                "success": True,
                "range": result.get('range', range_notation),
                "values": result.get('values', []),
                "rows_count": len(result.get('values', [])),
                "major_dimension": result.get('majorDimension', 'ROWS')
            }

        except HttpError as e:
            return self._handle_http_error(e, "read_range")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def write_range(
        self,
        spreadsheet_id: str,
        range_notation: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED"
    ) -> Dict[str, Any]:
        """
        Write values to a spreadsheet range.

        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_notation: A1 notation for where to write
            values: 2D array of values [[row1], [row2], ...]
            value_input_option: How input is interpreted
                - RAW: Values are stored as-is
                - USER_ENTERED: Parsed as if typed in UI (supports formulas)

        Returns:
            Dict with update results
        """
        self._ensure_connected()

        try:
            body = {'values': values}

            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_notation,
                valueInputOption=value_input_option,
                body=body
            ).execute()

            return {
                "success": True,
                "updated_range": result.get('updatedRange'),
                "updated_rows": result.get('updatedRows', 0),
                "updated_columns": result.get('updatedColumns', 0),
                "updated_cells": result.get('updatedCells', 0)
            }

        except HttpError as e:
            return self._handle_http_error(e, "write_range")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def append_rows(
        self,
        spreadsheet_id: str,
        range_notation: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED",
        insert_data_option: str = "INSERT_ROWS"
    ) -> Dict[str, Any]:
        """
        Append rows to the end of a table.

        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_notation: Table range to append to (e.g., 'Sheet1!A:D')
            values: 2D array of rows to append
            value_input_option: RAW or USER_ENTERED
            insert_data_option: INSERT_ROWS or OVERWRITE

        Returns:
            Dict with append results including where data was placed
        """
        self._ensure_connected()

        try:
            body = {'values': values}

            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_notation,
                valueInputOption=value_input_option,
                insertDataOption=insert_data_option,
                body=body
            ).execute()

            updates = result.get('updates', {})

            return {
                "success": True,
                "spreadsheet_id": result.get('spreadsheetId'),
                "table_range": result.get('tableRange'),
                "updated_range": updates.get('updatedRange'),
                "updated_rows": updates.get('updatedRows', 0),
                "updated_columns": updates.get('updatedColumns', 0),
                "updated_cells": updates.get('updatedCells', 0)
            }

        except HttpError as e:
            return self._handle_http_error(e, "append_rows")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def search(
        self,
        spreadsheet_id: str,
        range_notation: str,
        query: str,
        column_index: Optional[int] = None,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """
        Search for values in a spreadsheet range.

        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_notation: Range to search within
            query: Text to search for (case-insensitive)
            column_index: Optional column to limit search to (0-indexed)
            max_results: Maximum number of results

        Returns:
            Dict with matching rows and their row numbers
        """
        self._ensure_connected()

        try:
            # First read the data
            read_result = self.read_range(spreadsheet_id, range_notation)

            if not read_result.get('success'):
                return read_result

            values = read_result.get('values', [])
            query_lower = query.lower()
            matches = []

            for row_idx, row in enumerate(values):
                # Determine which cells to search
                if column_index is not None:
                    cells_to_search = [row[column_index]] if column_index < len(row) else []
                else:
                    cells_to_search = row

                # Check for match
                for cell in cells_to_search:
                    if query_lower in str(cell).lower():
                        matches.append({
                            "row_number": row_idx + 1,  # 1-indexed for Sheets
                            "row_index": row_idx,       # 0-indexed
                            "values": row
                        })
                        break

                if len(matches) >= max_results:
                    break

            return {
                "success": True,
                "query": query,
                "total_rows_searched": len(values),
                "matches_found": len(matches),
                "matches": matches,
                "truncated": len(matches) >= max_results
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def get_metadata(self, spreadsheet_id: str) -> Dict[str, Any]:
        """
        Get spreadsheet metadata including sheet names and properties.

        Args:
            spreadsheet_id: The ID of the spreadsheet

        Returns:
            Dict with spreadsheet title, sheets, and properties
        """
        self._ensure_connected()

        try:
            result = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="spreadsheetId,properties.title,sheets.properties"
            ).execute()

            sheets = []
            for sheet in result.get('sheets', []):
                props = sheet.get('properties', {})
                grid_props = props.get('gridProperties', {})
                sheets.append({
                    "sheet_id": props.get('sheetId'),
                    "title": props.get('title'),
                    "index": props.get('index'),
                    "row_count": grid_props.get('rowCount'),
                    "column_count": grid_props.get('columnCount'),
                    "frozen_rows": grid_props.get('frozenRowCount', 0),
                    "frozen_columns": grid_props.get('frozenColumnCount', 0)
                })

            return {
                "success": True,
                "spreadsheet_id": result.get('spreadsheetId'),
                "title": result.get('properties', {}).get('title'),
                "sheet_count": len(sheets),
                "sheets": sheets
            }

        except HttpError as e:
            return self._handle_http_error(e, "get_metadata")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    # ==================
    # BATCH OPERATIONS
    # ==================

    def batch_get(
        self,
        spreadsheet_id: str,
        ranges: List[str],
        value_render_option: str = "FORMATTED_VALUE"
    ) -> Dict[str, Any]:
        """
        Read multiple ranges in a single API call.

        Args:
            spreadsheet_id: The ID of the spreadsheet
            ranges: List of A1 notation ranges
            value_render_option: How values are rendered

        Returns:
            Dict with value ranges
        """
        self._ensure_connected()

        try:
            result = self.service.spreadsheets().values().batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=ranges,
                valueRenderOption=value_render_option
            ).execute()

            value_ranges = []
            for vr in result.get('valueRanges', []):
                value_ranges.append({
                    "range": vr.get('range'),
                    "values": vr.get('values', []),
                    "rows_count": len(vr.get('values', []))
                })

            return {
                "success": True,
                "spreadsheet_id": result.get('spreadsheetId'),
                "value_ranges": value_ranges
            }

        except HttpError as e:
            return self._handle_http_error(e, "batch_get")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def batch_update(
        self,
        spreadsheet_id: str,
        data: List[Dict[str, Any]],
        value_input_option: str = "USER_ENTERED"
    ) -> Dict[str, Any]:
        """
        Write to multiple ranges in a single API call.

        Args:
            spreadsheet_id: The ID of the spreadsheet
            data: List of dicts with 'range' and 'values' keys
            value_input_option: RAW or USER_ENTERED

        Returns:
            Dict with update results
        """
        self._ensure_connected()

        try:
            body = {
                'valueInputOption': value_input_option,
                'data': data
            }

            result = self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()

            return {
                "success": True,
                "spreadsheet_id": result.get('spreadsheetId'),
                "total_updated_cells": result.get('totalUpdatedCells', 0),
                "total_updated_rows": result.get('totalUpdatedRows', 0),
                "total_updated_columns": result.get('totalUpdatedColumns', 0),
                "total_updated_sheets": result.get('totalUpdatedSheets', 0),
                "responses": result.get('responses', [])
            }

        except HttpError as e:
            return self._handle_http_error(e, "batch_update")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    # ==================
    # SPREADSHEET CREATION
    # ==================

    def create_spreadsheet(
        self,
        title: str,
        sheet_data: Optional[List[List[Any]]] = None,
        sheet_name: str = "Sheet1"
    ) -> Dict[str, Any]:
        """
        Create a new Google Spreadsheet with optional initial data.

        Args:
            title: Title for the new spreadsheet
            sheet_data: Optional 2D array of initial data (first row = headers)
            sheet_name: Name for the first sheet tab

        Returns:
            Dict with spreadsheet_id, url, and success status
        """
        self._ensure_connected()

        try:
            body = {
                "properties": {"title": title},
                "sheets": [
                    {
                        "properties": {
                            "title": sheet_name,
                            "gridProperties": {
                                "rowCount": max(100, len(sheet_data) + 10) if sheet_data else 100,
                                "columnCount": max(26, len(sheet_data[0]) + 2) if sheet_data and sheet_data[0] else 26,
                            },
                        }
                    }
                ],
            }

            result = self.service.spreadsheets().create(body=body).execute()
            spreadsheet_id = result.get("spreadsheetId")
            url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

            # Write initial data if provided
            if sheet_data and spreadsheet_id:
                self.write_range(
                    spreadsheet_id,
                    f"{sheet_name}!A1",
                    sheet_data,
                )

            return {
                "success": True,
                "spreadsheet_id": spreadsheet_id,
                "url": url,
                "title": title,
                "sheet_name": sheet_name,
                "rows_written": len(sheet_data) if sheet_data else 0,
            }

        except HttpError as e:
            return self._handle_http_error(e, "create_spreadsheet")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }

    # ==================
    # TODO MANAGEMENT (Google Sheets as source of truth)
    # ==================

    def get_todos(
        self,
        spreadsheet_id: str,
        user_id: int,
        sheet_name: str = "todos_active"
    ) -> List[Dict[str, Any]]:
        """
        Get active todos for a user from Sheets (queried fresh every time).

        Args:
            spreadsheet_id: The spreadsheet ID
            user_id: Telegram user ID to filter by
            sheet_name: Tab name for active todos

        Returns:
            List of todo dicts with id, user_id, title, created_at, priority
        """
        result = self.read_range(spreadsheet_id, f"{sheet_name}!A:E")

        if not result.get('success') or not result.get('values'):
            return []

        rows = result['values']
        # Skip header row
        if rows and rows[0] and str(rows[0][0]).lower() == 'id':
            rows = rows[1:]

        todos = []
        for i, row in enumerate(rows):
            if len(row) < 3:
                continue
            row_user_id = str(row[1]).strip()
            if str(user_id) == row_user_id:
                todos.append({
                    'id': row[0],
                    'user_id': int(row[1]),
                    'title': row[2],
                    'created_at': row[3] if len(row) > 3 else '',
                    'priority': row[4] if len(row) > 4 else 'medium',
                    'sheet_row': i + 2  # 1-indexed + header
                })

        return todos

    def add_todo(
        self,
        spreadsheet_id: str,
        user_id: int,
        title: str,
        priority: str = 'medium',
        sheet_name: str = "todos_active"
    ) -> Dict[str, Any]:
        """
        Add a new todo to the active sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            user_id: Telegram user ID
            title: Task title
            priority: 'high', 'medium', or 'low'
            sheet_name: Tab name for active todos

        Returns:
            Dict with success status and todo_id
        """
        import uuid
        from datetime import datetime

        todo_id = str(uuid.uuid4())[:8]
        created_at = datetime.now().isoformat()

        result = self.append_rows(
            spreadsheet_id,
            f"{sheet_name}!A:E",
            [[todo_id, str(user_id), title, created_at, priority]]
        )

        if result.get('success'):
            return {
                'success': True,
                'todo_id': todo_id,
                'title': title,
                'priority': priority
            }
        return {'success': False, 'error': result.get('error', 'Failed to add todo')}

    def find_todo(
        self,
        spreadsheet_id: str,
        user_id: int,
        title: str,
        sheet_name: str = "todos_active"
    ) -> Optional[Dict[str, Any]]:
        """
        Check for duplicate todo by title (case-insensitive).

        Returns:
            Matching todo dict if found, None otherwise
        """
        todos = self.get_todos(spreadsheet_id, user_id, sheet_name)
        title_lower = title.lower().strip()

        for todo in todos:
            if todo['title'].lower().strip() == title_lower:
                return todo
        return None

    def complete_todo(
        self,
        spreadsheet_id: str,
        todo_id: str,
        active_sheet: str = "todos_active",
        history_sheet: str = "todos_history"
    ) -> Dict[str, Any]:
        """
        Complete a todo: copy to history sheet, delete from active sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            todo_id: The todo's UUID
            active_sheet: Tab name for active todos
            history_sheet: Tab name for completed todos

        Returns:
            Dict with success status and completed todo info
        """
        from datetime import datetime

        # Find the todo in active sheet
        result = self.read_range(spreadsheet_id, f"{active_sheet}!A:E")
        if not result.get('success') or not result.get('values'):
            return {'success': False, 'error': 'Could not read active todos'}

        rows = result['values']
        target_row = None
        target_row_index = None

        for i, row in enumerate(rows):
            if row and str(row[0]).strip() == str(todo_id).strip():
                target_row = row
                target_row_index = i
                break

        if target_row is None:
            return {'success': False, 'error': f'Todo {todo_id} not found'}

        title = target_row[2] if len(target_row) > 2 else ''
        completed_at = datetime.now().isoformat()

        # Append to history
        history_result = self.append_rows(
            spreadsheet_id,
            f"{history_sheet}!A:E",
            [[todo_id, target_row[1] if len(target_row) > 1 else '',
              title, completed_at, todo_id]]
        )

        if not history_result.get('success'):
            return {'success': False, 'error': 'Failed to write to history'}

        # Delete from active sheet
        delete_result = self.delete_row(spreadsheet_id, active_sheet, target_row_index)

        if not delete_result.get('success'):
            return {'success': False, 'error': 'Moved to history but failed to remove from active'}

        return {
            'success': True,
            'todo_id': todo_id,
            'title': title,
            'completed_at': completed_at
        }

    def get_todo_by_id(
        self,
        spreadsheet_id: str,
        todo_id: str,
        sheet_name: str = "todos_active"
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single todo by its ID.

        Returns:
            Todo dict if found, None otherwise
        """
        result = self.read_range(spreadsheet_id, f"{sheet_name}!A:E")
        if not result.get('success') or not result.get('values'):
            return None

        for i, row in enumerate(result['values']):
            if row and str(row[0]).strip() == str(todo_id).strip():
                return {
                    'id': row[0],
                    'user_id': int(row[1]) if len(row) > 1 else 0,
                    'title': row[2] if len(row) > 2 else '',
                    'created_at': row[3] if len(row) > 3 else '',
                    'priority': row[4] if len(row) > 4 else 'medium',
                    'sheet_row': i + 1
                }
        return None

    def delete_row(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        row_index: int
    ) -> Dict[str, Any]:
        """
        Delete a row from a sheet by index (0-based).

        Uses the Sheets batchUpdate API to delete a specific row.

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: The sheet tab name
            row_index: 0-based row index to delete

        Returns:
            Dict with success status
        """
        self._ensure_connected()

        try:
            # Get sheet ID from sheet name
            metadata = self.get_metadata(spreadsheet_id)
            if not metadata.get('success'):
                return {'success': False, 'error': 'Could not get sheet metadata'}

            sheet_id = None
            for sheet in metadata.get('sheets', []):
                if sheet.get('title') == sheet_name:
                    sheet_id = sheet.get('sheet_id')
                    break

            if sheet_id is None:
                return {'success': False, 'error': f'Sheet "{sheet_name}" not found'}

            request = {
                'requests': [{
                    'deleteDimension': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'ROWS',
                            'startIndex': row_index,
                            'endIndex': row_index + 1
                        }
                    }
                }]
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=request
            ).execute()

            return {'success': True}

        except HttpError as e:
            return self._handle_http_error(e, "delete_row")
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================
    # ERROR HANDLING
    # ==================

    def _handle_http_error(self, error: HttpError, operation: str) -> Dict[str, Any]:
        """Handle Google API HTTP errors with helpful messages."""
        try:
            error_details = json.loads(error.content.decode('utf-8')).get('error', {})
        except:
            error_details = {}

        status_code = error.resp.status

        error_messages = {
            400: "Bad request - check your range notation and parameters",
            401: "Authentication failed - check service account credentials",
            403: "Permission denied - ensure the spreadsheet is shared with the service account email",
            404: "Spreadsheet not found - verify the spreadsheet ID",
            429: "Rate limit exceeded - too many requests, try again later",
            500: "Google Sheets server error - try again later"
        }

        return {
            "success": False,
            "error": error_messages.get(status_code, f"HTTP {status_code} error"),
            "error_type": "HttpError",
            "status_code": status_code,
            "operation": operation,
            "details": error_details.get('message', str(error))
        }


# ==================
# TESTING
# ==================

def test_sheets_client():
    """Test the Sheets client (requires valid credentials and test spreadsheet)."""
    print("Testing Google Sheets Client...")
    print("=" * 60)

    if not GOOGLE_API_AVAILABLE:
        print("ERROR: Google API packages not installed.")
        print("Run: pip install google-auth google-api-python-client")
        return

    try:
        from config import GOOGLE_SERVICE_ACCOUNT_PATH
        print(f"Credentials path: {GOOGLE_SERVICE_ACCOUNT_PATH}")
    except ImportError:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_PATH not found in config.py")
        return

    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_PATH):
        print(f"ERROR: Service account file not found at: {GOOGLE_SERVICE_ACCOUNT_PATH}")
        print("\nTo set up Google Sheets integration:")
        print("1. Go to console.cloud.google.com")
        print("2. Create/select a project")
        print("3. Enable Google Sheets API")
        print("4. Go to IAM & Admin > Service Accounts")
        print("5. Create a service account and download the JSON key")
        print("6. Place the JSON file at the path above")
        return

    print("\nService account file found. Testing connection...")

    try:
        with GoogleSheetsClient() as client:
            print("Connection successful!")
            print("\nTo test with a spreadsheet:")
            print("1. Create a test Google Sheet")
            print("2. Share it with the service account email (found in your JSON file)")
            print("3. Run: client.get_metadata('your-spreadsheet-id')")
    except SheetsClientError as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    test_sheets_client()
