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
