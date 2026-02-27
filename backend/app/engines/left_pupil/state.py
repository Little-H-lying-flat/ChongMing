from typing import TypedDict, Any, Dict, List, Optional
from app.schemas.api_ir import APIIR, APIResponse

class ApiAgentState(TypedDict):
    """
    LangGraph State for Left Pupil Engine (API Automation)
    """
    api_ir: APIIR                     # The API request definition
    context: Dict[str, Any]           # The execution context (variables, etc.)
    response: Optional[APIResponse]   # The HTTP response after execution
    extracted_values: Dict[str, Any]  # Values extracted post-execution
    assertions_passed: List[str]      # List of passed assertion messages
    assertions_failed: List[str]      # List of failed assertion messages
    error: Optional[str]              # System or execution error message
    failure_type: Optional[str]       # Type of failure (e.g., ASSERTION_MISMATCH, DATA_FORMAT_ERROR)
    retry_count: int                  # Current number of healing retries
    max_retries: int                  # Maximum allowed retries
    created_resources: List[Dict[str, Any]] # Tracked resources for Janitor cleanup
    security_report: List[str]        # Security issues found by Red Teamer
