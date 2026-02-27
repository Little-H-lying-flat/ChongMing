"""
Data Persona Agent - Generates compliant synthetic data for healing
"""
import autogen
from typing import Dict, Any

class DataPersonaAgent(autogen.ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message="""You are Data_Persona, an expert at generating mock test data.
Sherlock has identified a DATA_FORMAT_ERROR or ASSERTION_MISMATCH caused by invalid or stale data in the API request.

Your task is to propose strictly valid synthetic data to replace the bad data.
For instance:
- If the server complained "email already exists", generate a new random email.
- If the server needs a valid format, provide an example string that strictly adheres to it.
- If an assertion failed because data was 0 instead of 100, suggest appropriate mock values.

You should coordinate with API_Healer. Give your data suggestions clearly to them. Do not write code.
""",
            llm_config=llm_config,
            human_input_mode="NEVER"
        )
