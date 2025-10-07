import json
from intelligent_agent import IntelligentAgent

# Validation script: runs representative queries and prints a routing transcript

KB_PATH = 'data/master_knowledge_base.json'


def run_validation():
    agent = IntelligentAgent(KB_PATH)

    tests = [
        {
            'name': 'Non-local topic (CRISPR)',
            'q': 'What is CRISPR gene editing?'
        },
        {
            'name': 'Conceptual advisory',
            'q': 'What is the safest strategy to invest in Nigerian stocks?'
        },
        {
            'name': 'Specific data lookup',
            'q': 'What were the total assets for Jaiz Bank in 2023?'
        },
        {
            'name': 'Entity extraction: creator',
            'q': 'Who created SkyCap AI?'
        },
    ]

    transcript = []

    for t in tests:
        res = agent.ask(t['q'])
        transcript.append({
            'case': t['name'],
            'question': t['q'],
            'answer': res.get('answer'),
            'brain_used': res.get('brain_used'),
            'provenance': res.get('provenance')
        })

    print("=== Local Validation Transcript ===")
    for entry in transcript:
        print(f"\n[Case] {entry['case']}")
        print(f"Q: {entry['question']}")
        print(f"Brain: {entry['brain_used']} | Provenance: {entry['provenance']}")
        print(f"A: {entry['answer']}")

    # Also return transcript for programmatic consumers
    return transcript


if __name__ == '__main__':
    run_validation()
