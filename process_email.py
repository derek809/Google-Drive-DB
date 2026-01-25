#!/usr/bin/env python3
"""
MCP Email Processor - Simple Interface
Usage: Called by Claude to process emails
"""

import sys
import json
from orchestrator import MCPOrchestrator, format_confidence_report
from template_processor import TemplateProcessor


def process_email_simple(email_data, mcp_prompt):
    """
    Process a single email with MCP system.
    
    Args:
        email_data: dict with keys: subject, body, sender_email, sender_name, attachments
        mcp_prompt: Derek's instruction (e.g., "send w9")
    
    Returns:
        dict with processing results
    """
    with MCPOrchestrator() as mcp:
        # Process email
        result = mcp.process_email(email_data, mcp_prompt)
        
        # If template-ready, generate draft
        if result['status'] == 'template_ready' and result.get('routing', {}).get('template_id'):
            processor = TemplateProcessor(mcp)
            template_id = result['routing']['template_id']
            
            draft_result = processor.generate_draft_from_template(
                template_id,
                email_data
            )
            
            result['draft'] = draft_result.get('draft')
            result['draft_status'] = draft_result.get('status')
            result['draft_confidence'] = draft_result.get('confidence')
            result['draft_warnings'] = draft_result.get('warnings', [])
            result['draft_attachments'] = draft_result.get('attachments', [])
        
        return result


def main():
    """Main entry point for command-line usage."""
    if len(sys.argv) < 2:
        print("Usage: python3 process_email.py '<email_json>' '<prompt>'")
        print("Example: python3 process_email.py '{\"subject\":\"W9 Request\",...}' 'send w9'")
        sys.exit(1)
    
    try:
        email_data = json.loads(sys.argv[1])
        mcp_prompt = sys.argv[2] if len(sys.argv) > 2 else ""
        
        result = process_email_simple(email_data, mcp_prompt)
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
