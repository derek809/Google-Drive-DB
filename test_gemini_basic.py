"""
Basic test to verify Gemini API is working
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import GEMINI_API_KEY
    from google import genai
    
    print("=" * 60)
    print("Testing Gemini API Connection")
    print("=" * 60)
    print()
    
    # Create client
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    print("✓ Gemini API key loaded")
    print("✓ Client initialized: gemini-2.0-flash-exp")
    print()
    
    # Simple test
    print("Sending test message to Gemini...")
    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents="Say hello in one short sentence."
    )
    
    print("✓ Gemini response:", response.text)
    print()
    print("=" * 60)
    print("✓ SUCCESS! Gemini API is working perfectly!")
    print("=" * 60)
    print()
    print("Next step: Run test_gemini_integration.py to test full system")
    
except ImportError as e:
    print(f"✗ Import Error: {e}")
    print()
    print("Did you install google-genai?")
    print("Run: pip install google-genai")
    
except Exception as e:
    print(f"✗ Error: {e}")
    print()
    print("Check:")
    print("1. Did you add your API key to config.py?")
    print("2. Is your API key correct?")
    print("3. Did you enable Generative Language API in Google Cloud?")
