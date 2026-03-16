from typing import TypedDict, List, Dict, Any, Optional
from app.schemas.execution import AUIIR


class AgentState(TypedDict):
    """Right Pupil LangGraph state."""

    # Task context
    task_description: str
    task_url: Optional[str]
    execution_id: Optional[str]
    history: List[Dict[str, Any]]

    # Perception outputs
    current_screenshot: Optional[str]
    current_dom: Optional[Dict[str, Any]]
    som_text: Optional[str]
    semantic_elements: Optional[str]
    annotated_screenshot: Optional[str]
    id_map: Dict[str, Any]

    # Planning and execution
    action_intent: Optional[AUIIR]
    use_existing_action: bool
    action_result: Optional[Dict[str, Any]]

    # Failure and retry controls
    error: Optional[str]
    failure_type: Optional[str]
    retry_count: int
    max_retries: int
