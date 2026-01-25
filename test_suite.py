"""
MCP System Test Suite
Comprehensive tests to verify all components are working
"""

import sqlite3
import sys
from orchestrator import MCPOrchestrator, format_confidence_report
from template_processor import TemplateProcessor


def test_database():
    """Test 1: Verify database exists and has correct structure."""
    print("=" * 60)
    print("TEST 1: Database Structure")
    print("=" * 60)
    
    try:
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(script_dir, "mcp_learning.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'threads', 'messages', 'responses', 'pattern_hints',
            'templates', 'existing_tools', 'knowledge_base',
            'contact_patterns', 'writing_patterns', 'learning_patterns',
            'observed_actions', 'overrides', 'confidence_rules'
        ]
        
        print(f"\nExpected tables: {len(expected_tables)}")
        print(f"Found tables: {len(tables)}")
        
        missing = set(expected_tables) - set(tables)
        if missing:
            print(f"\n❌ Missing tables: {missing}")
            return False
        
        print("✓ All tables present")
        
        # Check bootstrap data
        cursor.execute("SELECT COUNT(*) FROM templates")
        template_count = cursor.fetchone()[0]
        print(f"✓ Templates loaded: {template_count} (expected: 4)")
        
        cursor.execute("SELECT COUNT(*) FROM pattern_hints")
        pattern_count = cursor.fetchone()[0]
        print(f"✓ Patterns loaded: {pattern_count} (expected: 7)")
        
        cursor.execute("SELECT COUNT(*) FROM existing_tools")
        tool_count = cursor.fetchone()[0]
        print(f"✓ Tools loaded: {tool_count} (expected: 3)")
        
        conn.close()
        
        if template_count == 4 and pattern_count == 7 and tool_count == 3:
            print("\n✅ TEST 1 PASSED")
            return True
        else:
            print("\n❌ TEST 1 FAILED: Bootstrap data incomplete")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        return False


def test_orchestrator():
    """Test 2: Verify orchestrator processes emails correctly."""
    print("\n" + "=" * 60)
    print("TEST 2: Orchestrator Processing")
    print("=" * 60)
    
    try:
        test_cases = [
            {
                'name': 'W9 Request',
                'email': {
                    'subject': 'W9 Needed',
                    'body': 'Hi Derek, can you send your W9 and wiring instructions?',
                    'sender_email': 'john@client.com',
                    'sender_name': 'John Smith',
                    'attachments': []
                },
                'prompt': 'send w9',
                'expected_pattern': 'w9_wiring_request',
                'expected_template': 'w9_response'
            },
            {
                'name': 'Payment Confirmation',
                'email': {
                    'subject': 'OCS Payment',
                    'body': 'We sent $50,000 on 1/15/2026. Please confirm receipt.',
                    'sender_email': 'accounting@client.com',
                    'sender_name': 'Jane Accountant',
                    'attachments': []
                },
                'prompt': 'confirm payment',
                'expected_pattern': 'payment_confirmation',
                'expected_template': 'payment_confirmation'
            },
            {
                'name': 'Invoice Request',
                'email': {
                    'subject': 'Invoice for Series A',
                    'body': 'Please invoice for the $2M Series A deal. 3% fee.',
                    'sender_email': 'mike@limadvisors.com',
                    'sender_name': 'Mike Riskind',
                    'attachments': []
                },
                'prompt': 'generate invoice',
                'expected_pattern': 'invoice_processing',
                'expected_template': None  # Should route to Claude Project
            }
        ]
        
        passed = 0
        failed = 0
        
        with MCPOrchestrator() as mcp:
            for tc in test_cases:
                print(f"\n--- {tc['name']} ---")
                result = mcp.process_email(tc['email'], tc['prompt'])
                
                # Check pattern match
                if result.get('pattern_match'):
                    pattern_name = result['pattern_match']['pattern_name']
                    if pattern_name == tc['expected_pattern']:
                        print(f"✓ Pattern matched: {pattern_name}")
                    else:
                        print(f"❌ Expected pattern: {tc['expected_pattern']}, got: {pattern_name}")
                        failed += 1
                        continue
                else:
                    if tc['expected_pattern']:
                        print(f"❌ No pattern matched (expected: {tc['expected_pattern']})")
                        failed += 1
                        continue
                
                # Check routing
                routing = result.get('routing', {})
                if tc['expected_template']:
                    if routing.get('template_id') == tc['expected_template']:
                        print(f"✓ Template selected: {tc['expected_template']}")
                    else:
                        print(f"❌ Expected template: {tc['expected_template']}, got: {routing.get('template_id')}")
                        failed += 1
                        continue
                
                print(f"✓ Status: {result['status']}")
                print(f"✓ Confidence: {result['confidence']}/100")
                passed += 1
        
        print(f"\n{passed}/{len(test_cases)} tests passed")
        
        if failed == 0:
            print("\n✅ TEST 2 PASSED")
            return True
        else:
            print("\n❌ TEST 2 FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_templates():
    """Test 3: Verify template processor generates drafts."""
    print("\n" + "=" * 60)
    print("TEST 3: Template Processing")
    print("=" * 60)
    
    try:
        test_email = {
            'subject': 'W9 Request',
            'body': 'Please send W9 and wiring instructions',
            'sender_email': 'john@example.com',
            'sender_name': 'John Smith',
            'attachments': []
        }
        
        with MCPOrchestrator() as mcp:
            processor = TemplateProcessor(mcp)
            
            # Test W9 template
            print("\n--- Testing W9 Template ---")
            draft_result = processor.generate_draft_from_template(
                'w9_response',
                test_email
            )
            
            if draft_result['status'] == 'success':
                print("✓ Draft generated successfully")
                print(f"✓ Confidence: {draft_result['confidence']}%")
                
                # Check draft contains expected elements
                draft = draft_result['draft']
                if 'Hi John' in draft:
                    print("✓ Personalized greeting included")
                else:
                    print("❌ Missing personalized greeting")
                    return False
                
                if 'W9 form' in draft:
                    print("✓ W9 reference included")
                else:
                    print("❌ Missing W9 reference")
                    return False
                
                if 'wiring instructions' in draft:
                    print("✓ Wiring instructions included")
                else:
                    print("❌ Missing wiring instructions")
                    return False
                
                # Check attachments
                if 'OldCity_W9.pdf' in draft_result['attachments']:
                    print("✓ Attachment listed")
                else:
                    print("❌ Missing attachment")
                    return False
                
                print("\n✅ TEST 3 PASSED")
                return True
            else:
                print(f"❌ Draft generation failed: {draft_result['status']}")
                return False
                
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_confidence_scoring():
    """Test 4: Verify confidence scoring system."""
    print("\n" + "=" * 60)
    print("TEST 4: Confidence Scoring")
    print("=" * 60)
    
    try:
        with MCPOrchestrator() as mcp:
            # Test high confidence (known pattern, would be known sender if in DB)
            high_conf_email = {
                'subject': 'W9 Request',
                'body': 'Please send your W9 form and wiring instructions',
                'sender_email': 'john@example.com',
                'sender_name': 'John Smith',
                'attachments': []
            }
            
            result = mcp.process_email(high_conf_email, 'send w9')
            print(f"\n--- High Confidence Test ---")
            print(f"Email: W9 request from client")
            print(f"Confidence: {result['confidence']}/100")
            
            if result['confidence'] >= 40:  # Base 50 + pattern 20 - unknown sender 20 = 50
                print("✓ High confidence achieved")
            else:
                print(f"❌ Expected high confidence, got {result['confidence']}")
                return False
            
            # Test low confidence (compliance keywords)
            low_conf_email = {
                'subject': 'FINRA Audit Request',
                'body': 'We need all documents for the FINRA audit',
                'sender_email': 'finra@regulator.gov',
                'sender_name': 'Regulator',
                'attachments': []
            }
            
            result = mcp.process_email(low_conf_email, 'respond')
            print(f"\n--- Low Confidence Test ---")
            print(f"Email: FINRA audit email")
            print(f"Confidence: {result['confidence']}/100")
            print(f"Status: {result['status']}")
            
            if result['status'] == 'blocked':
                print("✓ Correctly blocked compliance-related email")
            else:
                print(f"❌ Should have blocked email, got status: {result['status']}")
                return False
            
            print("\n✅ TEST 4 PASSED")
            return True
            
    except Exception as e:
        print(f"\n❌ TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_safety_overrides():
    """Test 5: Verify safety override system."""
    print("\n" + "=" * 60)
    print("TEST 5: Safety Overrides")
    print("=" * 60)
    
    try:
        with MCPOrchestrator() as mcp:
            dangerous_keywords = [
                'FINRA audit',
                'SEC investigation',
                'compliance violation'
            ]
            
            passed = 0
            for keyword in dangerous_keywords:
                email = {
                    'subject': f'RE: {keyword}',
                    'body': f'We need to discuss the {keyword}',
                    'sender_email': 'regulator@gov.com',
                    'sender_name': 'Regulator',
                    'attachments': []
                }
                
                result = mcp.process_email(email, 'respond')
                
                if result['status'] == 'blocked':
                    print(f"✓ Blocked: {keyword}")
                    passed += 1
                else:
                    print(f"❌ Should have blocked: {keyword}")
            
            if passed == len(dangerous_keywords):
                print(f"\n✅ TEST 5 PASSED ({passed}/{len(dangerous_keywords)})")
                return True
            else:
                print(f"\n❌ TEST 5 FAILED ({passed}/{len(dangerous_keywords)})")
                return False
                
    except Exception as e:
        print(f"\n❌ TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run complete test suite."""
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "MCP SYSTEM TEST SUITE" + " " * 22 + "║")
    print("╚" + "=" * 58 + "╝")
    
    results = {
        'Database Structure': test_database(),
        'Orchestrator Processing': test_orchestrator(),
        'Template Processing': test_templates(),
        'Confidence Scoring': test_confidence_scoring(),
        'Safety Overrides': test_safety_overrides()
    }
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED! System is ready for Phase 1.")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())