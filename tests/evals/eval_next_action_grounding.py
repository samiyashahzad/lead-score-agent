import sys
import pathlib

# Setup path so we can import from app
_ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT_DIR))

from app.schemas import Signals
from app.explanation import generate_explanation

def check_priority_policy(priority: str, next_action: str) -> str:
    """Simple checks for obvious contradictions with the Priority constraint."""
    action = next_action.lower()
    
    if priority == "Hot":
        if any(w in action for w in ["log", "no action", "future reference", "next few days"]):
            return "FAIL: Contains delaying/deferral language for Hot priority."
    elif priority == "Warm":
        if any(w in action for w in ["immediate", "immediately", "urgent", "urgently", "now"]):
            return "FAIL: Contains extreme urgency language for Warm priority."
        if any(w in action for w in ["log", "no action", "future reference"]):
            return "FAIL: Contains deferral language for Warm priority."
    elif priority == "Cold":
        if any(w in action for w in ["immediate", "immediately", "urgent", "schedule", "call", "reach out"]):
            return "FAIL: Contains urgent/outreach language for Cold priority."
            
    return "PASS"

def main():
    states = [
        {
            "name": "State 1: Cold (No Intent)",
            "score": 10,
            "priority": "Cold",
            "classification": "End Customer",
            "confidence": 0.75,
            "signals": Signals(
                distributor_intent=False,
                commercial_intent=False,
                decision_maker=False,
                urgency="low",
                industry_relevance="low",
                geographic_scope="unknown",
                company_scale="unknown"
            )
        },
        {
            "name": "State 2: Warm Standard (Commercial Intent)",
            "score": 65,
            "priority": "Warm",
            "classification": "End Customer",
            "confidence": 1.0,
            "signals": Signals(
                distributor_intent=False,
                commercial_intent=True,
                decision_maker=False,
                urgency="medium",
                industry_relevance="medium",
                geographic_scope="national",
                company_scale="small"
            )
        },
        {
            "name": "State 3: Hot Distributor",
            "score": 95,
            "priority": "Hot",
            "classification": "Distributor",
            "confidence": 1.0,
            "signals": Signals(
                distributor_intent=True,
                commercial_intent=True,
                decision_maker=True,
                urgency="medium",
                industry_relevance="high",
                geographic_scope="multi_country",
                company_scale="large"
            )
        },
        {
            "name": "State 4: High Urgency Contradiction (Warm Priority)",
            "score": 75,
            "priority": "Warm",
            "classification": "End Customer",
            "confidence": 0.75,
            "signals": Signals(
                distributor_intent=False,
                commercial_intent=True,
                decision_maker=True,
                urgency="high",
                industry_relevance="high",
                geographic_scope="unknown",
                company_scale="unknown"
            )
        }
    ]

    print("# Next Action Evaluation (Baseline)\n")
    print("This report provides 12 generations (3 per state) for manual grounding review.\n")
    
    for state in states:
        print(f"## {state['name']}")
        print(f"**Inputs:** Score: {state['score']} | Priority: {state['priority']} | Class: {state['classification']} | Conf: {state['confidence']}")
        print(f"**Signals:** {state['signals'].model_dump_json()}\n")
        
        for iteration in range(1, 4):
            # Generate reasoning and next_action
            _, next_action = generate_explanation(
                signals=state["signals"],
                score=state["score"],
                priority=state["priority"],
                classification=state["classification"],
                confidence=state["confidence"]
            )
            
            policy_check = check_priority_policy(state["priority"], next_action)
            
            print(f"**Iteration {iteration}:**")
            print(f"- **Generated next_action:** \"{next_action}\"")
            print(f"- **Priority-Policy Check:** {policy_check}\n")

if __name__ == "__main__":
    main()
