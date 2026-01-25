"""
MCP Email Processing System - Core Orchestrator
Version 1.0
Created: January 22, 2026

This is the main orchestrator that coordinates email processing,
pattern matching, template loading, and response generation.
"""

import sqlite3
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


class MCPOrchestrator:
    """Main orchestrator for MCP email processing system."""
    
    def __init__(self, db_path: str = None):
        """Initialize orchestrator with database connection."""
        if db_path is None:
            # Look for database in the same directory as this script
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "mcp_learning.db")
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        
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
    # INTENT PARSING
    # ==================
    
    def parse_intent(self, mcp_prompt: str, email_content: str) -> str:
        """
        Determine what Derek wants from MCP.
        Returns: 'extract', 'execute', 'modify', 'delegate', 'unclear'
        """
        prompt_lower = mcp_prompt.lower()
        
        # EXTRACTION: Just give me information
        extraction_keywords = ['tell me', 'what is', 'find', 'show me', 'list', 'extract']
        if any(kw in prompt_lower for kw in extraction_keywords):
            return 'extract'
        
        # EXECUTION: Do something (draft, send, generate)
        execution_keywords = ['generate', 'create', 'send', 'make', 'draft']
        if any(kw in prompt_lower for kw in execution_keywords):
            return 'execute'
        
        # MODIFICATION: Edit existing content
        modification_keywords = ['update', 'edit', 'change', 'fix', 'remove', 'correct']
        if any(kw in prompt_lower for kw in modification_keywords):
            return 'modify'
        
        # DELEGATION: Pass to someone else
        delegation_keywords = ['loop in', 'ask', 'forward to', 'delegate']
        if any(kw in prompt_lower for kw in delegation_keywords):
            return 'delegate'
        
        # DEFAULT: Unclear intent
        return 'unclear'
    
    # ==================
    # PATTERN MATCHING
    # ==================
    
    def match_pattern(self, email_content: str, subject: str = "") -> Optional[Dict]:
        """
        Match email content against known patterns.
        Returns pattern info if match found, None otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT pattern_id, pattern_name, keywords, confidence_boost, notes
            FROM pattern_hints
            ORDER BY confidence_boost DESC
        """)
        
        patterns = cursor.fetchall()
        content_lower = email_content.lower()
        subject_lower = subject.lower()
        combined_text = f"{subject_lower} {content_lower}"
        
        for pattern in patterns:
            keywords = json.loads(pattern['keywords']) if pattern['keywords'] else []
            
            # Check if any keywords match
            matches = sum(1 for kw in keywords if kw.lower() in combined_text)
            
            if matches > 0:
                return {
                    'pattern_id': pattern['pattern_id'],
                    'pattern_name': pattern['pattern_name'],
                    'confidence_boost': pattern['confidence_boost'],
                    'keyword_matches': matches,
                    'notes': pattern['notes']
                }
        
        return None
    
    # ==================
    # TEMPLATE MANAGEMENT
    # ==================
    
    def get_template(self, template_id: str) -> Optional[Dict]:
        """Load template by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT template_id, template_name, template_body, variables, attachments
            FROM templates
            WHERE template_id = ?
        """, (template_id,))
        
        template = cursor.fetchone()
        if template:
            return {
                'template_id': template['template_id'],
                'template_name': template['template_name'],
                'template_body': template['template_body'],
                'variables': json.loads(template['variables']) if template['variables'] else [],
                'attachments': json.loads(template['attachments']) if template['attachments'] else []
            }
        return None
    
    def fill_template(self, template_body: str, variables: Dict[str, str]) -> str:
        """Fill template with provided variables."""
        result = template_body
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            result = result.replace(placeholder, str(var_value))
        return result
    
    # ==================
    # CONFIDENCE SCORING
    # ==================
    
    def calculate_confidence(
        self, 
        email_data: Dict,
        pattern_match: Optional[Dict],
        sender_known: bool
    ) -> Tuple[int, List[str]]:
        """
        Calculate confidence score for processing this email.
        Returns: (score, reasoning_list)
        """
        score = 50  # Base confidence
        reasoning = ["Base confidence: 50"]
        
        # Pattern match bonus
        if pattern_match:
            boost = pattern_match['confidence_boost']
            score += boost
            reasoning.append(f"Pattern '{pattern_match['pattern_name']}' matched: +{boost}")
        
        # Known sender bonus
        if sender_known:
            score += 10
            reasoning.append("Known sender: +10")
        else:
            score -= 20
            reasoning.append("Unknown sender: -20")
        
        # Check for compliance keywords (penalties)
        content_lower = email_data.get('body', '').lower()
        subject_lower = email_data.get('subject', '').lower()
        combined = f"{subject_lower} {content_lower}"
        
        compliance_keywords = ['finra audit', 'sec', 'compliance violation', 'regulatory']
        for keyword in compliance_keywords:
            if keyword in combined:
                score -= 30
                reasoning.append(f"Compliance keyword '{keyword}': -30")
                break
        
        # Apply confidence rules from database
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT rule_name, score_modifier
            FROM confidence_rules
            WHERE is_active = 1
            ORDER BY priority DESC
        """)
        
        rules = cursor.fetchall()
        for rule in rules:
            # This is simplified - real implementation would check conditions
            pass
        
        # Clamp score to 0-100 range
        score = max(0, min(100, score))
        
        return score, reasoning
    
    # ==================
    # ROUTING LOGIC
    # ==================
    
    def route_task(
        self, 
        email_content: str,
        mcp_prompt: str,
        attachments: List[str],
        pattern_match: Optional[Dict]
    ) -> Dict:
        """
        Decide where to send the work.
        Returns routing decision with destination and reasoning.
        """
        prompt_lower = mcp_prompt.lower()
        
        # 1. Check explicit instruction in prompt
        if "use claude project" in prompt_lower:
            return {
                'destination': 'claude_project',
                'tool_name': 'specified_in_prompt',
                'reason': 'User explicitly requested Claude Project'
            }
        
        if "use script" in prompt_lower:
            return {
                'destination': 'google_script',
                'script_name': 'specified_in_prompt',
                'reason': 'User explicitly requested Google Script'
            }
        
        # 2. Check pattern hints for routing guidance
        if pattern_match:
            pattern_name = pattern_match['pattern_name']
            
            if pattern_name == 'invoice_processing':
                # Check for CSV attachment
                has_csv = any('.csv' in att.lower() for att in attachments)
                
                if has_csv:
                    return {
                        'destination': 'google_script',
                        'tool_name': 'Invoice CSV Processor',
                        'reason': 'CSV attachment detected'
                    }
                else:
                    return {
                        'destination': 'claude_project',
                        'tool_name': 'Invoice Generator',
                        'reason': 'Body text invoice request'
                    }
            
            # 3. Check if template can handle it directly
            if pattern_name in ['w9_wiring_request', 'payment_confirmation', 'delegation_eytan']:
                template_id = self._get_template_for_pattern(pattern_name)
                return {
                    'destination': 'mcp_direct',
                    'template_id': template_id,
                    'reason': 'Template-based response available'
                }
        
        # 4. Check if extraction only (no execution needed)
        intent = self.parse_intent(mcp_prompt, email_content)
        if intent == 'extract':
            return {
                'destination': 'mcp_direct',
                'action': 'extract_and_present',
                'reason': 'Information extraction request'
            }
        
        # 5. Default: MCP handles with Claude reasoning
        return {
            'destination': 'mcp_direct',
            'action': 'draft_with_claude',
            'reason': 'No specific routing rule matched'
        }
    
    def _get_template_for_pattern(self, pattern_name: str) -> Optional[str]:
        """Map pattern name to template ID."""
        mapping = {
            'w9_wiring_request': 'w9_response',
            'payment_confirmation': 'payment_confirmation',
            'delegation_eytan': 'delegation_eytan',
            'turnaround_expectation': 'turnaround_time'
        }
        return mapping.get(pattern_name)
    
    # ==================
    # CONTACT MANAGEMENT
    # ==================
    
    def is_known_sender(self, email_address: str) -> bool:
        """Check if sender is in contact_patterns table."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id FROM contact_patterns
            WHERE contact_email = ?
        """, (email_address,))
        return cursor.fetchone() is not None
    
    def get_contact_info(self, email_address: str) -> Optional[Dict]:
        """Get contact information if available."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT contact_email, contact_name, relationship_type, preferred_tone
            FROM contact_patterns
            WHERE contact_email = ?
        """, (email_address,))
        
        contact = cursor.fetchone()
        if contact:
            return dict(contact)
        return None
    
    # ==================
    # SAFETY CHECKS
    # ==================
    
    def check_overrides(self, email_data: Dict) -> Optional[Dict]:
        """
        Check if any safety overrides apply to this email.
        Returns override info if one applies, None otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT rule_type, rule_value, action, reason
            FROM overrides
            WHERE is_active = 1
        """)
        
        overrides = cursor.fetchall()
        subject = email_data.get('subject', '').lower()
        content = email_data.get('body', '').lower()
        sender = email_data.get('sender_email', '').lower()
        
        for override in overrides:
            rule_type = override['rule_type']
            rule_value = override['rule_value'].lower()
            
            if rule_type == 'subject_keyword' and rule_value in subject:
                return dict(override)
            
            if rule_type == 'sender' and rule_value == sender:
                return dict(override)
        
        return None
    
    # ==================
    # LOGGING
    # ==================
    
    def log_response(
        self,
        thread_id: int,
        template_id: Optional[str],
        draft_text: str,
        confidence_score: float,
        model_used: str = 'Claude'
    ) -> int:
        """Log response to database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO responses 
            (thread_id, template_id, model_used, draft_text, confidence_score)
            VALUES (?, ?, ?, ?, ?)
        """, (thread_id, template_id, model_used, draft_text, confidence_score))
        
        self.conn.commit()
        return cursor.lastrowid
    
    # ==================
    # MAIN ORCHESTRATION
    # ==================
    
    def process_email(self, email_data: Dict, mcp_prompt: str) -> Dict:
        """
        Main orchestration function - processes one [MCP] labeled email.
        
        Args:
            email_data: Dict with keys: subject, body, sender_email, sender_name, attachments
            mcp_prompt: Derek's instruction for this email
            
        Returns:
            Dict with processing results and next steps
        """
        result = {
            'status': 'unknown',
            'message': '',
            'confidence': 0,
            'routing': None,
            'draft': None,
            'reasoning': []
        }
        
        try:
            # 1. Safety check
            override = self.check_overrides(email_data)
            if override:
                result['status'] = 'blocked'
                result['message'] = f"Safety override triggered: {override['reason']}"
                result['action_required'] = override['action']
                return result
            
            # 2. Parse intent
            intent = self.parse_intent(mcp_prompt, email_data.get('body', ''))
            result['intent'] = intent
            
            # 3. Match pattern
            pattern_match = self.match_pattern(
                email_data.get('body', ''),
                email_data.get('subject', '')
            )
            result['pattern_match'] = pattern_match
            
            # 4. Check sender
            sender_known = self.is_known_sender(email_data.get('sender_email', ''))
            result['sender_known'] = sender_known
            
            # 5. Calculate confidence
            confidence, reasoning = self.calculate_confidence(
                email_data, pattern_match, sender_known
            )
            result['confidence'] = confidence
            result['reasoning'] = reasoning
            
            # 6. Route task
            routing = self.route_task(
                email_data.get('body', ''),
                mcp_prompt,
                email_data.get('attachments', []),
                pattern_match
            )
            result['routing'] = routing
            
            # 7. Execute based on routing
            if routing['destination'] == 'mcp_direct':
                if 'template_id' in routing:
                    # Use template
                    result['status'] = 'template_ready'
                    result['message'] = f"Ready to use template: {routing['template_id']}"
                else:
                    # Need Claude reasoning
                    result['status'] = 'needs_claude'
                    result['message'] = "Requires Claude reasoning to generate response"
            else:
                # External tool needed
                result['status'] = 'needs_delegation'
                result['message'] = f"Route to: {routing['destination']}"
            
            return result
            
        except Exception as e:
            result['status'] = 'error'
            result['message'] = f"Error processing email: {str(e)}"
            return result


# ==================
# UTILITY FUNCTIONS
# ==================

def format_confidence_report(result: Dict) -> str:
    """Format the confidence scoring report for display."""
    report = []
    report.append("=" * 60)
    report.append("MCP PROCESSING REPORT")
    report.append("=" * 60)
    report.append("")
    
    report.append(f"Status: {result['status'].upper()}")
    report.append(f"Message: {result['message']}")
    report.append("")
    
    report.append(f"Intent: {result.get('intent', 'unknown')}")
    report.append(f"Sender Known: {result.get('sender_known', False)}")
    report.append("")
    
    if result.get('pattern_match'):
        pm = result['pattern_match']
        report.append(f"Pattern Matched: {pm['pattern_name']}")
        report.append(f"Confidence Boost: +{pm['confidence_boost']}")
        report.append(f"Notes: {pm['notes']}")
        report.append("")
    
    report.append(f"Final Confidence Score: {result['confidence']}/100")
    report.append("")
    report.append("Reasoning:")
    for reason in result.get('reasoning', []):
        report.append(f"  • {reason}")
    report.append("")
    
    if result.get('routing'):
        report.append("Routing Decision:")
        routing = result['routing']
        report.append(f"  Destination: {routing['destination']}")
        report.append(f"  Reason: {routing['reason']}")
        if 'template_id' in routing:
            report.append(f"  Template: {routing['template_id']}")
        if 'tool_name' in routing:
            report.append(f"  Tool: {routing['tool_name']}")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)


if __name__ == "__main__":
    # Test the orchestrator
    print("MCP Orchestrator initialized successfully!")
    print(f"Database: /root/MCP/mcp_workflow.db")
    
    # Test database connection
    with MCPOrchestrator() as mcp:
        print("\nTesting pattern matching...")
        
        # Test W9 request
        test_email = {
            'subject': 'W9 Needed',
            'body': 'Hi Derek, can you send your W9 and wiring instructions?',
            'sender_email': 'client@example.com',
            'sender_name': 'John Client',
            'attachments': []
        }
        
        result = mcp.process_email(test_email, "send w9")
        print(format_confidence_report(result))