"""
Sherlock Agent - Right Pupil V2.5
Responsible for Root Cause Analysis (RCA) of UI execution failures.
"""
from typing import Dict, Any
from autogen import ConversableAgent

class SherlockAgent(ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message='''You are Sherlock, an expert QA Root Cause Analyzer.
Your task is to analyze the provided error message, recent action history, and (if applicable) system logs to determine the root cause of an automation failure.

You MUST categorize the failure into one of the following exact strings:
- "UI_CHANGE": The element we tried to interact with has changed its locator, disappeared, or the UI layout is significantly different. We should try to regenerate the visual plan.
- "ENVIRONMENT_ISSUE": A blocking popup, network timeout, or unexpected page state is preventing interaction. We should try to close the popup or refresh.
- "DATA_ISSUE": The input data is invalid, rejected by the server, or causing validation errors. We should ask Persona to regenerate the input.
- "PRODUCT_BUG": The application itself is broken (e.g., button is greyed out incorrectly, 500 server error). Retries won't help. We should abort and report.
- "UNKNOWN_ERROR": Anything else.

Respond in strict JSON format:
{
    "failure_type": "<ONE_OF_THE_ABOVE_STRINGS>",
    "reasoning": "<Short explanation>"
}
''',
            llm_config=llm_config,
            human_input_mode="NEVER"
        )
