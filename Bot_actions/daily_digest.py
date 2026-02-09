"""
Daily Digest Capability for Mode 4
Morning email summary via Telegram.

Fetches MCP-labeled emails and provides a summary.

Commands:
    /morning - Get today's email digest
    /digest - Alias for /morning
    /unread - Show unread count by category

Usage:
    from daily_digest import DailyDigest

    digest = DailyDigest()
    summary = digest.get_morning_summary()
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class DailyDigestError(Exception):
    """Custom exception for daily digest errors."""
    pass


class DailyDigest:
    """
    Daily email digest capability for Mode 4.

    Provides morning summaries of emails by category/label.
    Uses Gmail API to fetch recent emails.
    """

    def __init__(self):
        """Initialize daily digest."""
        self._gmail = None
        self._ollama = None

        # Categories to track (MCP labels)
        self.categories = [
            'Action Required',
            'High Priority',
            'Client',
            'Invoice',
            'Contract',
            'Meeting',
            'INBOX'  # Fallback for unlabeled
        ]

    def _get_gmail(self):
        """Lazy load Gmail client."""
        if self._gmail is None:
            from gmail_client import GmailClient
            self._gmail = GmailClient()
            self._gmail.authenticate()
        return self._gmail

    def _get_ollama(self):
        """Lazy load Ollama client."""
        if self._ollama is None:
            try:
                from ollama_client import OllamaClient
                self._ollama = OllamaClient()
            except Exception as e:
                logger.warning(f"Could not load Ollama: {e}")
        return self._ollama

    # ==================
    # DIGEST GENERATION
    # ==================

    def get_morning_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get morning email summary.

        Args:
            hours_back: Hours to look back (default 24)

        Returns:
            Dict with summary data
        """
        gmail = self._get_gmail()
        cutoff = datetime.now() - timedelta(hours=hours_back)

        summary = {
            'total_unread': 0,
            'categories': {},
            'urgent': [],
            'action_required': [],
            'generated_at': datetime.now().isoformat()
        }

        try:
            # Get unread emails - FIXED: use 'reference' and 'search_type' parameters
            unread_emails = gmail.search_emails(
                reference=f'is:unread after:{cutoff.strftime("%Y/%m/%d")}',
                search_type='keyword',
                max_results=50
            )

            summary['total_unread'] = len(unread_emails)

            # Categorize emails
            for email in unread_emails:
                labels = email.get('labels', [])
                categorized = False

                for category in self.categories:
                    if category.upper() in [l.upper() for l in labels]:
                        if category not in summary['categories']:
                            summary['categories'][category] = []
                        summary['categories'][category].append({
                            'subject': email.get('subject', '(no subject)'),
                            'sender': email.get('sender_name', email.get('sender_email', 'Unknown')),
                            'snippet': email.get('snippet', '')[:100],
                            'date': email.get('date', ''),
                            'id': email.get('id', '')
                        })
                        categorized = True
                        break

                if not categorized:
                    if 'Other' not in summary['categories']:
                        summary['categories']['Other'] = []
                    summary['categories']['Other'].append({
                        'subject': email.get('subject', '(no subject)'),
                        'sender': email.get('sender_name', email.get('sender_email', 'Unknown')),
                        'snippet': email.get('snippet', '')[:100],
                        'date': email.get('date', ''),
                        'id': email.get('id', '')
                    })

                # Check for urgent/action required
                subject_lower = email.get('subject', '').lower()
                if any(word in subject_lower for word in ['urgent', 'asap', 'immediate', 'critical']):
                    summary['urgent'].append(email.get('subject', ''))

                if any(word in subject_lower for word in ['action required', 'action needed', 'please respond', 'response needed']):
                    summary['action_required'].append(email.get('subject', ''))

        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            summary['error'] = str(e)

        return summary

    def get_unread_counts(self) -> Dict[str, int]:
        """
        Get unread email counts by category.

        Returns:
            Dict mapping category to count
        """
        gmail = self._get_gmail()
        counts = {}

        for category in self.categories:
            try:
                if category == 'INBOX':
                    query = 'is:unread in:inbox'
                else:
                    query = f'is:unread label:{category.replace(" ", "-")}'

                # FIXED: use 'reference' and 'search_type' parameters
                emails = gmail.search_emails(
                    reference=query,
                    search_type='keyword',
                    max_results=100
                )
                counts[category] = len(emails)
            except Exception as e:
                logger.warning(f"Error counting {category}: {e}")
                counts[category] = 0

        return counts

    def generate_ai_summary(self, summary: Dict[str, Any]) -> str:
        """
        Generate AI summary of emails using Ollama.

        Args:
            summary: Summary dict from get_morning_summary()

        Returns:
            AI-generated summary text
        """
        ollama = self._get_ollama()
        if not ollama or not ollama.is_available():
            return self._format_basic_summary(summary)

        # Build context for AI
        email_list = []
        for category, emails in summary.get('categories', {}).items():
            for email in emails[:5]:  # Limit per category
                email_list.append(f"[{category}] {email['sender']}: {email['subject']}")

        if not email_list:
            return "No new emails in the last 24 hours."

        prompt = f"""Summarize these unread emails briefly for a morning briefing.
Focus on what needs attention today.

Emails:
{chr(10).join(email_list)}

Provide a 2-3 sentence summary highlighting:
1. Most important items needing attention
2. Any patterns or themes
3. Suggested priorities

Keep it concise and actionable."""

        try:
            response = ollama.generate(prompt)
            return response
        except Exception as e:
            logger.warning(f"AI summary failed: {e}")
            return self._format_basic_summary(summary)

    def _format_basic_summary(self, summary: Dict[str, Any]) -> str:
        """Format basic summary without AI."""
        lines = [f"You have {summary['total_unread']} unread emails."]

        if summary.get('urgent'):
            lines.append(f"\nURGENT ({len(summary['urgent'])}):")
            for subj in summary['urgent'][:3]:
                lines.append(f"  - {subj[:50]}")

        if summary.get('action_required'):
            lines.append(f"\nACTION REQUIRED ({len(summary['action_required'])}):")
            for subj in summary['action_required'][:3]:
                lines.append(f"  - {subj[:50]}")

        for category, emails in summary.get('categories', {}).items():
            if emails and category not in ('Other',):
                lines.append(f"\n{category}: {len(emails)} emails")

        return '\n'.join(lines)

    # ==================
    # COMMAND HANDLERS
    # ==================

    def handle_command(self, command: str, args: str, user_id: int) -> str:
        """
        Handle digest command and return response text.

        Args:
            command: Command name (/morning, /digest, /unread)
            args: Command arguments
            user_id: Telegram user ID

        Returns:
            Response message text
        """
        try:
            if command in ('/morning', '/digest'):
                return self._cmd_morning(args)
            elif command == '/unread':
                return self._cmd_unread(args)
            else:
                return f"Unknown command: {command}"
        except Exception as e:
            logger.error(f"Digest command error: {e}")
            return f"Error: {str(e)}"

    def _cmd_morning(self, args: str) -> str:
        """Handle /morning command."""
        # Check for hours argument
        hours = 24
        if args.strip():
            try:
                hours = int(args.strip())
                hours = min(max(hours, 1), 168)  # 1 hour to 1 week
            except ValueError:
                pass

        summary = self.get_morning_summary(hours_back=hours)

        if summary.get('error'):
            return f"Error fetching emails: {summary['error']}"

        if summary['total_unread'] == 0:
            return f"Good morning! No unread emails in the last {hours} hours."

        # Build response
        lines = [f"Good morning! Here's your email digest:"]
        lines.append(f"\nTotal unread: {summary['total_unread']}")

        # Urgent items first
        if summary.get('urgent'):
            lines.append(f"\n🔴 URGENT ({len(summary['urgent'])}):")
            for subj in summary['urgent'][:5]:
                lines.append(f"  {subj[:45]}...")

        # Action required
        if summary.get('action_required'):
            lines.append(f"\n⚡ ACTION REQUIRED ({len(summary['action_required'])}):")
            for subj in summary['action_required'][:5]:
                lines.append(f"  {subj[:45]}...")

        # By category
        for category, emails in summary.get('categories', {}).items():
            if emails:
                lines.append(f"\n{category} ({len(emails)}):")
                for email in emails[:3]:
                    sender = email['sender'].split()[0] if email['sender'] else 'Unknown'
                    lines.append(f"  {sender}: {email['subject'][:35]}...")

        # AI summary if available
        ollama = self._get_ollama()
        if ollama and ollama.is_available() and summary['total_unread'] > 3:
            lines.append("\n🤖 AI Summary:")
            ai_summary = self.generate_ai_summary(summary)
            lines.append(ai_summary)

        return '\n'.join(lines)

    def _cmd_unread(self, args: str) -> str:
        """Handle /unread command."""
        counts = self.get_unread_counts()

        total = sum(counts.values())
        if total == 0:
            return "Inbox zero! No unread emails."

        lines = ["Unread Email Counts:"]
        for category, count in sorted(counts.items(), key=lambda x: -x[1]):
            if count > 0:
                bar = "█" * min(count, 10)
                lines.append(f"  {category}: {count} {bar}")

        lines.append(f"\nTotal: {total}")
        return '\n'.join(lines)

    def cleanup(self):
        """Cleanup resources."""
        if self._gmail:
            del self._gmail
            self._gmail = None
        if self._ollama:
            del self._ollama
            self._ollama = None


# ==================
# TESTING
# ==================

def test_daily_digest():
    """Test daily digest."""
    print("Testing Daily Digest...")
    print("=" * 60)

    digest = DailyDigest()

    # Test command handling (without actual Gmail)
    print("\nTesting command parsing...")
    print("Commands available: /morning, /digest, /unread")

    # Note: Actual testing requires Gmail credentials
    print("\nTo test with Gmail:")
    print("  1. Ensure gmail_client.py is configured")
    print("  2. Run: digest.get_morning_summary()")

    digest.cleanup()
    print("\nDaily digest test complete!")


if __name__ == "__main__":
    test_daily_digest()
