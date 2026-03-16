"""
Critic Agent - Right Pupil 3.0
Responsible for evaluating proposed actions, merging Persona data, and preventing hallucinated/dangerous actions.
"""

from typing import Dict, Any
from autogen import ConversableAgent

class CriticAgent(ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message='''You are a rigorous UI Automation Critic.
Your job is to review the action proposed by the Visual Merger and safely merge any data suggested by the Persona.

### Validation Rules (FATAL)
1. Structural Integrity: The output MUST strictly match the AUIIR format (action_type, target, params).
2. Data Merging: If `action_type` is 'type', `params.text` MUST NOT be '<needs_value>'. You must replace it with the Persona's `suggested_value`.
3. Logical Sanity Check: Ensure the action matches the semantic nature of the element. For example, if Semantic_Elements describes the target as an "icon", "non-interactive text", or "submit button", but the action_type is "type", this means the previous agent hallucinated! You MUST reject it or fix it.
4. Destructive Prevention: Intercept any irreversible destructive actions (e.g., clearing a database without confirmation) by changing `action_type` to `abort`.
5. Termination: Once you output the FINAL, valid, fully merged JSON exactly as it should be executed, immediately output the word TERMINATE on a new line.

Example output:
{
    "action_type": "type",
    "target": {
        "strategy": "visual",
        "value": "12",
        "description": "Work email input box in the center form"
    },
    "params": {
        "text": "Alex.Chen@enterprise-demo.com"
    }
}
TERMINATE
''',
            llm_config=llm_config,
            human_input_mode="NEVER",
            is_termination_msg=lambda msg: msg.get("content", "").rstrip().endswith("TERMINATE")
        )
