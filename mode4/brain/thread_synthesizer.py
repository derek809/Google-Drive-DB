"""
Thread Synthesizer - Creates actionable summaries of email threads for Mode 4
Synthesizes multi-email threads into 'State of Play' summaries
"""

import sqlite3
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ThreadSynthesizerError(Exception):
    """Exception raised when ThreadSynthesizer encounters an error."""
    pass


class ThreadSynthesizer:
    """
    Synthesizes multi-email threads into actionable summaries.

    Uses the Mode 4 database to fetch thread history and creates
    prompts for Claude to generate comprehensive summaries.
    """

    def __init__(self, db_path: str):
        """
        Initialize ThreadSynthesizer.

        Args:
            db_path: Path to the Mode 4 SQLite database
        """
        self.db_path = db_path
        logger.info(f"ThreadSynthesizer initialized with database: {db_path}")

    def get_thread_history(self, thread_id: int, max_messages: int = 50) -> List[Dict]:
        """
        Fetches all messages for a thread ordered by date.

        Args:
            thread_id: The Gmail thread ID to fetch
            max_messages: Maximum number of messages to return (default: 50)

        Returns:
            List of message dicts containing sender, email, body, and timestamp

        Raises:
            ThreadSynthesizerError: If database query fails
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query messages table for thread history
            # Note: Adjust table/column names if your schema differs
            cursor.execute('''
                SELECT sender_name, sender_email, body, received_at, subject
                FROM messages
                WHERE thread_id = ?
                ORDER BY received_at ASC
                LIMIT ?
            ''', (thread_id, max_messages))

            history = [dict(row) for row in cursor.fetchall()]
            conn.close()

            logger.info(f"Retrieved {len(history)} messages for thread {thread_id}")
            return history

        except sqlite3.Error as e:
            logger.error(f"Database error fetching thread {thread_id}: {e}")
            raise ThreadSynthesizerError(f"Failed to fetch thread history: {str(e)}")

    def create_synthesis_prompt(self, history: List[Dict], custom_instructions: Optional[str] = None) -> str:
        """
        Constructs a prompt for Claude to summarize the thread history.

        Args:
            history: List of message dicts from get_thread_history()
            custom_instructions: Optional additional instructions for Claude

        Returns:
            Formatted prompt string for Claude
        """
        if not history:
            return "No messages found in thread history."

        # Build conversation history text
        full_text = "\n---\n".join([
            f"From: {m['sender_name']} ({m['sender_email']})\n"
            f"Date: {m['received_at']}\n"
            f"Subject: {m.get('subject', 'N/A')}\n"
            f"Body: {m['body']}"
            for m in history
        ])

        # Base prompt template
        prompt = f"""
Below is the history of an email thread.
Synthesize this into a 'State of Play' summary for the user.

CONVERSATION HISTORY:
{full_text}

YOUR TASK:
1. Summarize the current status of this conversation.
2. List all facts agreed upon (dates, amounts, files, commitments).
3. List open questions the user needs to answer.
4. List open questions the other party needs to answer.
5. Suggest the 'Next Best Action' the user should take.
"""

        # Add custom instructions if provided
        if custom_instructions:
            prompt += f"\n\nADDITIONAL INSTRUCTIONS:\n{custom_instructions}"

        return prompt.strip()

    def get_thread_summary_preview(self, thread_id: int, max_chars: int = 500) -> str:
        """
        Get a quick text preview of the thread without full synthesis.

        Useful for showing thread context before generating full summary.

        Args:
            thread_id: The Gmail thread ID
            max_chars: Maximum characters to return

        Returns:
            Preview string of thread content
        """
        try:
            history = self.get_thread_history(thread_id, max_messages=10)

            if not history:
                return f"Thread {thread_id} has no messages."

            preview_lines = [
                f"Thread with {len(history)} messages",
                f"Latest: {history[-1]['sender_name']} - {history[-1]['received_at']}"
            ]

            # Add snippet of latest message
            latest_body = history[-1]['body'][:200]
            preview_lines.append(f"Preview: {latest_body}...")

            preview = "\n".join(preview_lines)

            if len(preview) > max_chars:
                preview = preview[:max_chars] + "..."

            return preview

        except ThreadSynthesizerError as e:
            return f"Error fetching thread preview: {str(e)}"


# --- Test Suite ---
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 3:
        print("Usage: python thread_synthesizer.py <db_path> <thread_id>")
        print("Example: python thread_synthesizer.py mode4.db 12345")
        sys.exit(1)

    db_path = sys.argv[1]
    thread_id = int(sys.argv[2])

    synthesizer = ThreadSynthesizer(db_path)

    print(f"\n{'='*60}")
    print(f"Thread Synthesizer Test - Thread ID: {thread_id}")
    print(f"{'='*60}\n")

    # Get thread history
    print("Fetching thread history...")
    history = synthesizer.get_thread_history(thread_id)

    if not history:
        print(f"No messages found for thread {thread_id}")
        sys.exit(0)

    print(f"Found {len(history)} messages\n")

    # Show preview
    print("Preview:")
    print(synthesizer.get_thread_summary_preview(thread_id))
    print()

    # Generate synthesis prompt
    print("Generated Prompt for Claude:")
    print("="*60)
    prompt = synthesizer.create_synthesis_prompt(history)
    print(prompt)
    print("="*60)
