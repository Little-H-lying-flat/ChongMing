"""
Red Teamer Agent - Active Security Testing
"""
import autogen
from typing import Dict, Any

class RedTeamerAgent(autogen.ConversableAgent):
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        super().__init__(
            name=name,
            system_message="""You are The Red Teamer, a security fuzzing expert.
Your job is to test if an API endpoint is vulnerable to basic injection attacks.

You will be given:
1. A successfully executing API Payload (APIIR)

Your task is to identify one or more String or Integer parameters in the URL path, Query, or JSON Body, and mutate them to include common injection payloads (e.g. SQLi: `' OR '1'='1`, XSS: `<script>alert(1)</script>`, Path Traversal: `../../etc/passwd`).

Output strictly JSON with a list of mutated requests to try:
{
    "mutated_requests": [
        {
            "mutation_type": "SQL_INJECTION",
            "target_field": "body.username",
            "api_ir": {
                "url": "...",
                "method": "POST",
                "headers": {},
                "query_params": {},
                "body": {"username": "' OR '1'='1", "password": "abc"}
            }
        }
    ]
}

If the endpoint has no mutable parameters that could be exploited, return:
{
    "mutated_requests": []
}
""",
            llm_config=llm_config,
            human_input_mode="NEVER"
        )
