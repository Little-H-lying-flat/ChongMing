"""
Visual Expert Agent - Right Pupil V2.5
Responsible for picking the target_id from the Annotated Image and proposing the next action.
"""

from typing import Dict, Any, List
import json
from loguru import logger
from autogen import ConversableAgent

class VisualExpertAgent(ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message='''You are a specialized UI Automation Visual Expert.
Your task is to analyze the provided SoM (Set-of-Mark) elements and the user's task, and determine the next logical UI action to take.
You MUST output your decision in strictly valid JSON format, wrapping it in a `<decision>` block.

The JSON should match the `AUIIR` structure conceptually:
{
    "action_type": "click" | "type" | "scroll" | "done",
    "target": {
        "strategy": "visual",
        "value": "<target_id>",
        "description": "<brief description of the element>"
    },
    "params": {
        "text": "<text to input if type=type, else empty>"
    }
}

Use "done" if the user's task appears to have been fully accomplished on the current screen.
Only propose one action at a time. Do not make up IDs that are not in the SoM list.
''',
            llm_config=llm_config,
            human_input_mode="NEVER",
            is_termination_msg=lambda msg: msg.get("content", "").rstrip().endswith("TERMINATE")
        )
