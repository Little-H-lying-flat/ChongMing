"""
Critic Agent - Right Pupil V2.5
Responsible for evaluating proposed actions before they are executed.
"""

from typing import Dict, Any
from autogen import ConversableAgent

class CriticAgent(ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message='''You are a rigorous UI Automation Critic.
Your job is to review the action proposed by the Visual Expert and any data suggested by the Persona.
You must ensure the action is safe, logical, and formatted correctly as JSON matching the `AUIIR` structure.

Validation Rules:
1. The JSON must contain `action_type`, `target`, and `params`.
2. If `action_type` is 'type', `params.text` MUST NOT be empty. It must contain the Persona's suggested value or a reasonable default if missing.
3. If the action is destructive (e.g., clicking 'Delete' without confirmation context), flag it.
4. If everything looks good, output the FINAL, valid JSON exactly as it should be executed, followed immediately by the word TERMINATE on a new line.

Example output:
{
    "action_type": "type",
    "target": {
        "strategy": "visual",
        "value": "12",
        "description": "Username Input"
    },
    "params": {
        "text": "test_user@example.com"
    }
}
TERMINATE
''',
            llm_config=llm_config,
            human_input_mode="NEVER",
            is_termination_msg=lambda msg: msg.get("content", "").rstrip().endswith("TERMINATE")
        )
