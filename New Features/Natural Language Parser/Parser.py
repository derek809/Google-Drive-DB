

// ////needs to be uodated to 
// OLLAMA_MODEL = "qwen2.5:3b"
// OLLAMA_HOST = "http://localhost:11434"

// def parse_message(self, text: str):
//     from smart_parser import SmartParser
//     parser = SmartParser(model="qwen2.5:3b")
//     return parser.parse_with_fallback(text)



import re
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

class SmartParser:
    """
    Hybrid parser using Local LLM (Qwen2.5) and Regex Fallbacks.
    """
    
    def __init__(self, model: str = "qwen2.5:3b"):
        self.model = model
        self.available = OLLAMA_AVAILABLE and self._check_model()

    def _check_model(self) -> bool:
        try:
            models = ollama.list()
            return any(self.model in m['name'] for m in models.get('models', []))
        except:
            return False

    def parse_with_llm(self, text: str) -> Optional[Dict]:
        """Layer 1: Few-Shot LLM Extraction"""
        if not self.available: return None

        prompt = f"""Extract email reference and instruction as JSON.
Examples:
Msg: "draft email to jason on the laura clarke email"
JSON: {{"email_reference": "laura clarke", "instruction": "draft email to jason", "search_type": "keyword"}}

Msg: "forward the invoice to accounting"
JSON: {{"email_reference": "invoice", "instruction": "forward to accounting", "search_type": "keyword"}}

Now parse:
Msg: "{text}"
JSON:"""

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': 0.1},
                format='json'
            )
            data = json.loads(response['response'])
            data['parsed_with'] = 'llm'
            return data
        except Exception as e:
            logger.warning(f"LLM Parse failed: {e}")
            return None

    def _rule_based_parse(self, text: str) -> Dict:
        """Layer 2: Regex Patterns (Backward Compatibility)"""
        # Pattern: X - Y
        match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', text)
        if match:
            return {
                'email_reference': match.group(1).strip(),
                'instruction': match.group(2).strip(),
                'search_type': 'keyword',
                'parsed_with': 'rules'
            }
        
        # Layer 3: Safety Fallback
        return {
            'email_reference': text,
            'instruction': 'process email',
            'search_type': 'keyword',
            'parsed_with': 'fallback'
        }

    def parse_with_fallback(self, text: str) -> Dict:
        """Main entry point for the bot"""
        result = self.parse_with_llm(text)
        if result: return result
        return self._rule_based_parse(text)

# --- Test Suite ---
if __name__ == "__main__":
    parser = SmartParser()
    tests = [
        "draft email to jason on the laura clarke email",
        "Project X - send update",
        "forward the invoice"
    ]
    for t in tests:
        res = parser.parse_with_fallback(t)
        print(f"Input: {t}\nOutput: {res}\n")