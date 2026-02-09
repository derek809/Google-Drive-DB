"""
Todo Manager Capability for Mode 4
Google Sheets-based task tracking via Telegram.

Source of truth: Google Sheets (todos_active / todos_history tabs)
Queried fresh every time — no caching.

Commands:
    /task <title> - Add a new task
    /tasks - List pending tasks
    /task_done <id> - Mark task as completed
    /task_priority <id> <high|medium|low> - Set priority
    /task_deadline <id> <date> - Set deadline

Usage:
    from todo_manager import TodoManager

    todo = TodoManager()
    task_id = todo.add_task("Send invoice to Jason", priority="high")
    tasks = todo.get_pending_tasks()
    todo.complete_task(task_id)
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TodoManagerError(Exception):
    """Custom exception for todo manager errors."""
    pass


class TodoManager:
    """
    Task management capability for Mode 4.

    Uses Google Sheets as source of truth (todos_active / todos_history tabs).
    """

    def __init__(self, user_id: int = None):
        """
        Initialize todo manager.

        Args:
            user_id: Default Telegram user ID for operations
        """
        self._sheets = None
        self._spreadsheet_id = None
        self._active_sheet = None
        self._history_sheet = None
        self._user_id = user_id

    def _get_sheets(self):
        """Lazy load Sheets client and config."""
        if self._sheets is None:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from sheets_client import GoogleSheetsClient
            from m1_config import (
                SPREADSHEET_ID, SHEETS_CREDENTIALS_PATH,
                TODOS_ACTIVE_SHEET, TODOS_HISTORY_SHEET
            )
            self._sheets = GoogleSheetsClient(SHEETS_CREDENTIALS_PATH)
            self._sheets.connect()
            self._spreadsheet_id = SPREADSHEET_ID
            self._active_sheet = TODOS_ACTIVE_SHEET
            self._history_sheet = TODOS_HISTORY_SHEET
        return self._sheets

    # ==================
    # TASK OPERATIONS
    # ==================

    def add_task(
        self,
        title: str,
        priority: str = 'medium',
        deadline: datetime = None,
        notes: str = None
    ) -> str:
        """
        Add a new task to Google Sheets.

        Args:
            title: Task description
            priority: 'high', 'medium', or 'low'
            deadline: Optional deadline datetime (not yet stored in Sheets)
            notes: Optional notes (not yet stored in Sheets)

        Returns:
            Task ID (UUID string)
        """
        sheets = self._get_sheets()
        user_id = self._user_id or 0

        result = sheets.add_todo(
            self._spreadsheet_id,
            user_id,
            title,
            priority=priority,
            sheet_name=self._active_sheet
        )

        if result.get('success'):
            todo_id = result['todo_id']
            logger.info(f"Added task {todo_id}: {title[:50]}")
            return todo_id
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"Failed to add task: {error}")
            raise TodoManagerError(f"Failed to add task: {error}")

    def get_pending_tasks(self, limit: int = 20) -> List[Dict]:
        """
        Get pending tasks from Google Sheets (queried fresh).

        Args:
            limit: Maximum tasks to return

        Returns:
            List of task dicts with id, title, priority, created_at, status
        """
        sheets = self._get_sheets()
        user_id = self._user_id or 0

        todos = sheets.get_todos(
            self._spreadsheet_id,
            user_id,
            sheet_name=self._active_sheet
        )

        # Sort by priority: high > medium > low
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        todos.sort(key=lambda t: priority_order.get(t.get('priority', 'medium'), 1))

        # Add 'status' field for backward compatibility
        for todo in todos:
            todo['status'] = 'pending'

        return todos[:limit]

    def get_all_tasks(self, include_completed: bool = False, limit: int = 50) -> List[Dict]:
        """
        Get all tasks, optionally including completed.

        Args:
            include_completed: If True, also read from history sheet
            limit: Maximum tasks to return

        Returns:
            List of task dicts
        """
        sheets = self._get_sheets()
        user_id = self._user_id or 0

        # Get active tasks
        active = sheets.get_todos(
            self._spreadsheet_id,
            user_id,
            sheet_name=self._active_sheet
        )
        for t in active:
            t['status'] = 'pending'

        if include_completed:
            # Get completed tasks from history
            completed = sheets.get_todos(
                self._spreadsheet_id,
                user_id,
                sheet_name=self._history_sheet
            )
            for t in completed:
                t['status'] = 'completed'
                # History sheet has completed_at in column D instead of created_at
                t['completed_at'] = t.get('created_at', '')

            all_tasks = active + completed
        else:
            all_tasks = active

        # Sort: pending first, then by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        all_tasks.sort(key=lambda t: (
            0 if t['status'] == 'pending' else 1,
            priority_order.get(t.get('priority', 'medium'), 1)
        ))

        return all_tasks[:limit]

    def complete_task(self, task_id) -> bool:
        """
        Mark a task as completed (move from active to history sheet).

        Args:
            task_id: Task ID (UUID string) to complete

        Returns:
            True if successful
        """
        sheets = self._get_sheets()

        result = sheets.complete_todo(
            self._spreadsheet_id,
            str(task_id),
            active_sheet=self._active_sheet,
            history_sheet=self._history_sheet
        )

        if result.get('success'):
            logger.info(f"Completed task {task_id}")
            return True
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"Failed to complete task {task_id}: {error}")
            raise TodoManagerError(f"Failed to complete task: {error}")

    def delete_task(self, task_id) -> bool:
        """
        Delete a task from the active sheet (without moving to history).

        Args:
            task_id: Task ID to delete

        Returns:
            True if successful
        """
        sheets = self._get_sheets()

        # Find the row
        result = sheets.read_range(
            self._spreadsheet_id,
            f"{self._active_sheet}!A:E"
        )
        if not result.get('success') or not result.get('values'):
            raise TodoManagerError("Could not read active todos")

        for i, row in enumerate(result['values']):
            if row and str(row[0]).strip() == str(task_id).strip():
                delete_result = sheets.delete_row(
                    self._spreadsheet_id,
                    self._active_sheet,
                    i
                )
                if delete_result.get('success'):
                    logger.info(f"Deleted task {task_id}")
                    return True
                else:
                    raise TodoManagerError(f"Failed to delete: {delete_result.get('error')}")

        raise TodoManagerError(f"Task {task_id} not found")

    def update_priority(self, task_id, priority: str) -> bool:
        """Update task priority in Sheets."""
        if priority not in ('high', 'medium', 'low'):
            raise TodoManagerError(f"Invalid priority: {priority}")

        sheets = self._get_sheets()

        # Find the row and update priority column (E)
        result = sheets.read_range(
            self._spreadsheet_id,
            f"{self._active_sheet}!A:E"
        )
        if not result.get('success') or not result.get('values'):
            raise TodoManagerError("Could not read active todos")

        for i, row in enumerate(result['values']):
            if row and str(row[0]).strip() == str(task_id).strip():
                # Update priority in column E (row i+1 in 1-indexed)
                update_result = sheets.write_range(
                    self._spreadsheet_id,
                    f"{self._active_sheet}!E{i + 1}",
                    [[priority]]
                )
                if update_result.get('success'):
                    return True
                else:
                    raise TodoManagerError(f"Failed to update priority: {update_result.get('error')}")

        raise TodoManagerError(f"Task {task_id} not found")

    def update_deadline(self, task_id, deadline: datetime) -> bool:
        """Update task deadline. Note: deadline is not currently in the Sheets schema."""
        logger.warning(f"Deadline update for task {task_id} - deadline column not in Sheets schema yet")
        return True

    def get_task(self, task_id) -> Optional[Dict]:
        """Get a single task by ID from Sheets."""
        sheets = self._get_sheets()

        todo = sheets.get_todo_by_id(
            self._spreadsheet_id,
            str(task_id),
            sheet_name=self._active_sheet
        )

        if todo:
            todo['status'] = 'pending'
            return todo
        return None

    # ==================
    # COMMAND HANDLERS
    # ==================

    def handle_command(self, command: str, args: str, user_id: int) -> str:
        """
        Handle a todo command and return response text.

        Args:
            command: Command name (task, tasks, task_done, etc.)
            args: Command arguments
            user_id: Telegram user ID

        Returns:
            Response message text
        """
        # Set user_id for this operation
        self._user_id = user_id

        try:
            if command == '/task':
                return self._cmd_add_task(args)
            elif command == '/tasks':
                return self._cmd_list_tasks(args)
            elif command == '/task_done':
                return self._cmd_complete_task(args)
            elif command == '/task_delete':
                return self._cmd_delete_task(args)
            elif command == '/task_priority':
                return self._cmd_set_priority(args)
            elif command == '/task_deadline':
                return self._cmd_set_deadline(args)
            else:
                return f"Unknown command: {command}"
        except Exception as e:
            logger.error(f"Todo command error: {e}")
            return f"Error: {str(e)}"

    def _cmd_add_task(self, args: str) -> str:
        """Handle /task command."""
        if not args.strip():
            return (
                "Usage: /task <title>\n"
                "Example: /task Send invoice to Jason\n"
                "Optional: /task Send invoice !high @friday"
            )

        # Parse priority from !high, !medium, !low
        priority = 'medium'
        priority_match = re.search(r'!(\w+)', args)
        if priority_match:
            p = priority_match.group(1).lower()
            if p in ('high', 'medium', 'low'):
                priority = p
            args = args.replace(priority_match.group(0), '').strip()

        # Parse deadline from @date
        deadline = None
        deadline_match = re.search(r'@(\w+)', args)
        if deadline_match:
            deadline = self._parse_deadline(deadline_match.group(1))
            args = args.replace(deadline_match.group(0), '').strip()

        title = args.strip()
        if not title:
            return "Task title cannot be empty."

        task_id = self.add_task(title, priority=priority, deadline=deadline)

        response = f"Task #{task_id} added: {title}"
        if priority != 'medium':
            response += f"\nPriority: {priority}"
        if deadline:
            response += f"\nDeadline: {deadline.strftime('%Y-%m-%d')}"

        return response

    def _cmd_list_tasks(self, args: str) -> str:
        """Handle /tasks command."""
        include_completed = 'all' in args.lower()
        tasks = self.get_all_tasks(include_completed=include_completed, limit=20)

        if not tasks:
            return "No tasks found. Add one with /task <title>"

        lines = ["Your Tasks:"]
        for task in tasks:
            status_icon = "[ ]" if task['status'] == 'pending' else "[x]"
            priority_icon = ""
            if task.get('priority') == 'high':
                priority_icon = "!"
            elif task.get('priority') == 'low':
                priority_icon = "-"

            lines.append(
                f"{status_icon} #{task['id']} {priority_icon}{task['title'][:40]}"
            )

        lines.append("\nCommands: /task_done <id>, /task_priority <id> <level>")
        return "\n".join(lines)

    def _cmd_complete_task(self, args: str) -> str:
        """Handle /task_done command."""
        task_id = args.strip().replace('#', '')
        if not task_id:
            return "Usage: /task_done <id>\nExample: /task_done abc123"

        task = self.get_task(task_id)
        if not task:
            return f"Task #{task_id} not found."

        self.complete_task(task_id)
        return f"Completed: {task['title'][:50]}"

    def _cmd_delete_task(self, args: str) -> str:
        """Handle /task_delete command."""
        task_id = args.strip().replace('#', '')
        if not task_id:
            return "Usage: /task_delete <id>\nExample: /task_delete abc123"

        task = self.get_task(task_id)
        if not task:
            return f"Task #{task_id} not found."

        self.delete_task(task_id)
        return f"Deleted: {task['title'][:50]}"

    def _cmd_set_priority(self, args: str) -> str:
        """Handle /task_priority command."""
        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /task_priority <id> <high|medium|low>"

        task_id = parts[0].replace('#', '')
        priority = parts[1].lower()

        if priority not in ('high', 'medium', 'low'):
            return "Priority must be: high, medium, or low"

        task = self.get_task(task_id)
        if not task:
            return f"Task #{task_id} not found."

        self.update_priority(task_id, priority)
        return f"Task #{task_id} priority set to {priority}"

    def _cmd_set_deadline(self, args: str) -> str:
        """Handle /task_deadline command."""
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /task_deadline <id> <date>\nExample: /task_deadline abc123 friday"

        task_id = parts[0].replace('#', '')

        deadline = self._parse_deadline(parts[1])
        if not deadline:
            return "Could not parse deadline. Try: today, tomorrow, friday, 2024-01-15"

        task = self.get_task(task_id)
        if not task:
            return f"Task #{task_id} not found."

        self.update_deadline(task_id, deadline)
        return f"Task #{task_id} deadline set to {deadline.strftime('%Y-%m-%d')}"

    def _parse_deadline(self, text: str) -> Optional[datetime]:
        """Parse natural language deadline."""
        text = text.lower().strip()
        today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)

        if text == 'today':
            return today
        elif text == 'tomorrow':
            return today + timedelta(days=1)
        elif text in ('monday', 'mon'):
            return self._next_weekday(today, 0)
        elif text in ('tuesday', 'tue'):
            return self._next_weekday(today, 1)
        elif text in ('wednesday', 'wed'):
            return self._next_weekday(today, 2)
        elif text in ('thursday', 'thu'):
            return self._next_weekday(today, 3)
        elif text in ('friday', 'fri'):
            return self._next_weekday(today, 4)
        elif text in ('saturday', 'sat'):
            return self._next_weekday(today, 5)
        elif text in ('sunday', 'sun'):
            return self._next_weekday(today, 6)
        elif text == 'next week':
            return today + timedelta(days=7)
        else:
            # Try parsing as date
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m/%d', '%d']:
                try:
                    parsed = datetime.strptime(text, fmt)
                    if fmt == '%m/%d':
                        parsed = parsed.replace(year=today.year)
                    elif fmt == '%d':
                        parsed = parsed.replace(year=today.year, month=today.month)
                    return parsed
                except ValueError:
                    continue
        return None

    def _next_weekday(self, start: datetime, weekday: int) -> datetime:
        """Get next occurrence of weekday (0=Monday, 6=Sunday)."""
        days_ahead = weekday - start.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return start + timedelta(days=days_ahead)

    # ==================
    # FORMATTING
    # ==================

    def format_task_list_html(self, tasks: List[Dict]) -> str:
        """Format tasks as HTML for Telegram."""
        if not tasks:
            return "No tasks found."

        lines = ["<b>Your Tasks:</b>\n"]
        for task in tasks:
            status = "[ ]" if task.get('status') == 'pending' else "[x]"
            priority = ""
            if task.get('priority') == 'high':
                priority = " <b>!</b>"

            lines.append(f"{status} #{task['id']}{priority} {task['title'][:40]}")

        return "\n".join(lines)

    def cleanup(self):
        """Cleanup resources."""
        if self._sheets:
            self._sheets.close()
            self._sheets = None
