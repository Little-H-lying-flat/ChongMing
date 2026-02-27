import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
import asyncio

from .state import AgentState

logger = logging.getLogger(__name__)

def edge_evaluate_condition(state: AgentState) -> Literal["end", "sherlock"]:
    """Evaluate 路由条件"""
    if state.get("error"):
        return "sherlock"
    
    # 检查 action_result 是否成功
    action_result = state.get("action_result", {})
    if action_result and not action_result.get("success", False):
        return "sherlock"
        
    return "end"

def edge_sherlock_condition(state: AgentState) -> Literal["healer", "end"]:
    """Sherlock 路由条件"""
    failure_type = state.get("failure_type")
    
    # These three are actionable by Healer
    if failure_type in ["UI_CHANGE", "ENVIRONMENT_ISSUE", "DATA_ISSUE", "VISION_FAILED", "RETRYABLE"]:
        if state.get("retry_count", 0) < state.get("max_retries", 1):
            return "healer"
    return "end"

def create_right_pupil_graph(engine: Any) -> StateGraph:
    """构建右瞳引擎的 LangGraph骨架"""
    workflow = StateGraph(AgentState)
    
    # 注册节点
    workflow.add_node("perceive", engine.node_perceive)
    workflow.add_node("reason", engine.node_reason)
    workflow.add_node("act", engine.node_act)
    workflow.add_node("evaluate", engine.node_evaluate)
    workflow.add_node("sherlock", engine.node_sherlock)
    workflow.add_node("healer", engine.node_healer)
    
    # 构建边 (流转逻辑)
    workflow.set_entry_point("perceive")
    workflow.add_edge("perceive", "reason")
    workflow.add_edge("reason", "act")
    workflow.add_edge("act", "evaluate")
    
    # Evaluate 的条件分支
    workflow.add_conditional_edges(
        "evaluate",
        edge_evaluate_condition,
        {
            "end": END,
            "sherlock": "sherlock"
        }
    )
    
    # Sherlock 的条件分支
    workflow.add_conditional_edges(
        "sherlock",
        edge_sherlock_condition,
        {
            "healer": "healer",
            "end": END
        }
    )
    
    # Healer 修正后重试
    workflow.add_edge("healer", "perceive")
    
    # 编译有向图
    return workflow.compile()
