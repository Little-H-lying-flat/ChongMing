import logging
from typing import Any, Literal
from langgraph.graph import StateGraph, END
import asyncio

from .state import ApiAgentState

logger = logging.getLogger(__name__)

def edge_evaluate_condition(state: ApiAgentState) -> Literal["sherlock", "red_team", "janitor"]:
    """
    Evaluate routing condition after execution.
    If there are assertion failures or implicit HTTP errors (>=400), route to sherlock for healing.
    Otherwise, route to red_team (if enabled) or janitor.
    """
    # For now, default to always running red_team if no errors
    # In a full implementation, this could be controlled via an environment variable or config flag
    import os
    enable_red_teamer = os.getenv("ENABLE_RED_TEAMER", "true").lower() == "true"
    enable_janitor = os.getenv("ENABLE_JANITOR", "true").lower() == "true"
    
    # Check if max retries exceeded
    if state.get("retry_count", 0) >= state.get("max_retries", 1) and (state.get("error") or len(state.get("assertions_failed", [])) > 0):
        # We failed, but can't retry anymore. Route directly to janitor.
        return "janitor"
    
    if state.get("error") or len(state.get("assertions_failed", [])) > 0:
        return "sherlock"
        
    response = state.get("response")
    if response and response.status_code >= 400:
        # Check if 400 was explicitly expected. If not, treat as failure needing healing.
        # This implies a failure not caught by standard assertions but requires healing.
        return "sherlock"
        
    if enable_red_teamer:
        return "red_team"
        
    if enable_janitor:
        return "janitor"
        
    return "end"

def edge_sherlock_condition(state: ApiAgentState) -> Literal["healer", "janitor", "end"]:
    """
    Sherlock routing condition.
    If retry count is within limits and it's healable, go to healer.
    Otherwise, go to janitor to cleanup whatever happened before aborting.
    """
    failure_type = state.get("failure_type")
    
    # Healable failure types
    if failure_type in ["DATA_FORMAT_ERROR", "AUTH_ERROR", "ASSERTION_MISMATCH", "RETRYABLE", "UNKNOWN", "SERVER_BUG"]:
        if state.get("retry_count", 0) < state.get("max_retries", 1):
            return "healer"
            
    # If not healable or max retries reached, go to janitor to cleanup
    return "janitor"

def edge_red_team_condition(state: ApiAgentState) -> Literal["janitor", "end"]:
    """ Always route to Janitor after Red Teamer completes """
    return "janitor"

def edge_janitor_condition(state: ApiAgentState) -> str:
    return "end"

def create_left_pupil_graph(executor: Any) -> StateGraph:
    """
    Builds the Left Pupil LangGraph skeleton for API Healing, Security, and Lifecycle.
    """
    workflow = StateGraph(ApiAgentState)
    
    # Register core nodes (Implementation will reside in APIExecutor)
    workflow.add_node("execute", executor.node_execute)
    workflow.add_node("evaluate", executor.node_evaluate)
    
    # Register intelligent multi-agent nodes
    workflow.add_node("sherlock", executor.node_sherlock)
    workflow.add_node("healer", executor.node_healer)
    workflow.add_node("red_team", executor.node_red_team)
    workflow.add_node("janitor", executor.node_janitor)
    
    # Define Edges
    workflow.set_entry_point("execute")
    workflow.add_edge("execute", "evaluate")
    
    # Branching logic after Evaluate
    workflow.add_conditional_edges(
        "evaluate",
        edge_evaluate_condition,
        {
            "sherlock": "sherlock",
            "red_team": "red_team",
            "janitor": "janitor",
            "end": END
        }
    )
    
    # Branching logic after Sherlock (RCA phase)
    workflow.add_conditional_edges(
        "sherlock",
        edge_sherlock_condition,
        {
            "healer": "healer",
            "janitor": "janitor",
            "end": END
        }
    )
    
    # Healer loops back to execute the newly proposed Payload
    workflow.add_edge("healer", "execute")
    
    # Red Team always goes to Janitor afterwards
    workflow.add_conditional_edges(
        "red_team",
        edge_red_team_condition,
        {
            "janitor": "janitor",
            "end": END
        }
    )
    
    # Janitor finishes the graph
    workflow.add_conditional_edges(
        "janitor",
        edge_janitor_condition,
        {
            "end": END
        }
    )
    
    return workflow.compile()
