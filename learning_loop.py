"""
MCP Learning Loop - Makes the system smarter over time
Compares drafts vs. sent emails, extracts patterns, updates confidence
"""

import sqlite3
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json


class LearningLoop:
    """Handles learning from Derek's email edits and decisions."""
    
    def __init__(self, db_path: str = None):
        """Initialize with database path."""
        if db_path is None:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "mcp_learning.db")
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Connect to database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    # ==================
    # COMPARE DRAFT VS SENT
    # ==================
    
    def calculate_edit_percentage(self, draft_text: str, sent_text: str) -> float:
        """
        Calculate how much Derek edited the draft.
        Returns percentage (0-100).
        """
        if not draft_text or not sent_text:
            return 100.0  # Complete rewrite
        
        # Simple word-based comparison
        draft_words = set(draft_text.lower().split())
        sent_words = set(sent_text.lower().split())
        
        if len(sent_words) == 0:
            return 100.0
        
        # Words that were added or removed
        added = sent_words - draft_words
        removed = draft_words - sent_words
        changed = len(added) + len(removed)
        
        # Calculate percentage
        total_words = max(len(draft_words), len(sent_words))
        edit_pct = (changed / total_words) * 100 if total_words > 0 else 0
        
        return min(100.0, edit_pct)
    
    def compare_and_learn(
        self,
        response_id: int,
        final_text: str,
        was_sent: bool = True
    ) -> Dict:
        """
        Compare draft vs final sent version and learn from differences.
        
        Args:
            response_id: ID from responses table
            final_text: What Derek actually sent
            was_sent: Whether Derek sent it (True) or deleted (False)
        
        Returns:
            Dict with learning results
        """
        cursor = self.conn.cursor()
        
        # Get the draft
        cursor.execute("""
            SELECT r.draft_text, r.confidence_score, r.template_id,
                   t.subject, t.mcp_prompt, t.gmail_thread_id
            FROM responses r
            JOIN threads t ON r.thread_id = t.id
            WHERE r.id = ?
        """, (response_id,))
        
        row = cursor.fetchone()
        if not row:
            return {'status': 'error', 'message': 'Response not found'}
        
        draft_text = row['draft_text']
        
        # Calculate edit percentage
        edit_pct = self.calculate_edit_percentage(draft_text, final_text)
        
        # Classify outcome
        if not was_sent:
            outcome = 'deleted'
        elif edit_pct < 10:
            outcome = 'success'
        elif edit_pct < 30:
            outcome = 'good'
        elif edit_pct < 50:
            outcome = 'needs_work'
        else:
            outcome = 'failure'
        
        # Update response record
        cursor.execute("""
            UPDATE responses
            SET final_text = ?,
                sent = ?,
                user_edited = ?,
                edit_percentage = ?,
                sent_at = ?
            WHERE id = ?
        """, (final_text, 1 if was_sent else 0, 1, edit_pct, 
              datetime.now().isoformat(), response_id))
        
        # Extract what changed
        changes = self._extract_changes(draft_text, final_text)
        
        # Learn from the changes
        learning_results = {
            'outcome': outcome,
            'edit_percentage': edit_pct,
            'changes_detected': len(changes),
            'patterns_learned': []
        }
        
        if changes and was_sent:
            # Extract new phrases Derek used
            new_phrases = self._extract_phrases(final_text, draft_text)
            for phrase in new_phrases:
                self._learn_writing_pattern(phrase, row['subject'])
                learning_results['patterns_learned'].append(phrase)
        
        # Update pattern confidence
        if row['template_id']:
            self._update_template_success(row['template_id'], outcome)
        
        self.conn.commit()
        
        return learning_results
    
    def _extract_changes(self, draft: str, sent: str) -> List[Dict]:
        """Extract what changed between draft and sent."""
        changes = []
        
        draft_lines = draft.split('\n')
        sent_lines = sent.split('\n')
        
        # Find added lines
        for line in sent_lines:
            if line.strip() and line not in draft:
                changes.append({
                    'type': 'added',
                    'text': line.strip()
                })
        
        # Find removed lines
        for line in draft_lines:
            if line.strip() and line not in sent:
                changes.append({
                    'type': 'removed',
                    'text': line.strip()
                })
        
        return changes
    
    def _extract_phrases(self, sent: str, draft: str) -> List[str]:
        """Extract new phrases Derek used that weren't in draft."""
        # Simple phrase extraction (3-8 words)
        sent_lower = sent.lower()
        draft_lower = draft.lower()
        
        phrases = []
        words = sent_lower.split()
        
        for length in [3, 4, 5]:  # 3-5 word phrases
            for i in range(len(words) - length + 1):
                phrase = ' '.join(words[i:i+length])
                
                # If it's in sent but not in draft, and looks like a useful phrase
                if phrase in sent_lower and phrase not in draft_lower:
                    if self._is_useful_phrase(phrase):
                        phrases.append(phrase)
        
        return list(set(phrases))[:5]  # Top 5 unique phrases
    
    def _is_useful_phrase(self, phrase: str) -> bool:
        """Check if phrase is worth learning."""
        # Filter out common/useless phrases
        skip_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have',
                      'a', 'an', 'to', 'of', 'in', 'is', 'it', 'be', 'are', 'was'}
        words = phrase.split()

        # Must have at least 2 meaningful words
        meaningful_words = [w for w in words if w not in skip_words]
        if len(meaningful_words) < 2:
            return False

        # Known useful phrase starters (high confidence)
        useful_starts = [
            'just wanted', 'please find', 'looping in', 'let me know',
            'i wanted to', 'thanks for', 'happy to', 'feel free',
            'as discussed', 'per our', 'following up', 'circling back',
            'wanted to check', 'quick note', 'heads up', 'fyi',
            'appreciate your', 'looking forward', 'sounds good',
            'will do', 'got it', 'makes sense', 'good point',
            'i can', 'we can', 'i will', 'we will',
            'please let', 'if you', 'when you', 'once you',
            'attached is', 'attached are', 'see attached', 'please see'
        ]

        if any(phrase.startswith(start) for start in useful_starts):
            return True

        # Also learn phrases with business/finance keywords
        business_keywords = ['payment', 'invoice', 'wire', 'transfer', 'confirm',
                             'approve', 'review', 'update', 'schedule', 'meeting',
                             'deadline', 'urgent', 'priority', 'completed', 'pending']
        if any(kw in phrase for kw in business_keywords):
            return True

        # Learn phrases with action verbs
        action_verbs = ['send', 'provide', 'share', 'forward', 'submit', 'complete',
                        'review', 'approve', 'confirm', 'schedule', 'arrange']
        if any(phrase.startswith(verb) or f' {verb} ' in phrase for verb in action_verbs):
            return True

        # Default: accept phrases with enough meaningful content
        # (less restrictive than before)
        return len(meaningful_words) >= 3
    
    # ==================
    # LEARNING STORAGE
    # ==================
    
    def _learn_writing_pattern(self, phrase: str, context: str):
        """Store a new writing pattern Derek uses."""
        cursor = self.conn.cursor()
        
        # Check if exists
        cursor.execute("""
            SELECT id, frequency FROM writing_patterns
            WHERE phrase = ?
        """, (phrase,))
        
        existing = cursor.fetchone()
        
        if existing:
            # Increment frequency
            cursor.execute("""
                UPDATE writing_patterns
                SET frequency = frequency + 1,
                    last_used = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), existing['id']))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO writing_patterns (phrase, context, frequency)
                VALUES (?, ?, 1)
            """, (phrase, context))
        
        self.conn.commit()
    
    def _update_template_success(self, template_id: str, outcome: str):
        """Update template success rate based on outcome."""
        cursor = self.conn.cursor()
        
        # Get current stats
        cursor.execute("""
            SELECT usage_count, success_rate FROM templates
            WHERE template_id = ?
        """, (template_id,))
        
        row = cursor.fetchone()
        if not row:
            return
        
        usage_count = row['usage_count'] + 1
        success_rate = row['success_rate'] or 0.0
        
        # Update success rate (moving average)
        success_value = 1.0 if outcome in ['success', 'good'] else 0.0
        new_success_rate = ((success_rate * (usage_count - 1)) + success_value) / usage_count
        
        cursor.execute("""
            UPDATE templates
            SET usage_count = ?,
                success_rate = ?,
                last_used = ?
            WHERE template_id = ?
        """, (usage_count, new_success_rate, datetime.now().isoformat(), template_id))
        
        self.conn.commit()
    
    def learn_contact(
        self,
        email: str,
        name: str,
        tone_observed: str = None,
        topics: List[str] = None
    ):
        """Learn about a contact from an interaction."""
        cursor = self.conn.cursor()
        
        # Check if exists
        cursor.execute("""
            SELECT id, interaction_count FROM contact_patterns
            WHERE contact_email = ?
        """, (email,))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update
            updates = {
                'interaction_count': existing['interaction_count'] + 1,
                'last_interaction': datetime.now().isoformat()
            }
            
            if tone_observed:
                updates['preferred_tone'] = tone_observed
            
            if topics:
                # Merge with existing topics
                cursor.execute("""
                    SELECT common_topics FROM contact_patterns WHERE id = ?
                """, (existing['id'],))
                current_topics = cursor.fetchone()['common_topics']
                if current_topics:
                    existing_topics = json.loads(current_topics)
                    topics = list(set(existing_topics + topics))
                updates['common_topics'] = json.dumps(topics)
            
            # Build update query
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [existing['id']]
            
            cursor.execute(f"""
                UPDATE contact_patterns
                SET {set_clause}
                WHERE id = ?
            """, values)
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO contact_patterns 
                (contact_email, contact_name, preferred_tone, common_topics, interaction_count)
                VALUES (?, ?, ?, ?, 1)
            """, (email, name, tone_observed, json.dumps(topics) if topics else None))
        
        self.conn.commit()
    
    # ==================
    # QUERY LEARNED DATA
    # ==================
    
    def get_writing_patterns(self, limit: int = 20) -> List[Dict]:
        """Get most frequently used writing patterns."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT phrase, frequency, context, last_used
            FROM writing_patterns
            ORDER BY frequency DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_contact_info(self, email: str) -> Optional[Dict]:
        """Get learned information about a contact."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM contact_patterns
            WHERE contact_email = ?
        """, (email,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_template_stats(self) -> List[Dict]:
        """Get success statistics for all templates."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT template_id, template_name, usage_count, success_rate, last_used
            FROM templates
            ORDER BY usage_count DESC
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_learning_summary(self) -> Dict:
        """Get overall learning statistics."""
        cursor = self.conn.cursor()
        
        # Count learned items
        cursor.execute("SELECT COUNT(*) as count FROM writing_patterns")
        writing_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM contact_patterns")
        contact_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM knowledge_base")
        knowledge_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM learning_patterns")
        pattern_count = cursor.fetchone()['count']
        
        # Count processed emails
        cursor.execute("SELECT COUNT(*) as count FROM responses WHERE sent = 1")
        sent_count = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT AVG(edit_percentage) as avg_edit
            FROM responses
            WHERE sent = 1 AND edit_percentage IS NOT NULL
        """)
        avg_edit = cursor.fetchone()['avg_edit'] or 0
        
        return {
            'emails_processed': sent_count,
            'average_edit_rate': round(avg_edit, 1),
            'writing_patterns_learned': writing_count,
            'contacts_learned': contact_count,
            'knowledge_entries': knowledge_count,
            'discovered_patterns': pattern_count
        }


# ==================
# UTILITY FUNCTIONS
# ==================

def format_learning_report(summary: Dict) -> str:
    """Format learning summary for display."""
    lines = []
    lines.append("=" * 60)
    lines.append("MCP LEARNING SUMMARY")
    lines.append("=" * 60)
    lines.append("")
    
    lines.append(f"Emails Processed: {summary['emails_processed']}")
    lines.append(f"Average Edit Rate: {summary['average_edit_rate']}%")
    lines.append("")
    
    lines.append("What's Been Learned:")
    lines.append(f"  • Writing Patterns: {summary['writing_patterns_learned']}")
    lines.append(f"  • Contacts: {summary['contacts_learned']}")
    lines.append(f"  • Knowledge Entries: {summary['knowledge_entries']}")
    lines.append(f"  • Discovered Patterns: {summary['discovered_patterns']}")
    lines.append("")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Demo the learning loop
    print("Testing Learning Loop...\n")
    
    with LearningLoop() as learning:
        # Get learning summary
        summary = learning.get_learning_summary()
        print(format_learning_report(summary))
        
        print("\nTop Writing Patterns:")
        patterns = learning.get_writing_patterns(limit=10)
        if patterns:
            for p in patterns:
                print(f"  '{p['phrase']}' (used {p['frequency']} times)")
        else:
            print("  (None learned yet - start processing emails!)")
        
        print("\nTemplate Statistics:")
        stats = learning.get_template_stats()
        for s in stats:
            usage = s['usage_count'] or 0
            success = (s['success_rate'] or 0) * 100
            print(f"  {s['template_id']}: {usage} uses, {success:.0f}% success")
