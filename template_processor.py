"""
MCP Template Processor
Handles template loading, variable extraction, and draft generation
"""

import re
from typing import Dict, List, Optional, Tuple
from orchestrator import MCPOrchestrator


class TemplateProcessor:
    """Processes templates and generates email drafts."""
    
    def __init__(self, orchestrator: MCPOrchestrator):
        """Initialize with MCP orchestrator."""
        self.mcp = orchestrator
    
    def extract_variables_from_email(
        self,
        template_variables: List[str],
        email_data: Dict
    ) -> Tuple[Dict[str, str], List[str]]:
        """
        Attempt to extract template variables from email content.
        Returns: (extracted_vars, missing_vars)
        """
        extracted = {}
        missing = []
        
        sender_name = email_data.get('sender_name', '')
        sender_email = email_data.get('sender_email', '')
        body = email_data.get('body', '')
        subject = email_data.get('subject', '')
        
        for var in template_variables:
            if var == 'name':
                # Extract first name from sender
                if sender_name:
                    extracted['name'] = sender_name.split()[0]
                else:
                    # Try to extract from email
                    extracted['name'] = sender_email.split('@')[0].title()
            
            elif var == 'wiring_details':
                # This would typically come from a stored value
                extracted['wiring_details'] = """Bank: [Bank Name]
Account: [Account Number]
Routing: [Routing Number]
Swift: [Swift Code if international]"""
                
            elif var == 'amount':
                # Try to extract dollar amounts from email
                amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', body)
                if amounts:
                    extracted['amount'] = amounts[0].replace('$', '')
                else:
                    missing.append('amount')
            
            elif var == 'date':
                # Try to extract dates
                dates = re.findall(r'\d{1,2}/\d{1,2}/\d{2,4}', body)
                if dates:
                    extracted['date'] = dates[0]
                else:
                    missing.append('date')
            
            elif var == 'context':
                # For delegation template - extract key question/issue
                # Use first paragraph or sentence as context
                lines = body.strip().split('\n')
                if lines:
                    extracted['context'] = lines[0][:200]  # First 200 chars
                else:
                    missing.append('context')
            
            elif var == 'request_type':
                # Infer from email content or subject
                if 'invoice' in subject.lower() or 'invoice' in body.lower():
                    extracted['request_type'] = 'invoice processing'
                elif 'mandate' in subject.lower() or 'mandate' in body.lower():
                    extracted['request_type'] = 'mandate review'
                else:
                    missing.append('request_type')
            
            elif var == 'timeline':
                # Default timelines based on request type
                request_type = extracted.get('request_type', '')
                if 'invoice' in request_type:
                    extracted['timeline'] = '2-3 business days'
                elif 'mandate' in request_type:
                    extracted['timeline'] = '1 week'
                else:
                    missing.append('timeline')
            
            elif var == 'specific_date':
                # Calculate date based on timeline
                # For now, placeholder
                extracted['specific_date'] = '[Date will be calculated]'
            
            else:
                # Unknown variable
                missing.append(var)
        
        return extracted, missing
    
    def generate_draft_from_template(
        self,
        template_id: str,
        email_data: Dict,
        manual_vars: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        Generate email draft from template.
        
        Args:
            template_id: ID of template to use
            email_data: Email data dict
            manual_vars: Optional manually provided variables
            
        Returns:
            Dict with draft, confidence, warnings, etc.
        """
        result = {
            'status': 'unknown',
            'draft': None,
            'confidence': 0,
            'warnings': [],
            'extracted_vars': {},
            'missing_vars': []
        }
        
        # Load template
        template = self.mcp.get_template(template_id)
        if not template:
            result['status'] = 'error'
            result['warnings'].append(f"Template '{template_id}' not found")
            return result
        
        # Extract variables
        variables = template['variables']
        extracted_vars, missing_vars = self.extract_variables_from_email(
            variables, email_data
        )
        
        # Override with manual vars if provided
        if manual_vars:
            extracted_vars.update(manual_vars)
            # Remove from missing if now provided
            missing_vars = [v for v in missing_vars if v not in manual_vars]
        
        result['extracted_vars'] = extracted_vars
        result['missing_vars'] = missing_vars
        
        # Calculate confidence based on variable extraction
        total_vars = len(variables)
        extracted_count = len(extracted_vars)
        
        if total_vars > 0:
            extraction_confidence = (extracted_count / total_vars) * 100
        else:
            extraction_confidence = 100  # No variables needed
        
        result['confidence'] = extraction_confidence
        
        # Add warnings for missing vars
        if missing_vars:
            result['warnings'].append(f"⚠️ Missing variables: {', '.join(missing_vars)}")
            result['warnings'].append("Please provide these values before sending")
        
        # Fill template
        try:
            draft = self.mcp.fill_template(template['template_body'], extracted_vars)
            result['draft'] = draft
            result['status'] = 'success' if not missing_vars else 'needs_input'
            result['template_name'] = template['template_name']
            result['attachments'] = template['attachments']
        except Exception as e:
            result['status'] = 'error'
            result['warnings'].append(f"Error filling template: {str(e)}")
        
        return result
    
    def format_draft_output(self, draft_result: Dict, email_data: Dict) -> str:
        """Format draft result for display to Derek."""
        lines = []
        lines.append("=" * 60)
        lines.append("EMAIL DRAFT GENERATED")
        lines.append("=" * 60)
        lines.append("")
        
        lines.append(f"To: {email_data.get('sender_email', '')}")
        lines.append(f"Subject: Re: {email_data.get('subject', '')}")
        lines.append("")
        
        if draft_result.get('warnings'):
            lines.append("⚠️ WARNINGS:")
            for warning in draft_result['warnings']:
                lines.append(f"  {warning}")
            lines.append("")
        
        if draft_result.get('attachments'):
            lines.append("📎 ATTACHMENTS:")
            for att in draft_result['attachments']:
                lines.append(f"  • {att}")
            lines.append("")
        
        lines.append("DRAFT:")
        lines.append("-" * 60)
        lines.append(draft_result.get('draft', '[No draft generated]'))
        lines.append("-" * 60)
        lines.append("")
        
        if draft_result.get('extracted_vars'):
            lines.append("Variables Used:")
            for var, value in draft_result['extracted_vars'].items():
                lines.append(f"  {var}: {value}")
            lines.append("")
        
        lines.append(f"Confidence: {draft_result.get('confidence', 0):.0f}%")
        lines.append(f"Template: {draft_result.get('template_name', 'N/A')}")
        lines.append("")
        
        if draft_result.get('status') == 'needs_input':
            lines.append("⚠️ ACTION REQUIRED:")
            lines.append("Please fill in missing variables before sending")
        elif draft_result.get('status') == 'success':
            lines.append("✓ Ready to review and send")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


def demo_template_processing():
    """Demo the template processor."""
    print("Testing Template Processor\n")
    
    # Test W9 request
    email_data = {
        'subject': 'W9 Request',
        'body': 'Hi Derek, could you please send me your W9 and wiring instructions for payment?',
        'sender_email': 'john@example.com',
        'sender_name': 'John Smith',
        'attachments': []
    }
    
    with MCPOrchestrator() as mcp:
        processor = TemplateProcessor(mcp)
        
        # Generate draft
        draft_result = processor.generate_draft_from_template(
            'w9_response',
            email_data
        )
        
        # Format output
        output = processor.format_draft_output(draft_result, email_data)
        print(output)
        
        print("\n" + "="*60)
        print("Now testing with manual variable override...")
        print("="*60 + "\n")
        
        # Try with manual wiring details
        draft_result2 = processor.generate_draft_from_template(
            'w9_response',
            email_data,
            manual_vars={
                'wiring_details': """Wells Fargo Bank
Account: 1234567890
Routing: 121000248
For international: SWIFT WFBIUS6S"""
            }
        )
        
        output2 = processor.format_draft_output(draft_result2, email_data)
        print(output2)


if __name__ == "__main__":
    demo_template_processing()
