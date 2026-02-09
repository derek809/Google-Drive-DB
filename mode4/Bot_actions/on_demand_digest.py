"""
On-Demand Digest for Mode 4
Generates a daily digest on user request via /digest command.

Unlike scheduled digests, this runs when the user asks for it,
which is better for systems that aren't always running (like an M1 laptop).

Usage:
    from on_demand_digest import OnDemandDigest

    digest = OnDemandDigest(gmail_client, todo_manager, claude_client)
    summary = await digest.generate_digest(user_id)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import html

logger = logging.getLogger(__name__)


class OnDemandDigest:
    """
    Generate on-demand digest summarizing:
    - MCP-labeled emails (Gmail label)
    - Overdue todos
    - Unsent drafts
    - Pending items from workspace

    Uses Claude Haiku for cost-effective summarization.
    """

    def __init__(
        self,
        gmail_client=None,
        todo_manager=None,
        claude_client=None,
        db_manager=None
    ):
        """
        Initialize digest generator.

        Args:
            gmail_client: GmailClient instance
            todo_manager: TodoManager instance
            claude_client: ClaudeClient instance (uses Haiku for summaries)
            db_manager: DatabaseManager instance
        """
        self.gmail = gmail_client
        self.todo = todo_manager
        self.claude = claude_client
        self.db = db_manager

    async def generate_digest(self, user_id: int = None) -> str:
        """
        Generate a comprehensive digest of actionable items.

        Args:
            user_id: Optional user ID for personalization

        Returns:
            Formatted digest string (HTML for Telegram)
        """
        logger.info("Generating on-demand digest...")

        # Gather data from all sources
        data = {
            'mcp_emails': await self._get_mcp_emails(),
            'overdue_todos': self._get_overdue_todos(),
            'pending_todos': self._get_pending_todos(),
            'unsent_drafts': await self._get_unsent_drafts(),
            'workspace_items': self._get_workspace_items(),
        }

        # Check if there's anything to report
        has_content = any([
            data['mcp_emails'],
            data['overdue_todos'],
            data['pending_todos'],
            data['unsent_drafts'],
            data['workspace_items']
        ])

        if not has_content:
            return self._generate_empty_digest()

        # Generate summary using Claude Haiku (or format directly if no Claude)
        if self.claude and self.claude.is_available():
            return await self._generate_ai_summary(data)
        else:
            return self._generate_formatted_digest(data)

    async def _get_mcp_emails(self) -> List[Dict]:
        """Get emails with MCP label from Gmail."""
        if not self.gmail:
            return []

        try:
            # Search for MCP-labeled emails from last 7 days
            emails = self.gmail.search_email(
                reference='label:MCP',
                search_type='label',
                max_results=20
            )

            if isinstance(emails, dict):
                # Single email returned
                emails = [emails] if emails else []

            # Filter to recent emails and extract key info
            recent_emails = []
            cutoff = datetime.now() - timedelta(days=7)

            for email in emails or []:
                # Calculate age
                received_str = email.get('received_at', email.get('date', ''))
                if received_str:
                    try:
                        received = datetime.fromisoformat(received_str.replace('Z', '+00:00'))
                        if received.replace(tzinfo=None) < cutoff:
                            continue
                        age_days = (datetime.now() - received.replace(tzinfo=None)).days
                    except:
                        age_days = 0
                else:
                    age_days = 0

                recent_emails.append({
                    'subject': email.get('subject', '(no subject)')[:60],
                    'sender': email.get('sender_name', email.get('sender_email', 'Unknown')),
                    'sender_email': email.get('sender_email', ''),
                    'age_days': age_days,
                    'thread_id': email.get('thread_id', ''),
                    'is_replied': email.get('is_replied', False)
                })

            return recent_emails

        except Exception as e:
            logger.error(f"Error fetching MCP emails: {e}")
            return []

    def _get_overdue_todos(self) -> List[Dict]:
        """Get overdue tasks from todo manager."""
        if not self.todo:
            # Try to create one
            try:
                from todo_manager import TodoManager
                self.todo = TodoManager()
            except:
                return []

        try:
            tasks = self.todo.get_overdue_tasks() if hasattr(self.todo, 'get_overdue_tasks') else []
            return [
                {
                    'id': task.get('id'),
                    'title': task.get('title', '')[:60],
                    'priority': task.get('priority', 'medium'),
                    'deadline': task.get('deadline', ''),
                    'days_overdue': self._calculate_days_overdue(task.get('deadline'))
                }
                for task in tasks
            ]
        except Exception as e:
            logger.error(f"Error fetching overdue todos: {e}")
            return []

    def _get_pending_todos(self) -> List[Dict]:
        """Get pending (non-overdue) tasks."""
        if not self.todo:
            try:
                from todo_manager import TodoManager
                self.todo = TodoManager()
            except:
                return []

        try:
            tasks = self.todo.list_tasks(status='pending') if hasattr(self.todo, 'list_tasks') else []

            # Filter out overdue (already in separate section)
            pending = []
            for task in tasks:
                deadline = task.get('deadline')
                if deadline:
                    try:
                        deadline_dt = datetime.fromisoformat(deadline)
                        if deadline_dt < datetime.now():
                            continue  # Skip overdue
                    except:
                        pass

                pending.append({
                    'id': task.get('id'),
                    'title': task.get('title', '')[:60],
                    'priority': task.get('priority', 'medium'),
                    'deadline': deadline
                })

            # Limit to top 5 by priority
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            pending.sort(key=lambda x: priority_order.get(x['priority'], 1))
            return pending[:5]

        except Exception as e:
            logger.error(f"Error fetching pending todos: {e}")
            return []

    async def _get_unsent_drafts(self) -> List[Dict]:
        """Get unsent Gmail drafts older than 1 day."""
        if not self.gmail:
            return []

        try:
            # This requires Gmail API access to drafts
            # For now, return empty - implement when Gmail draft listing is available
            return []
        except Exception as e:
            logger.error(f"Error fetching unsent drafts: {e}")
            return []

    def _get_workspace_items(self) -> List[Dict]:
        """Get workspace items from ProactiveEngine tracking."""
        if not self.db:
            try:
                from db_manager import DatabaseManager
                self.db = DatabaseManager()
            except:
                return []

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT thread_id, subject, from_name, urgency, days_old
                    FROM workspace_items
                    WHERE status = 'active' AND days_old >= 2
                    ORDER BY urgency DESC, days_old DESC
                    LIMIT 5
                """)
                rows = cursor.fetchall()

                return [
                    {
                        'thread_id': row['thread_id'],
                        'subject': row['subject'][:60],
                        'sender': row['from_name'],
                        'urgency': row['urgency'],
                        'days_old': row['days_old']
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.debug(f"Error fetching workspace items: {e}")
            return []

    def _calculate_days_overdue(self, deadline_str: str) -> int:
        """Calculate how many days overdue a task is."""
        if not deadline_str:
            return 0
        try:
            deadline = datetime.fromisoformat(deadline_str)
            delta = datetime.now() - deadline
            return max(0, delta.days)
        except:
            return 0

    def _generate_empty_digest(self) -> str:
        """Generate response when there's nothing to report."""
        now = datetime.now()
        greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"

        return (
            f"<b>{greeting}!</b> \n\n"
            f"<b>All clear!</b> No urgent items to report.\n\n"
            f"• No MCP-labeled emails waiting\n"
            f"• No overdue tasks\n"
            f"• No stale items in workspace\n\n"
            f"<i>Check back later or add tasks with 'add [task] to my todos'</i>"
        )

    async def _generate_ai_summary(self, data: Dict[str, List]) -> str:
        """Generate AI-powered summary using Claude Haiku."""
        try:
            # Format data for Claude
            summary_prompt = self._format_for_ai(data)

            # Call Claude Haiku
            response = self.claude.summarize(
                data=summary_prompt,
                prompt=(
                    "Generate a concise, actionable morning digest for a Director of Operations. "
                    "Prioritize by urgency. Use bullet points. Be brief but complete. "
                    "Format for Telegram (simple markdown ok). "
                    "End with 2-3 suggested next actions."
                )
            )

            if response:
                now = datetime.now()
                greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"
                return f"<b>{greeting}! Here's your digest:</b>\n\n{response}"

        except Exception as e:
            logger.error(f"AI summary failed: {e}")

        # Fallback to formatted digest
        return self._generate_formatted_digest(data)

    def _format_for_ai(self, data: Dict[str, List]) -> str:
        """Format data as text for AI summarization."""
        lines = []

        if data['mcp_emails']:
            lines.append("MCP EMAILS (need attention):")
            for email in data['mcp_emails']:
                lines.append(f"- From {email['sender']}: {email['subject']} ({email['age_days']} days old)")

        if data['overdue_todos']:
            lines.append("\nOVERDUE TASKS:")
            for task in data['overdue_todos']:
                lines.append(f"- [{task['priority'].upper()}] {task['title']} (due {task['deadline']})")

        if data['pending_todos']:
            lines.append("\nPENDING TASKS (top 5):")
            for task in data['pending_todos']:
                deadline_str = f" (due {task['deadline']})" if task['deadline'] else ""
                lines.append(f"- [{task['priority'].upper()}] {task['title']}{deadline_str}")

        if data['workspace_items']:
            lines.append("\nSTALE WORKSPACE ITEMS:")
            for item in data['workspace_items']:
                lines.append(f"- {item['subject']} from {item['sender']} ({item['days_old']} days, {item['urgency']})")

        return "\n".join(lines)

    def _generate_formatted_digest(self, data: Dict[str, List]) -> str:
        """Generate formatted digest without AI."""
        now = datetime.now()
        greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"
        date_str = now.strftime("%A, %B %d")

        lines = [f"<b>{greeting}!</b>", f"<i>{date_str}</i>\n"]

        # MCP Emails
        if data['mcp_emails']:
            lines.append("<b>MCP Emails (need attention)</b>")
            for email in data['mcp_emails'][:5]:  # Limit to 5
                age = f" ({email['age_days']}d)" if email['age_days'] > 0 else ""
                sender = html.escape(email['sender'])
                subject = html.escape(email['subject'])
                lines.append(f"• <b>{sender}</b>: {subject}{age}")
            if len(data['mcp_emails']) > 5:
                lines.append(f"  <i>...and {len(data['mcp_emails']) - 5} more</i>")
            lines.append("")

        # Overdue Tasks
        if data['overdue_todos']:
            lines.append("<b>Overdue Tasks</b>")
            for task in data['overdue_todos']:
                priority_emoji = {'high': '', 'medium': '', 'low': ''}.get(task['priority'], '')
                title = html.escape(task['title'])
                days = task.get('days_overdue', 0)
                overdue_str = f" ({days}d overdue)" if days > 0 else ""
                lines.append(f"• {priority_emoji} {title}{overdue_str}")
            lines.append("")

        # Pending Tasks
        if data['pending_todos']:
            lines.append("<b>Upcoming Tasks</b>")
            for task in data['pending_todos']:
                priority_emoji = {'high': '', 'medium': '', 'low': ''}.get(task['priority'], '•')
                title = html.escape(task['title'])
                deadline = f" (due {task['deadline']})" if task['deadline'] else ""
                lines.append(f"• {title}{deadline}")
            lines.append("")

        # Workspace Items
        if data['workspace_items']:
            lines.append("<b>Waiting for Response</b>")
            for item in data['workspace_items']:
                sender = html.escape(item['sender'])
                subject = html.escape(item['subject'])
                lines.append(f"• {sender}: {subject} ({item['days_old']}d)")
            lines.append("")

        # Suggested Actions
        lines.append("<b>Suggested Actions</b>")
        suggestions = self._generate_suggestions(data)
        for i, suggestion in enumerate(suggestions[:3], 1):
            lines.append(f"{i}. {html.escape(suggestion)}")

        return "\n".join(lines)

    def _generate_suggestions(self, data: Dict[str, List]) -> List[str]:
        """Generate suggested next actions based on data."""
        suggestions = []

        # Priority: Overdue tasks
        if data['overdue_todos']:
            top_overdue = data['overdue_todos'][0]
            suggestions.append(f"Complete overdue task: {top_overdue['title']}")

        # MCP emails waiting longest
        if data['mcp_emails']:
            oldest = max(data['mcp_emails'], key=lambda x: x.get('age_days', 0))
            if oldest['age_days'] >= 3:
                suggestions.append(f"Reply to {oldest['sender']} (waiting {oldest['age_days']} days)")

        # High priority pending
        high_priority = [t for t in data.get('pending_todos', []) if t['priority'] == 'high']
        if high_priority:
            suggestions.append(f"Focus on: {high_priority[0]['title']}")

        # Stale workspace items
        if data['workspace_items']:
            stale = data['workspace_items'][0]
            suggestions.append(f"Follow up with {stale['sender']}")

        # Default suggestion
        if not suggestions:
            suggestions.append("Review inbox for new items")

        return suggestions


# ==================
# CONVENIENCE FUNCTION
# ==================

async def generate_digest(
    gmail_client=None,
    todo_manager=None,
    claude_client=None,
    db_manager=None,
    user_id: int = None
) -> str:
    """
    Convenience function to generate digest.

    Args:
        gmail_client: GmailClient instance
        todo_manager: TodoManager instance
        claude_client: ClaudeClient instance
        db_manager: DatabaseManager instance
        user_id: Optional user ID

    Returns:
        Formatted digest string
    """
    digest = OnDemandDigest(
        gmail_client=gmail_client,
        todo_manager=todo_manager,
        claude_client=claude_client,
        db_manager=db_manager
    )
    return await digest.generate_digest(user_id)
