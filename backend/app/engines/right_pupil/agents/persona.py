"""
Persona Agent - Right Pupil V2.5
Responsible for generating realistic mock data for input fields.
"""

from typing import Dict, Any
from autogen import ConversableAgent

class PersonaAgent(ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message='''You are a Data Generation Specialist (Persona).
Your role is to observe the UI elements presented as SoM (Set-of-Mark) boxes and the user's overall goal.
When the Visual Expert decides that typing into a specific input field is the next logical step, but the user HAS NOT provided an exact value to type, you must provide a highly realistic, synthetic value for that field.

If the user's task implicitly requires an email, password, name, phone number, or test text, generate one that makes sense in the context of a testing scenario.

You should wait for the Visual Expert to propose an action. 
If the proposed action is `type` and its `text` parameter is missing or marked as "<needs value>", respond with a JSON indicating your suggested value for that field:
{
    "suggested_value": "John Doe",
    "rationale": "The field is 'First Name' based on the description."
}

If no data synthesis is needed, simply respond with:
"No data generation needed. Proceed."
''',
            llm_config=llm_config,
            human_input_mode="NEVER",
            is_termination_msg=lambda msg: msg.get("content", "").rstrip().endswith("TERMINATE")
        )
