"""
MCP Orchestrator with Intelligent Gemini Integration
Claude decides when to call Gemini based on reasoning, not keywords
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import MCPOrchestrator
from gemini_helper import GeminiHelper
from typing import Dict, Optional
import json


class SmartMCPOrchestrator(MCPOrchestrator):
    """
    Enhanced orchestrator where Claude thinks and decides when to call Gemini
    """
    
    def __init__(self, db_path: str = None, gemini_api_key: str = None):
        """Initialize with optional Gemini integration"""
        super().__init__(db_path)
        
        self.gemini_helper = None
        if gemini_api_key:
            try:
                self.gemini_helper = GeminiHelper(gemini_api_key)
                print("✓ Gemini integration enabled")
            except Exception as e:
                print(f"⚠ Gemini integration failed: {e}")
                print("  Continuing without Gemini...")
    
    def assess_task_complexity(self, email_data: Dict, mcp_prompt: str) -> Dict:
        """
        Claude evaluates: Can I do this myself, or do I need Gemini's help?
        
        This is the key intelligence - Claude THINKS about the task
        No keyword matching, pure reasoning
        """
        
        assessment = {
            'needs_gemini': False,
            'reasoning': '',
            'gemini_task': None,
            'confidence_without_gemini': 0,
            'confidence_with_gemini': 0
        }
        
        # Claude's self-awareness about its capabilities
        subject = email_data.get('subject', '').lower()
        body = email_data.get('body', '').lower()
        prompt = mcp_prompt.lower()
        
        combined_text = f"{subject} {body} {prompt}"
        
        # Does this task require data from Drive/Sheets/Gmail?
        requires_drive_data = any([
            'spreadsheet' in combined_text,
            'sheet' in combined_text,
            'drive' in combined_text,
            'reconcile' in combined_text and ('ap' in combined_text or 'balance' in combined_text),
            'compare' in combined_text and 'file' in combined_text,
            'find document' in combined_text,
            'search for' in combined_text and 'email' in combined_text,
        ])
        
        # Does this task require searching through past emails?
        requires_email_search = any([
            'did we send' in combined_text,
            'check if' in combined_text and 'sent' in combined_text,
            'find email' in combined_text,
            'search thread' in combined_text,
        ])
        
        # Does this task require bulk document analysis?
        requires_bulk_analysis = any([
            'all mandates' in combined_text,
            'review all' in combined_text,
            'audit' in combined_text and 'document' in combined_text,
            'check compliance' in combined_text,
        ])
        
        # Claude's reasoning
        if requires_drive_data:
            assessment['needs_gemini'] = True
            assessment['reasoning'] = "This task requires accessing Google Drive to find and read spreadsheet data. I'm not good at searching Drive or reading spreadsheet formulas directly. Gemini has native Google integration and can fetch this data efficiently."
            assessment['gemini_task'] = "Search Google Drive for the mentioned spreadsheet, extract the data including all sheets, headers, and values."
            assessment['confidence_without_gemini'] = 20
            assessment['confidence_with_gemini'] = 85
            
        elif requires_email_search:
            assessment['needs_gemini'] = True
            assessment['reasoning'] = "This task requires searching through past email threads. While I can see the current email, I cannot efficiently search Gmail history. Gemini can traverse email threads and find relevant past communications."
            assessment['gemini_task'] = "Search Gmail for emails matching the criteria mentioned, return relevant thread information."
            assessment['confidence_without_gemini'] = 30
            assessment['confidence_with_gemini'] = 80
            
        elif requires_bulk_analysis:
            assessment['needs_gemini'] = True
            assessment['reasoning'] = "This task requires scanning multiple documents across Drive. This is time-consuming for me but Gemini can do bulk document scanning efficiently with its native Drive integration."
            assessment['gemini_task'] = "Search Drive for the mentioned documents, extract key information from each."
            assessment['confidence_without_gemini'] = 25
            assessment['confidence_with_gemini'] = 75
            
        else:
            # Claude can handle this directly
            assessment['needs_gemini'] = False
            assessment['reasoning'] = "I can handle this task directly. It involves email drafting, template usage, or analysis that doesn't require external data fetching. I have access to the SQLite database for patterns and templates."
            assessment['confidence_without_gemini'] = 70
            assessment['confidence_with_gemini'] = 70  # No benefit from Gemini
        
        return assessment
    
    def process_email_with_smart_delegation(self, email_data: Dict, mcp_prompt: str) -> Dict:
        """
        Main processing with intelligent Gemini delegation
        Claude thinks first, then decides if it needs help
        """
        
        result = {
            'status': 'processing',
            'used_gemini': False,
            'gemini_data': None,
            'assessment': None,
            'output': None
        }
        
        print("\n" + "=" * 60)
        print("SMART EMAIL PROCESSING")
        print("=" * 60)
        print(f"\nEmail: {email_data.get('subject', 'No subject')}")
        print(f"From: {email_data.get('sender_email', 'Unknown')}")
        print(f"Instruction: {mcp_prompt}")
        print()
        
        # Step 1: Claude assesses the task
        print("Step 1: Claude assessing task complexity...")
        assessment = self.assess_task_complexity(email_data, mcp_prompt)
        result['assessment'] = assessment
        
        print(f"\nClaude's Assessment:")
        print(f"  Needs Gemini: {assessment['needs_gemini']}")
        print(f"  Reasoning: {assessment['reasoning']}")
        print(f"  Confidence without Gemini: {assessment['confidence_without_gemini']}%")
        print(f"  Confidence with Gemini: {assessment['confidence_with_gemini']}%")
        print()
        
        # Step 2: Call Gemini if needed
        if assessment['needs_gemini'] and self.gemini_helper:
            print("Step 2: Calling Gemini to fetch data...")
            print(f"  Task: {assessment['gemini_task']}")
            
            gemini_data = self.gemini_helper.call_gemini_for_data(
                assessment['gemini_task'],
                email_data
            )
            
            result['used_gemini'] = True
            result['gemini_data'] = gemini_data
            
            if gemini_data.get('data_found'):
                print("  ✓ Gemini returned data successfully")
            else:
                print(f"  ⚠ Gemini couldn't fetch data: {gemini_data.get('reason', 'unknown')}")
            print()
            
        elif assessment['needs_gemini'] and not self.gemini_helper:
            print("Step 2: Gemini needed but not available")
            print("  ⚠ Processing without external data...")
            print()
        
        # Step 3: Process with or without Gemini data
        print("Step 3: Claude processing the request...")
        
        # Use the base orchestrator to process
        base_result = self.process_email(email_data, mcp_prompt)
        
        # Enhance with Gemini data if available
        if result['used_gemini'] and result['gemini_data']:
            base_result['gemini_data_used'] = True
            base_result['gemini_data'] = result['gemini_data']
            base_result['confidence'] = assessment['confidence_with_gemini']
        
        result['output'] = base_result
        result['status'] = 'complete'
        
        print("  ✓ Processing complete")
        print("=" * 60)
        print()
        
        return result


def demo_smart_orchestration():
    """Demo the intelligent Claude + Gemini collaboration"""
    from config import GEMINI_API_KEY, DB_PATH
    
    print("\n" + "=" * 60)
    print("DEMO: Intelligent Claude + Gemini Collaboration")
    print("=" * 60)
    print()
    
    # Initialize
    orchestrator = SmartMCPOrchestrator(
        db_path=DB_PATH,
        gemini_api_key=GEMINI_API_KEY
    )
    
    # Test Case 1: Simple W9 (Claude handles alone)
    print("\n📧 Test Case 1: W9 Request (Claude handles directly)")
    print("-" * 60)
    
    email1 = {
        'subject': 'W9 Request',
        'body': 'Hi Derek, can you send your W9 and wiring instructions?',
        'sender_email': 'client@example.com',
        'sender_name': 'John Client'
    }
    
    result1 = orchestrator.process_email_with_smart_delegation(email1, "send w9")
    print(f"\nResult: {result1['output']['status']}")
    print(f"Used Gemini: {result1['used_gemini']}")
    
    # Test Case 2: AP Reconciliation (needs Gemini)
    print("\n📧 Test Case 2: AP Reconciliation (Needs Drive data)")
    print("-" * 60)
    
    email2 = {
        'subject': 'AP Aging Reconciliation',
        'body': 'The AP Aging doesn\'t match the Balance Sheet. Can you check what\'s wrong?',
        'sender_email': 'accounting@example.com',
        'sender_name': 'Accountant'
    }
    
    result2 = orchestrator.process_email_with_smart_delegation(email2, "reconcile ap")
    print(f"\nResult: {result2['output']['status']}")
    print(f"Used Gemini: {result2['used_gemini']}")
    if result2['gemini_data']:
        print(f"Gemini data: {json.dumps(result2['gemini_data'], indent=2)}")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    demo_smart_orchestration()