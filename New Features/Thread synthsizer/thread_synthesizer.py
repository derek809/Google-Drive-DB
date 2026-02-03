"""
MCP Thread Synthesizer
Synthesizes multi-email threads into actionable summaries for Claude.
"""

import sqlite3
import json
from typing import List, Dict

class ThreadSynthesizer:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_thread_history(self, thread_id: int) -> List[Dict]:
        """Fetches all messages for a thread ordered by date."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sender_name, sender_email, body, received_at 
            FROM messages 
            WHERE thread_id = ? 
            ORDER BY received_at ASC
        ''', (thread_id,))
        
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    def create_synthesis_prompt(self, history: List[Dict]) -> str:
        """Constructs a prompt for Claude to summarize the thread history."""
        full_text = "\n---\n".join([
            f"From: {m['sender_name']} ({m['sender_email']})\nDate: {m['received_at']}\nBody: {m['body']}"
            for m in history
        ])
        
        return f"""
        Below is the history of an email thread. 
        Synthesize this into a 'State of Play' summary for Derek.
        
        CONVERSATION HISTORY:
        {full_text}
        
        YOUR TASK:
        1. Summarize the current status.
        2. List all facts agreed upon (dates, amounts, files).
        3. List open questions Derek needs to answer.
        4. List open questions the other party needs to answer.
        5. Suggest the 'Next Best Action'.
        """