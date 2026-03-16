"""
Visual Expert Agent - Right Pupil 3.0
Responsible for merging UI intent with semantic element descriptions to propose the next physical action.
"""

from typing import Dict, Any, List
import json
from loguru import logger
from autogen import ConversableAgent

class VisualExpertAgent(ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message='''You are a UI Operations Decision Brain (Visual Merger Agent).
Your task is to merge the abstract UI_INTENT with the current screen's Semantic_Elements (from Element Describer) to decide the next physical action.

### Decision Logic (FATAL RULES)
1. Semantic Matching: Find the most matching element ID in Semantic_Elements for the UI_INTENT.
2. No-Target Fallback: If no element remotely matches the intent (Target might be off-screen or loading):
   - You MUST set action_type to "WAIT" or "SCROLL_DOWN". 
   - Set target.value to null. DO NOT guess a wrong ID!
3. Value Hydration: If the action is "type" but the intent provides no specific value, you MUST set params.text to "<needs_value>". The Persona Agent will fill it later.

### Output JSON Format (AUIIR Concept)
You MUST output your decision in strictly valid JSON format:
{
    "thought": "The intent is to input email. ID 12 is described as 'work email input box', which is a perfect match. No value provided, so I request generation.",
    "action_type": "type",
    "target": {
        "strategy": "visual",
        "value": "12",
        "description": "Work email input box in the center form"
    },
    "params": {
        "text": "<needs_value>"
    }
}

Output the JSON and then immediately output TERMINATE on a new line.
''',
            llm_config=llm_config,
            human_input_mode="NEVER",
            is_termination_msg=lambda msg: msg.get("content", "").rstrip().endswith("TERMINATE")
        )
