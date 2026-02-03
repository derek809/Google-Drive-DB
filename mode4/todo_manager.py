"""
Todo Manager Capability for Mode 4
SQLite-based task tracking via Telegram.

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

    Uses mode4.db for persistent storage.
    """

    def __init__(self):
        """Initialize todo manager."""
        self._db = None

    def _get_db(self):
        """Lazy load database manager."""
        if self._db is None:
            from db_manager import DatabaseManager
            self._db = DatabaseManager()
        return self._db

    # ==================
    # TASK OPERATIONS
    # ==================

    def add_task(
        self,
        title: str,
        priority: str = 'medium',
        deadline: datetime = None,
        notes: str = None
    ) -> int:
        """
        Add a new task.

        Args:
            title: Task description
            priority: 'high', 'medium', or 'low'
            deadline: Optional deadline datetime
            notes: Optional notes

        Returns:
            Task ID
        """
        db = self._get_db()
        task_id = db.add_task(
            title=title,
            priority=priority,
            deadline=deadline,
            notes=notes
        )
        logger.info(f"Added task {task_id}: {title[:50]}")
        return task_id

    def get_pending_tasks(self, limit: int = 20) -> List[Dict]:
        """
        Get pending tasks ordered by priority and deadline.

        Args:
            limit: Maximum tasks to return

        Returns:
            List of task dicts
        """
        db = self._get_db()
        return db.get_pending_tasks(limit)

    def get_all_tasks(self, include_completed: bool = False, limit: int = 50) -> List[Dict]:
        """Get all tasks optionally including completed."""
        db = self._get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if include_completed:
                cursor.execute("""
                    SELECT * FROM tasks
                    ORDER BY
                        CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                        CASE priority
                            WHEN 'high' THEN 1
                            WHEN 'medium' THEN 2
                            ELSE 3
                        END,
                        deadline ASC NULLS LAST
                    LIMIT ?
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT * FROM tasks
                    WHERE status = 'pending'
                    ORDER BY
                        CASE priority
                            WHEN 'high' THEN 1
                            WHEN 'medium' THEN 2
                            ELSE 3
                        END,
                        deadline ASC NULLS LAST
                    LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def complete_task(self, task_id: int) -> bool:
        """
        Mark a task as completed.

        Args:
            task_id: Task ID to complete

        Returns:
            True if successful
        """
        db = self._get_db()
        db.complete_task(task_id)
        logger.info(f"Completed task {task_id}")
        return True

    def delete_task(self, task_id: int) -> bool:
        """
        Delete a task.

        Args:
            task_id: Task ID to delete

        Returns:
            True if successful
        """
        db = self._get_db()
        db.delete_task(task_id)
        logger.info(f"Deleted task {task_id}")
        return True

    def update_priority(self, task_id: int, priority: str) -> bool:
        """Update task priority."""
        if priority not in ('high', 'medium', 'low'):
            raise TodoManagerError(f"Invalid priority: {priority}")

        db = self._get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks SET priority = ? WHERE id = ?
            """, (priority, task_id))
            conn.commit()
        return True

    def update_deadline(self, task_id: int, deadline: datetime) -> bool:
        """Update task deadline."""
        db = self._get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks SET deadline = ? WHERE id = ?
            """, (deadline, task_id))
            conn.commit()
        return True

    def get_task(self, task_id: int) -> Optional[Dict]:
        """Get a single task by ID."""
        db = self._get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

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
            if task['priority'] == 'high':
                priority_icon = "!"
            elif task['priority'] == 'low':
                priority_icon = "-"

            deadline_str = ""
            if task.get('deadline'):
                try:
                    dl = datetime.fromisoformat(task['deadline'])
                    deadline_str = f" @{dl.strftime('%m/%d')}"
                except:
                    pass

            lines.append(
                f"{status_icon} #{task['id']} {priority_icon}{task['title'][:40]}{deadline_str}"
            )

        lines.append("\nCommands: /task_done <id>, /task_priority <id> <level>")
        return "\n".join(lines)

    def _cmd_complete_task(self, args: str) -> str:
        """Handle /task_done command."""
        try:
            task_id = int(args.strip().replace('#', ''))
        except ValueError:
            return "Usage: /task_done <id>\nExample: /task_done 1"

        task = self.get_task(task_id)
        if not task:
            return f"Task #{task_id} not found."

        self.complete_task(task_id)
        return f"Completed: {task['title'][:50]}"

    def _cmd_delete_task(self, args: str) -> str:
        """Handle /task_delete command."""
        try:
            task_id = int(args.strip().replace('#', ''))
        except ValueError:
            return "Usage: /task_delete <id>\nExample: /task_delete 1"

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

        try:
            task_id = int(parts[0].replace('#', ''))
            priority = parts[1].lower()
        except ValueError:
            return "Invalid task ID."

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
            return "Usage: /task_deadline <id> <date>\nExample: /task_deadline 1 friday"

        try:
            task_id = int(parts[0].replace('#', ''))
        except ValueError:
            return "Invalid task ID."

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
            status = "[ ]" if task['status'] == 'pending' else "[x]"
            priority = ""
            if task['priority'] == 'high':
                priority = " <b>!</b>"

            deadline = ""
            if task.get('deadline'):
                try:
                    dl = datetime.fromisoformat(task['deadline'])
                    deadline = f" <i>@{dl.strftime('%m/%d')}</i>"
                except:
                    pass

            lines.append(f"{status} #{task['id']}{priority} {task['title'][:40]}{deadline}")

        return "\n".join(lines)

    def cleanup(self):
        """Cleanup resources."""
        if self._db:
            del self._db
            self._db = None


# ==================
# TESTING
# ==================

def test_todo_manager():
    """Test todo manager."""
    print("Testing Todo Manager...")
    print("=" * 60)

    todo = TodoManager()

    # Test add task
    print("\nAdding tasks...")
    id1 = todo.add_task("Send invoice to Jason", priority="high")
    id2 = todo.add_task("Review contract", deadline=datetime.now() + timedelta(days=2))
    id3 = todo.add_task("Call accountant", priority="low")
    print(f"  Added tasks: {id1}, {id2}, {id3}")

    # Test list tasks
    print("\nListing tasks...")
    tasks = todo.get_pending_tasks()
    for task in tasks:
        print(f"  #{task['id']} [{task['priority']}] {task['title']}")

    # Test command handling
    print("\nTesting commands...")
    print(todo.handle_command('/tasks', '', 123))

    # Test complete
    print(f"\nCompleting task #{id1}...")
    todo.complete_task(id1)
    tasks = todo.get_pending_tasks()
    print(f"  Remaining pending: {len(tasks)}")

    # Cleanup
    todo.delete_task(id1)
    todo.delete_task(id2)
    todo.delete_task(id3)
    todo.cleanup()

    print("\nTodo manager test complete!")


if __name__ == "__main__":
    test_todo_manager()
