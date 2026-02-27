"""
API Sherlock Agent - Root Cause Analysis for API Failures
"""
import autogen
from typing import Dict, Any

class APISherlockAgent(autogen.ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message="""You are API_Sherlock, a senior integration engineer.
Your task is to analyze failed HTTP responses or assertion mismatch failures.
You will be provided with:
1. The Original API Intent (APIIR)
2. The HTTP Response (Status, Headers, Body)
3. The Exact Assertion Error Message

Your job is to identify the root cause of the error. Is it:
- "DATA_FORMAT_ERROR": (e.g. integer instead of string, missing required schema field)
- "AUTH_ERROR": (e.g. 401, 403, invalid token)
- "ASSERTION_MISMATCH": (The server successfully returned a 2xx, but the returned data value did not match the business expectation)
- "SERVER_BUG": (e.g. 500 Internal Server Error with a stack trace)

You MUST output your diagnosis in the following strict JSON format:
{
    "failure_type": "DATA_FORMAT_ERROR",
    "reasoning": "Brief explanation of why"
}
""",
            llm_config=llm_config,
            human_input_mode="NEVER"
        )
