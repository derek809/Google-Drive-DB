"""
Test Suite for Intelligent Claude + Gemini Integration
Tests Claude's decision-making about when to call Gemini
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator_with_gemini import SmartMCPOrchestrator
from config import GEMINI_API_KEY, DB_PATH


def test_case_1_simple_template():
    """Test: Simple W9 request - Claude should handle alone"""
    print("\n" + "=" * 60)
    print("TEST 1: Simple W9 Request")
    print("Expected: Claude handles directly, no Gemini needed")
    print("=" * 60)
    
    orchestrator = SmartMCPOrchestrator(DB_PATH, GEMINI_API_KEY)
    
    email = {
        'subject': 'W9 Needed',
        'body': 'Hi Derek, please send your W9 form and wiring instructions. Thanks!',
        'sender_email': 'john@client.com',
        'sender_name': 'John Client'
    }
    
    result = orchestrator.process_email_with_smart_delegation(email, "send w9")
    
    print("\n📊 Test Result:")
    print(f"  Used Gemini: {result['used_gemini']}")
    print(f"  Status: {result['output']['status']}")
    print(f"  Assessment: {result['assessment']['reasoning'][:100]}...")
    
    assert result['used_gemini'] == False, "Should NOT use Gemini for simple template"
    print("\n✅ TEST 1 PASSED")


def test_case_2_spreadsheet_task():
    """Test: AP reconciliation - Claude should call Gemini"""
    print("\n" + "=" * 60)
    print("TEST 2: AP Reconciliation (Spreadsheet Task)")
    print("Expected: Claude calls Gemini for Drive data")
    print("=" * 60)
    
    orchestrator = SmartMCPOrchestrator(DB_PATH, GEMINI_API_KEY)
    
    email = {
        'subject': 'AP Aging Reconciliation',
        'body': 'Can you reconcile the AP Aging Summary with the Balance Sheet? They don\'t match.',
        'sender_email': 'chris@accounting.com',
        'sender_name': 'Chris Accountant'
    }
    
    result = orchestrator.process_email_with_smart_delegation(email, "reconcile ap aging")
    
    print("\n📊 Test Result:")
    print(f"  Used Gemini: {result['used_gemini']}")
    print(f"  Status: {result['output']['status']}")
    print(f"  Assessment: {result['assessment']['reasoning'][:100]}...")
    
    if result['gemini_data']:
        print(f"  Gemini returned data: {result['gemini_data'].get('data_found', False)}")
    
    assert result['used_gemini'] == True, "Should use Gemini for spreadsheet tasks"
    print("\n✅ TEST 2 PASSED")


def test_case_3_email_search():
    """Test: Past email search - Claude should call Gemini"""
    print("\n" + "=" * 60)
    print("TEST 3: Past Email Search")
    print("Expected: Claude calls Gemini to search Gmail")
    print("=" * 60)
    
    orchestrator = SmartMCPOrchestrator(DB_PATH, GEMINI_API_KEY)
    
    email = {
        'subject': 'Re: Mandate Submission',
        'body': 'Didn\'t we already send the Frank B mandate form last month? Can you check?',
        'sender_email': 'mike@limadvisors.com',
        'sender_name': 'Mike Riskind'
    }
    
    result = orchestrator.process_email_with_smart_delegation(email, "check if we sent this")
    
    print("\n📊 Test Result:")
    print(f"  Used Gemini: {result['used_gemini']}")
    print(f"  Status: {result['output']['status']}")
    print(f"  Assessment: {result['assessment']['reasoning'][:100]}...")
    
    assert result['used_gemini'] == True, "Should use Gemini for email search"
    print("\n✅ TEST 3 PASSED")


def test_case_4_payment_confirmation():
    """Test: Payment confirmation - Claude should handle alone"""
    print("\n" + "=" * 60)
    print("TEST 4: Payment Confirmation")
    print("Expected: Claude handles directly with template")
    print("=" * 60)
    
    orchestrator = SmartMCPOrchestrator(DB_PATH, GEMINI_API_KEY)
    
    email = {
        'subject': 'OCS Payment Confirmation',
        'body': 'We sent $50,000 on Jan 15th. Please confirm receipt.',
        'sender_email': 'accounting@client.com',
        'sender_name': 'Client Accounting'
    }
    
    result = orchestrator.process_email_with_smart_delegation(email, "confirm payment")
    
    print("\n📊 Test Result:")
    print(f"  Used Gemini: {result['used_gemini']}")
    print(f"  Status: {result['output']['status']}")
    print(f"  Assessment: {result['assessment']['reasoning'][:100]}...")
    
    assert result['used_gemini'] == False, "Should NOT use Gemini for simple confirmation"
    print("\n✅ TEST 4 PASSED")


def run_all_tests():
    """Run complete test suite"""
    print("\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "INTELLIGENT GEMINI INTEGRATION TEST SUITE" + " " * 7 + "║")
    print("╚" + "=" * 58 + "╝")
    
    try:
        test_case_1_simple_template()
        test_case_2_spreadsheet_task()
        test_case_3_email_search()
        test_case_4_payment_confirmation()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\nClaude successfully:")
        print("  ✓ Handles simple tasks alone")
        print("  ✓ Calls Gemini for Drive/spreadsheet data")
        print("  ✓ Calls Gemini for email searches")
        print("  ✓ Makes intelligent decisions based on reasoning")
        print("\nYour intelligent delegation system is working!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()