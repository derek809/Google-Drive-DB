"""
MCP Email Processor - Complete workflow with learning
Processes emails and learns from Derek's edits
"""

import sqlite3
from datetime import datetime
from orchestrator import MCPOrchestrator, format_confidence_report
from template_processor import TemplateProcessor
from learning_loop import LearningLoop, format_learning_report
from typing import Dict, Optional


class EmailProcessor:
    """Complete email processing with learning integration."""
    
    def __init__(self, db_path: str = None):
        """Initialize processor."""
        if db_path is None:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "mcp_learning.db")
        self.db_path = db_path
    
    def process_new_email(
        self,
        email_data: Dict,
        mcp_prompt: str
    ) -> Dict:
        """
        Process a new email labeled [MCP].
        
        Args:
            email_data: Dict with subject, body, sender_email, sender_name, attachments
            mcp_prompt: Derek's instruction
        
        Returns:
            Dict with draft and processing details
        """
        with MCPOrchestrator(self.db_path) as mcp:
            # Process email
            result = mcp.process_email(email_data, mcp_prompt)
            
            # Log to database
            thread_id = self._log_thread(email_data, mcp_prompt)
            message_id = self._log_message(thread_id, email_data)
            
            # Generate draft if template ready
            draft = None
            draft_info = {}
            
            if result['status'] == 'template_ready' and result.get('routing', {}).get('template_id'):
                processor = TemplateProcessor(mcp)
                template_id = result['routing']['template_id']
                
                draft_result = processor.generate_draft_from_template(
                    template_id,
                    email_data
                )
                
                draft = draft_result.get('draft')
                draft_info = {
                    'status': draft_result.get('status'),
                    'confidence': draft_result.get('confidence'),
                    'warnings': draft_result.get('warnings', []),
                    'attachments': draft_result.get('attachments', [])
                }
                
                # Log response
                response_id = self._log_response(
                    thread_id,
                    template_id,
                    draft,
                    result.get('confidence', 0)
                )
                
                draft_info['response_id'] = response_id
            
            # Learn about contact
            with LearningLoop(self.db_path) as learning:
                learning.learn_contact(
                    email_data['sender_email'],
                    email_data.get('sender_name', ''),
                    topics=[email_data.get('subject', '')]
                )
            
            return {
                'status': result['status'],
                'confidence': result.get('confidence', 0),
                'pattern_match': result.get('pattern_match'),
                'draft': draft,
                'draft_info': draft_info,
                'routing': result.get('routing'),
                'reasoning': result.get('reasoning', [])
            }
    
    def record_sent_email(
        self,
        response_id: int,
        final_text: str
    ) -> Dict:
        """
        Record that Derek sent an email (possibly with edits).
        This triggers learning.
        
        Args:
            response_id: ID from process_new_email
            final_text: What Derek actually sent
        
        Returns:
            Learning results
        """
        with LearningLoop(self.db_path) as learning:
            return learning.compare_and_learn(response_id, final_text, was_sent=True)
    
    def record_deleted_draft(self, response_id: int) -> Dict:
        """
        Record that Derek deleted/didn't use a draft.
        
        Args:
            response_id: ID from process_new_email
        
        Returns:
            Learning results
        """
        with LearningLoop(self.db_path) as learning:
            return learning.compare_and_learn(response_id, "", was_sent=False)
    
    def get_learning_stats(self) -> Dict:
        """Get overall learning statistics."""
        with LearningLoop(self.db_path) as learning:
            return learning.get_learning_summary()
    
    def get_writing_patterns(self, limit: int = 20) -> list:
        """Get learned writing patterns."""
        with LearningLoop(self.db_path) as learning:
            return learning.get_writing_patterns(limit)
    
    def get_contact_info(self, email: str) -> Optional[Dict]:
        """Get learned info about a contact."""
        with LearningLoop(self.db_path) as learning:
            return learning.get_contact_info(email)
    
    def _log_thread(self, email_data: Dict, mcp_prompt: str) -> int:
        """Log thread to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Generate thread ID (in real system, would come from Gmail)
        import hashlib
        gmail_thread_id = hashlib.md5(
            f"{email_data['subject']}{email_data['sender_email']}".encode()
        ).hexdigest()
        
        cursor.execute("""
            INSERT OR IGNORE INTO threads 
            (gmail_thread_id, subject, participants, mcp_prompt, status)
            VALUES (?, ?, ?, ?, 'processing')
        """, (
            gmail_thread_id,
            email_data.get('subject', ''),
            f"['{email_data['sender_email']}']",
            mcp_prompt
        ))
        
        cursor.execute("""
            SELECT id FROM threads WHERE gmail_thread_id = ?
        """, (gmail_thread_id,))
        
        thread_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        return thread_id
    
    def _log_message(self, thread_id: int, email_data: Dict) -> int:
        """Log message to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Generate message ID
        import hashlib
        gmail_message_id = hashlib.md5(
            f"{email_data['body']}{datetime.now().isoformat()}".encode()
        ).hexdigest()
        
        cursor.execute("""
            INSERT OR IGNORE INTO messages 
            (thread_id, gmail_message_id, sender_email, sender_name, body, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            thread_id,
            gmail_message_id,
            email_data['sender_email'],
            email_data.get('sender_name', ''),
            email_data.get('body', ''),
            datetime.now().isoformat()
        ))
        
        cursor.execute("""
            SELECT id FROM messages WHERE gmail_message_id = ?
        """, (gmail_message_id,))
        
        message_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        return message_id
    
    def _log_response(
        self,
        thread_id: int,
        template_id: str,
        draft_text: str,
        confidence: float
    ) -> int:
        """Log generated response."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO responses 
            (thread_id, template_id, model_used, draft_text, confidence_score)
            VALUES (?, ?, 'Claude', ?, ?)
        """, (thread_id, template_id, draft_text, confidence))
        
        response_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return response_id


# ==================
# DEMO / TESTING
# ==================

def demo_workflow():
    """Demonstrate the complete workflow."""
    print("=" * 60)
    print("MCP EMAIL PROCESSOR - DEMO WORKFLOW")
    print("=" * 60)
    print()
    
    processor = EmailProcessor()
    
    # Example email
    email = {
        'subject': 'W9 Request',
        'body': 'Hi Derek, can you please send your W9 form and wiring instructions?',
        'sender_email': 'john@client.com',
        'sender_name': 'John Client',
        'attachments': []
    }
    
    prompt = "send w9"
    
    print("STEP 1: Process new email")
    print("-" * 60)
    result = processor.process_new_email(email, prompt)
    
    print(f"Status: {result['status']}")
    print(f"Confidence: {result['confidence']}/100")
    if result.get('pattern_match'):
        print(f"Pattern: {result['pattern_match']['pattern_name']}")
    print()
    
    if result.get('draft'):
        print("DRAFT GENERATED:")
        print("-" * 60)
        print(result['draft'])
        print("-" * 60)
        print()
        
        # Simulate Derek editing and sending
        response_id = result['draft_info']['response_id']
        
        # Simulate minor edits
        final_text = result['draft'].replace(
            "Let me know if you need anything else!",
            "Let me know if you need anything else. Thanks!"
        )
        
        print("STEP 2: Derek edited and sent")
        print("-" * 60)
        learning_result = processor.record_sent_email(response_id, final_text)
        
        print(f"Outcome: {learning_result['outcome']}")
        print(f"Edit Percentage: {learning_result['edit_percentage']:.1f}%")
        print(f"Patterns Learned: {learning_result['patterns_learned']}")
        print()
    
    print("STEP 3: Learning Summary")
    print("-" * 60)
    stats = processor.get_learning_stats()
    print(format_learning_report(stats))


if __name__ == "__main__":
    demo_workflow()
