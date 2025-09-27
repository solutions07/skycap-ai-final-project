#!/usr/bin/env python3
"""
Comprehensive System Validation Suite
=====================================

This suite validates all three critical system upgrades:
1. FinancialDataEngine: Perfect parsing of large numerical values
2. Semantic Search: Read and Reason functionality (no raw JSON)
3. General Knowledge Fallback: Brain 2 with proper citations

Target: 100% success rate across all test categories
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from intelligent_agent import IntelligentAgent
except ImportError as e:
    print(f"ERROR: Cannot import IntelligentAgent: {e}")
    sys.exit(1)

class ComprehensiveSystemValidator:
    """Comprehensive validation suite for all system upgrades."""
    
    def __init__(self):
        self.agent = None
        self.results = []
        self.categories = {
            'financial_parsing': [],
            'semantic_reasoning': [],
            'general_knowledge': [],
            'edge_cases': []
        }
    
    def initialize_agent(self) -> bool:
        """Initialize the IntelligentAgent."""
        try:
            print("Initializing IntelligentAgent...")
            self.agent = IntelligentAgent()
            print("✅ Agent initialized successfully!")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize agent: {e}")
            return False
    
    def test_financial_parsing_precision(self) -> Dict[str, Any]:
        """Test Fix #1: Perfect FinancialDataEngine parsing."""
        print("\n=== FIX #1: FINANCIAL DATA ENGINE PRECISION TESTS ===")
        
        financial_tests = [
            {
                'query': 'What were the total assets of Jaiz Bank in Q1 2024?',
                'expected_value': 670984551.0,
                'expected_format': '₦670,984,551.00'
            },
            {
                'query': 'What was Jaiz Bank total assets for 2019?',
                'expected_value': 166837574.0,
                'expected_format': '₦166,837,574.00'
            },
            {
                'query': 'What was the profit before tax for Jaiz Bank in 2018?',
                'expected_value': 660192.0,
                'expected_format': '₦660,192.00'
            },
            {
                'query': 'What were Jaiz Bank total assets in 2017?',
                'expected_value': 87312609.0,
                'expected_format': '₦87,312,609.00'
            },
            {
                'query': 'Show me Jaiz Bank total assets Q1 2024',
                'expected_value': 670984551.0,
                'expected_format': '₦670,984,551.00'
            },
            {
                'query': 'PBT for Jaiz Bank Q1 2024',
                'expected_value': 6000136.0,
                'expected_format': '₦6,000,136.00'
            }
        ]
        
        passed = 0
        total = len(financial_tests)
        
        for i, test in enumerate(financial_tests):
            print(f"Test {i+1}/{total}: {test['query']}")
            
            result = self.agent.ask(test['query'])
            answer = result.get('answer', '')
            engine = result.get('provenance', 'unknown')
            
            # Check if it's using financial engine
            engine_correct = engine == 'financial'
            
            # Check if the formatted value appears in the answer
            format_correct = test['expected_format'] in answer
            
            # Check if no raw JSON appears
            no_raw_json = not ('{' in answer and '}' in answer and '"' in answer)
            
            success = engine_correct and format_correct and no_raw_json
            
            if success:
                print(f"✅ PASS")
                passed += 1
            else:
                print(f"❌ FAIL")
                print(f"   Expected format: {test['expected_format']}")
                print(f"   Expected engine: financial")
                print(f"   Got engine: {engine}")
                print(f"   Got answer: {answer[:100]}...")
                print(f"   Format found: {format_correct}")
                print(f"   No raw JSON: {no_raw_json}")
            
            self.categories['financial_parsing'].append({
                'test': test['query'],
                'passed': success,
                'answer': answer,
                'engine': engine
            })
        
        success_rate = (passed / total) * 100
        print(f"\nFinancial Parsing: {passed}/{total} ({success_rate:.1f}%)")
        return {'passed': passed, 'total': total, 'success_rate': success_rate}
    
    def test_semantic_reasoning(self) -> Dict[str, Any]:
        """Test Fix #2: Semantic Search Read and Reason."""
        print("\n=== FIX #2: SEMANTIC SEARCH READ AND REASON TESTS ===")
        
        semantic_tests = [
            {
                'query': 'Tell me about Skyview Capital company',
                'expect_professional': True,
                'expect_no_raw_json': True
            },
            {
                'query': 'What can you tell me about Skyview financial performance?',
                'expect_professional': True,
                'expect_no_raw_json': True
            },
            {
                'query': 'Describe Skyview Capital services',
                'expect_professional': True,
                'expect_no_raw_json': True
            },
            {
                'query': 'What makes Skyview Capital different from other firms?',
                'expect_professional': True,
                'expect_no_raw_json': True
            }
        ]
        
        passed = 0
        total = len(semantic_tests)
        
        for i, test in enumerate(semantic_tests):
            print(f"Test {i+1}/{total}: {test['query']}")
            
            result = self.agent.ask(test['query'])
            answer = result.get('answer', '')
            engine = result.get('provenance', 'unknown')
            
            # Check no raw JSON (critical requirement)
            no_raw_json = not (answer.startswith('(from semantic search)') or 
                             ('{' in answer and '"' in answer and answer.count('"') > 2))
            
            # Check professional language
            professional = (len(answer) > 50 and 
                          not answer.startswith('ERROR') and
                          'Skyview Capital' in answer)
            
            # Check it's not the default "I don't have" response
            not_default = "I don't have specific information" not in answer
            
            success = no_raw_json and professional and not_default
            
            if success:
                print(f"✅ PASS")
                passed += 1
            else:
                print(f"❌ FAIL")
                print(f"   No raw JSON: {no_raw_json}")
                print(f"   Professional: {professional}")
                print(f"   Not default: {not_default}")
                print(f"   Answer: {answer[:150]}...")
            
            self.categories['semantic_reasoning'].append({
                'test': test['query'],
                'passed': success,
                'answer': answer,
                'engine': engine,
                'no_raw_json': no_raw_json,
                'professional': professional
            })
        
        success_rate = (passed / total) * 100
        print(f"\nSemantic Reasoning: {passed}/{total} ({success_rate:.1f}%)")
        return {'passed': passed, 'total': total, 'success_rate': success_rate}
    
    def test_general_knowledge_fallback(self) -> Dict[str, Any]:
        """Test Fix #3: General Knowledge Fallback (Brain 2)."""
        print("\n=== FIX #3: GENERAL KNOWLEDGE FALLBACK TESTS ===")
        
        general_tests = [
            {
                'query': 'What is earnings per share and how is it calculated?',
                'expect_brain_2': True,
                'expect_citation': True,
                'keywords': ['earnings per share', 'EPS', 'calculated', 'general financial knowledge']
            },
            {
                'query': 'Explain profit before tax calculation',
                'expect_brain_2': True,
                'expect_citation': True,
                'keywords': ['profit before tax', 'PBT', 'general financial knowledge']
            },
            {
                'query': 'What is Islamic banking?',
                'expect_brain_2': True,
                'expect_citation': True,
                'keywords': ['Islamic banking', 'Sharia', 'general banking knowledge']
            },
            {
                'query': 'Define portfolio diversification',
                'expect_brain_2': True,
                'expect_citation': True,
                'keywords': ['diversification', 'investments', 'general investment knowledge']
            },
            {
                'query': 'What is the Nigerian Exchange Group?',
                'expect_brain_2': True,
                'expect_citation': True,
                'keywords': ['Nigerian Exchange', 'NGX', 'general market knowledge']
            }
        ]
        
        passed = 0
        total = len(general_tests)
        
        for i, test in enumerate(general_tests):
            print(f"Test {i+1}/{total}: {test['query']}")
            
            result = self.agent.ask(test['query'])
            answer = result.get('answer', '')
            brain_used = result.get('brain_used', '')
            engine = result.get('provenance', 'unknown')
            
            # Check Brain 2 usage
            brain_2_used = brain_used == 'Brain 2' or engine == 'general_knowledge'
            
            # Check proper citation
            has_citation = any(phrase in answer for phrase in [
                'general financial knowledge',
                'general banking knowledge', 
                'general investment knowledge',
                'general market knowledge',
                'Based on general knowledge'
            ])
            
            # Check keyword presence
            has_keywords = any(keyword.lower() in answer.lower() for keyword in test['keywords'])
            
            # Check it's not default response
            not_default = "I don't have specific information" not in answer
            
            # Check substantive answer
            substantive = len(answer) > 100
            
            success = brain_2_used and has_citation and has_keywords and not_default and substantive
            
            if success:
                print(f"✅ PASS")
                passed += 1
            else:
                print(f"❌ FAIL")
                print(f"   Brain 2 used: {brain_2_used} (brain_used: {brain_used}, engine: {engine})")
                print(f"   Has citation: {has_citation}")
                print(f"   Has keywords: {has_keywords}")
                print(f"   Not default: {not_default}")
                print(f"   Substantive: {substantive}")
                print(f"   Answer: {answer[:200]}...")
            
            self.categories['general_knowledge'].append({
                'test': test['query'],
                'passed': success,
                'answer': answer,
                'brain_used': brain_used,
                'engine': engine,
                'has_citation': has_citation,
                'has_keywords': has_keywords
            })
        
        success_rate = (passed / total) * 100
        print(f"\nGeneral Knowledge Fallback: {passed}/{total} ({success_rate:.1f}%)")
        return {'passed': passed, 'total': total, 'success_rate': success_rate}
    
    def test_edge_cases(self) -> Dict[str, Any]:
        """Test edge cases and integration."""
        print("\n=== EDGE CASE AND INTEGRATION TESTS ===")
        
        edge_tests = [
            {
                'query': 'Who is the CFO?',
                'expect_engine': 'personnel',
                'expect_content': 'Nkiru'
            },
            {
                'query': 'What is the stock price for JAIZBANK?',
                'expect_engine': 'market_price',
                'expect_content': '₦'
            },
            {
                'query': 'How many financial reports are available?',
                'expect_engine': 'metadata',
                'expect_content': '50'
            },
            {
                'query': 'Who is the',
                'expect_helpful': True,
                'expect_no_error': True
            }
        ]
        
        passed = 0
        total = len(edge_tests)
        
        for i, test in enumerate(edge_tests):
            print(f"Test {i+1}/{total}: {test['query']}")
            
            result = self.agent.ask(test['query'])
            answer = result.get('answer', '')
            engine = result.get('provenance', 'unknown')
            
            success = True
            reasons = []
            
            if 'expect_engine' in test:
                if engine != test['expect_engine']:
                    success = False
                    reasons.append(f"Expected engine {test['expect_engine']}, got {engine}")
            
            if 'expect_content' in test:
                if test['expect_content'] not in answer:
                    success = False
                    reasons.append(f"Expected content '{test['expect_content']}' not found")
            
            if test.get('expect_helpful'):
                if len(answer) < 30 or "error" in answer.lower():
                    success = False
                    reasons.append("Answer not helpful enough")
            
            if test.get('expect_no_error'):
                if "error" in answer.lower() or "failed" in answer.lower():
                    success = False
                    reasons.append("Answer contains error indicators")
            
            if success:
                print(f"✅ PASS")
                passed += 1
            else:
                print(f"❌ FAIL")
                for reason in reasons:
                    print(f"   {reason}")
                print(f"   Answer: {answer[:100]}...")
            
            self.categories['edge_cases'].append({
                'test': test['query'],
                'passed': success,
                'answer': answer,
                'engine': engine,
                'reasons': reasons
            })
        
        success_rate = (passed / total) * 100
        print(f"\nEdge Cases: {passed}/{total} ({success_rate:.1f}%)")
        return {'passed': passed, 'total': total, 'success_rate': success_rate}
    
    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all validation tests."""
        print("="*80)
        print("COMPREHENSIVE SYSTEM VALIDATION SUITE")
        print("="*80)
        print(f"Test execution started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not self.initialize_agent():
            return {'success': False, 'error': 'Agent initialization failed'}
        
        # Run all test categories
        results = {
            'financial_parsing': self.test_financial_parsing_precision(),
            'semantic_reasoning': self.test_semantic_reasoning(),
            'general_knowledge': self.test_general_knowledge_fallback(),
            'edge_cases': self.test_edge_cases()
        }
        
        # Calculate overall statistics
        total_passed = sum(r['passed'] for r in results.values())
        total_tests = sum(r['total'] for r in results.values())
        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # Generate final report
        print("\n" + "="*80)
        print("COMPREHENSIVE VALIDATION REPORT")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {total_passed}")
        print(f"Failed: {total_tests - total_passed}")
        print(f"Success Rate: {overall_success_rate:.1f}%")
        print()
        
        if overall_success_rate == 100.0:
            print("🎉 STATUS: ALL TESTS PASSED - SYSTEM READY FOR DEPLOYMENT! 🎉")
        elif overall_success_rate >= 95.0:
            print("✅ STATUS: EXCELLENT - MINOR ISSUES ONLY")
        elif overall_success_rate >= 85.0:
            print("⚠️  STATUS: GOOD - SOME FIXES NEEDED")
        else:
            print("❌ STATUS: SIGNIFICANT ISSUES - MAJOR FIXES REQUIRED")
        
        print()
        print("CATEGORY BREAKDOWN:")
        print("-" * 50)
        for category, result in results.items():
            status = "✅" if result['success_rate'] == 100 else "⚠️" if result['success_rate'] >= 80 else "❌"
            print(f"{status} {category.replace('_', ' ').title()}: {result['passed']}/{result['total']} ({result['success_rate']:.1f}%)")
        
        # Save detailed report
        report_filename = f"comprehensive_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'overall_stats': {
                    'total_tests': total_tests,
                    'total_passed': total_passed,
                    'total_failed': total_tests - total_passed,
                    'success_rate': overall_success_rate
                },
                'category_results': results,
                'detailed_results': self.categories
            }, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_filename}")
        
        if overall_success_rate == 100.0:
            print("\n🎉 ALL SYSTEMS VALIDATED - READY FOR DEPLOYMENT! 🎉")
        else:
            print(f"\n❌ {total_tests - total_passed} TESTS FAILED - FIXES REQUIRED")
        
        return {
            'success': overall_success_rate == 100.0,
            'overall_success_rate': overall_success_rate,
            'total_tests': total_tests,
            'total_passed': total_passed,
            'category_results': results,
            'report_file': report_filename
        }

def main():
    """Main execution function."""
    validator = ComprehensiveSystemValidator()
    result = validator.run_comprehensive_validation()
    
    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)

if __name__ == "__main__":
    main()