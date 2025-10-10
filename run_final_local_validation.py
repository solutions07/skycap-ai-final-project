from intelligent_agent import IntelligentAgent
import logging

# Set up logging to see the agent's process
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def run_final_test():
    """Executes a targeted validation of the final critical fixes."""
    
    print("--- [START] FINAL LOCAL VALIDATION OF CRITICAL FIXES ---")
    
    try:
        agent = IntelligentAgent(kb_path='data/master_knowledge_base.json')
        print("✅ Agent initialized successfully.")
    except Exception as e:
        print(f"❌ FATAL: Could not initialize agent. Error: {e}")
        return

    failed_questions = {
        "Flaw A (Comparative Module)": "How did Gross Earnings for Jaiz Bank change from year-end 2023 to year-end 2024?",
        "Flaw B (Date-Matching)": "What was the Earnings Per Share for Jaiz Bank in their 2018 annual report?",
        "Flaw C (Keyword Matching)": "Tell me about a testimonial from Emmanuel Oladimeji."
    }

    print(f"\n--- Running {len(failed_questions)} final validation queries... ---\n")
    
    for flaw, question in failed_questions.items():
        print(f"--- Testing: {flaw} ---")
        print(f"❓ Question: {question}")
        response = agent.ask(question)
        answer = response.get('answer', 'ERROR: No answer found')
        print(f"✅ Response: {answer}")
        print("-" * (25 + len(flaw)))

    print("\n--- [END] FINAL LOCAL VALIDATION ---")

if __name__ == '__main__':
    run_final_test()