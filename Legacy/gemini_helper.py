"""
Gemini Helper - Data Fetching Assistant for Claude
Gemini's job: Find and extract data from Google Drive, Sheets, Gmail
Claude's job: Interpret and make decisions
"""

from google import genai
from google.genai import types
from typing import Dict, Optional, List
import json

class GeminiHelper:
    """Gemini as a data fetching assistant - no decision making"""
    
    def __init__(self, api_key: str):
        """Initialize Gemini with API key"""
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.0-flash-exp'
    
    def call_gemini_for_data(self, task_description: str, context: Dict) -> Dict:
        """
        Main function Claude calls when it needs data
        
        Args:
            task_description: What data Claude needs (e.g., "Find AP Aging spreadsheet")
            context: Email data and any other context
            
        Returns:
            Structured data in JSON format
        """
        
        prompt = f"""You are a data fetching assistant for Claude.

Claude needs this data: {task_description}

Context from email:
Subject: {context.get('subject', '')}
From: {context.get('sender_email', '')}
Body: {context.get('body', '')}

Your ONLY job is to:
1. Search Google Drive/Gmail for the relevant files/emails/data
2. Extract the data requested
3. Return it in structured JSON format

DO NOT:
- Make recommendations
- Interpret the data
- Suggest what to do
- Make business decisions

Claude will handle all interpretation and decision-making.

Return ONLY valid JSON in this format:
{{
    "data_found": true/false,
    "data_type": "spreadsheet/email/document/multiple",
    "extracted_data": {{
        // Your extracted data here
    }},
    "source_info": {{
        "file_name": "...",
        "location": "...",
        "last_modified": "..."
    }},
    "notes": "Any relevant context about the data"
}}

If you cannot access Google Drive/Gmail (because this is a simulation), return:
{{
    "data_found": false,
    "reason": "simulated_environment",
    "mock_data": {{
        // Realistic mock data for testing
    }}
}}
"""
        
        try:
            # Use new API
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            
            # Parse JSON from response
            response_text = response.text
            
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            data = json.loads(response_text.strip())
            return data
            
        except json.JSONDecodeError as e:
            return {
                "data_found": False,
                "error": "json_parse_error",
                "raw_response": response.text if 'response' in locals() else None,
                "error_details": str(e)
            }
        except Exception as e:
            return {
                "data_found": False,
                "error": "gemini_api_error",
                "error_details": str(e)
            }
    
    def search_drive_files(self, search_query: str, context: Dict) -> Dict:
        """
        Search Google Drive for files
        """
        task = f"Search Google Drive for files matching: {search_query}"
        return self.call_gemini_for_data(task, context)
    
    def read_spreadsheet(self, file_identifier: str, context: Dict) -> Dict:
        """
        Read data from a Google Sheets spreadsheet
        """
        task = f"Read spreadsheet data from: {file_identifier}. Extract all sheet names, headers, and data."
        return self.call_gemini_for_data(task, context)
    
    def search_email_threads(self, search_criteria: str, context: Dict) -> Dict:
        """
        Search Gmail threads for relevant emails
        """
        task = f"Search Gmail for emails matching: {search_criteria}"
        return self.call_gemini_for_data(task, context)
    
    def extract_from_multiple_sources(self, sources: List[str], context: Dict) -> Dict:
        """
        Extract data from multiple sources and combine
        """
        task = f"Extract and combine data from these sources: {', '.join(sources)}"
        return self.call_gemini_for_data(task, context)


def test_gemini_helper():
    """Test the Gemini helper"""
    from config import GEMINI_API_KEY
    
    print("Testing Gemini Helper...")
    print("=" * 60)
    
    helper = GeminiHelper(GEMINI_API_KEY)
    
    # Test data fetch
    test_context = {
        'subject': 'AP Aging Reconciliation',
        'body': 'Can you reconcile the AP Aging with the Balance Sheet?',
        'sender_email': 'test@example.com'
    }
    
    result = helper.call_gemini_for_data(
        "Find AP Aging spreadsheet and extract the data",
        test_context
    )
    
    print("Result:")
    print(json.dumps(result, indent=2))
    print("=" * 60)


if __name__ == "__main__":
    test_gemini_helper()
