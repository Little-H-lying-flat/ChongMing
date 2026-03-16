import operator
from typing import Annotated, Dict, Any, List, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
import uuid
import json

from app.core.ai_client import get_ai_manager, Message
from app.core.ai_models import AIModule
from app.utils.json_repair import repair_json
from app.core.logging import logger
from app.core.memory_base import memory_base

class GraphState(TypedDict):
    project_id: str
    requirement_text: str
    target_type: str
    target_url: str
    context: str
    
    # Internal state
    extracted_points: List[str]
    scenarios: List[Dict[str, Any]]
    feedback: str
    revision_count: int
    is_swagger: bool
    editor_output: str # New field to track the last raw output from the editor


def _fallback_scenarios_from_points(
    extracted_points: List[str], target_type: str, target_url: str = ""
) -> List[Dict[str, Any]]:
    """Build minimal usable scenarios when AutoGen dependencies are unavailable."""
    if not extracted_points:
        return []

    normalized_target = (target_type or "").upper()
    base_login_url = (target_url or "").strip() or "https://example.test/login"

    if normalized_target == "UI":
        def _contains_any(text: str, keywords: List[str]) -> bool:
            normalized = (text or "").strip().lower()
            return any(k in normalized for k in keywords)

        def _build_steps(defaults: List[Dict[str, Any]], _hints: List[str]) -> List[Dict[str, Any]]:
            return [dict(s) for s in defaults]

        remember_keywords = [
            "remember me", "remember", "prefill", "pre-fill", "autofill", "auto fill",
            "persist", "cookie", "session restore",
            "记住我", "回填", "预填", "自动填充", "自动登录",
        ]
        negative_keywords = [
            "invalid", "wrong password", "error", "failed", "unauthorized", "401", "deny",
            "错误", "失败", "无效", "拒绝", "未授权", "异常",
        ]

        happy_points: List[str] = []
        negative_points: List[str] = []
        remember_points: List[str] = []

        for point in extracted_points:
            if _contains_any(point, remember_keywords):
                remember_points.append(point)
            elif _contains_any(point, negative_keywords):
                negative_points.append(point)
            else:
                happy_points.append(point)

        happy_defaults = [
            {"step_type": "UI", "action": "goto", "target": "browser", "value": base_login_url, "description": "Open login page"},
            {"step_type": "UI", "action": "assert", "target": "input[name='username']", "description": "Verify username input is visible"},
            {"step_type": "UI", "action": "assert", "target": "input[name='password']", "description": "Verify password input is visible"},
            {"step_type": "UI", "action": "type", "target": "input[name='username']", "value": "${TEST_USERNAME}", "description": "Enter valid username"},
            {"step_type": "UI", "action": "type", "target": "input[name='password']", "value": "${VALID_PASSWORD}", "description": "Enter valid password"},
            {"step_type": "UI", "action": "click", "target": "button[type='submit']", "description": "Click login"},
            {"step_type": "UI", "action": "wait", "target": "[data-testid='home-page']", "description": "Wait for redirect"},
            {"step_type": "UI", "action": "assert", "target": "location.pathname", "value": "/home", "description": "Verify URL redirected to home"},
            {"step_type": "UI", "action": "assert", "target": "[data-testid='user-nickname']", "description": "Verify nickname is visible"},
        ]
        negative_defaults = [
            {"step_type": "UI", "action": "goto", "target": "browser", "value": base_login_url, "description": "Open login page"},
            {"step_type": "UI", "action": "type", "target": "input[name='username']", "value": "${TEST_USERNAME}", "description": "Enter username"},
            {"step_type": "UI", "action": "type", "target": "input[name='password']", "value": "${INVALID_PASSWORD}", "description": "Enter invalid password"},
            {"step_type": "UI", "action": "click", "target": "button[type='submit']", "description": "Submit login"},
            {"step_type": "UI", "action": "wait", "target": "[data-testid='login-form']", "description": "Wait for error render"},
            {"step_type": "UI", "action": "assert", "target": "[data-testid='login-error']", "value": "Invalid username or password", "description": "Verify invalid password error message"},
        ]
        remember_defaults = [
            {"step_type": "UI", "action": "goto", "target": "browser", "value": base_login_url, "description": "Open login page"},
            {"step_type": "UI", "action": "assert", "target": "input[name='remember']", "description": "Verify remember-me checkbox is visible"},
            {"step_type": "UI", "action": "type", "target": "input[name='username']", "value": "${TEST_USERNAME}", "description": "Enter username"},
            {"step_type": "UI", "action": "type", "target": "input[name='password']", "value": "${VALID_PASSWORD}", "description": "Enter password"},
            {"step_type": "UI", "action": "click", "target": "input[name='remember']", "description": "Enable remember me"},
            {"step_type": "UI", "action": "click", "target": "button[type='submit']", "description": "Login"},
            {"step_type": "UI", "action": "wait", "target": "[data-testid='home-page']", "description": "Wait for home page"},
            {"step_type": "UI", "action": "click", "target": "[data-testid='logout']", "description": "Logout"},
            {"step_type": "UI", "action": "wait", "target": "[data-testid='login-form']", "description": "Wait for login page"},
            {"step_type": "UI", "action": "assert", "target": "input[name='username']", "value": "${TEST_USERNAME}", "description": "Verify username is prefilled"},
        ]

        return [
            {
                "scenario_id": f"SC-{uuid.uuid4().hex[:8]}",
                "name": "UI Happy Path Login",
                "priority": "P2",
                "description": "Fallback template for successful login flow",
                "steps": _build_steps(happy_defaults, happy_points),
            },
            {
                "scenario_id": f"SC-{uuid.uuid4().hex[:8]}",
                "name": "UI Negative Login",
                "priority": "P2",
                "description": "Fallback template for invalid credential handling",
                "steps": _build_steps(negative_defaults, negative_points),
            },
            {
                "scenario_id": f"SC-{uuid.uuid4().hex[:8]}",
                "name": "UI Remember Me",
                "priority": "P2",
                "description": "Fallback template for remember-me persistence",
                "steps": _build_steps(remember_defaults, remember_points),
            },
        ]

    steps = []
    step_type = "API" if normalized_target == "API" else "UI"
    for point in extracted_points[:8]:
        steps.append({"step_type": step_type, "description": point})

    return [
        {
            "scenario_id": f"SC-{uuid.uuid4().hex[:8]}",
            "name": f"[Fallback] {normalized_target or 'MIXED'} Scenario",
            "priority": "P1",
            "description": "Auto-generated fallback scenario when AutoGen path is unavailable",
            "steps": steps,
        }
    ]
# === Nodes ===

async def node_router(state: GraphState) -> Dict[str, Any]:
    """Determine if the input is OpenAPI/Swagger or standard PRD"""
    req_text = state.get("requirement_text", "").strip()
    is_swagger = False
    
    # Simple heuristic to guess if JSON/Swagger
    if req_text.startswith("{") or req_text.startswith("["):
        try:
            data = repair_json(req_text)
            if "openapi" in data or "swagger" in data or "paths" in data:
                is_swagger = True
        except Exception:
            pass
            
    logger.info(f"[Graph Router] is_swagger = {is_swagger}")
    return {"is_swagger": is_swagger, "revision_count": 0}

async def node_swagger_parser(state: GraphState) -> Dict[str, Any]:
    """Parse Swagger JSON into basic API scenarios"""
    logger.info("[Graph Node] Parsing Swagger/OpenAPI...")
    ai = get_ai_manager()
    prompt = f"Convert the following OpenAPI/Swagger schema into a list of automated API test scenarios. Extract endpoints, methods, and expected statuses.\n\nSchema:\n{state['requirement_text']}"
    messages = [
        Message(role="system", content="You are a senior API testing expert. Output a JSON object with a 'scenarios' list. Each scenario should have 'scenario_id' (string), 'name' (string), 'priority' (P0/P1/P2), 'description' (string), and 'steps' (a list of objects with 'step_type': 'API', 'method': 'GET/POST', 'url': '/api/...', 'description': 'summary')."),
        Message(role="user", content=prompt)
    ]
    try:
        response = await ai.invoke(AIModule.AGENT_NEURAL_MERGER, messages)
        data = repair_json(response.content)
        scenarios = data.get("scenarios", [])
        
        # Ensure scenario_ids
        for s in scenarios:
            if "scenario_id" not in s:
                s["scenario_id"] = f"SC-{uuid.uuid4().hex[:8]}"
                
        return {"scenarios": scenarios, "extracted_points": ["Parsed from OpenAPI structure directly."]}
    except Exception as e:
        logger.error(f"Swagger parse failed: {e}")
        return {"scenarios": [], "feedback": str(e)}

async def node_prd_extractor(state: GraphState) -> Dict[str, Any]:
    """Extract test points from PRD text"""
    logger.info("[Graph Node] Extracting test points from PRD...")
    ai = get_ai_manager()
    
    user_id = state.get("project_id", "default_user")
    project_id = state.get("project_id", "default_proj")
    
    memory_context = memory_base.search_memory(
        query=f"test preference and requirement analysis guidance: {state['requirement_text'][:200]}",
        user_id=user_id,
        project_id=project_id,
    )
    
    prompt = f"Extract the key business requirements and testing points from this PRD:\n{state['requirement_text']}\n\nTarget Type: {state.get('target_type', 'MIXED')}"
    if memory_context:
        prompt = f"{memory_context}\n\n{prompt}"
        
    messages = [
        Message(role="system", content="You are a strict QA requirement analyzer. Output ONLY clear, concise testing points as a JSON list of strings under the key 'points'. DO NOT add markdown markers outside the JSON."),
        Message(role="user", content=prompt)
    ]
    try:
        response = await ai.invoke(AIModule.AGENT_NEURAL_MERGER, messages)
        data = repair_json(response.content)
        points = data.get("points", [])
        logger.info(f"[Graph Node] Extracted {len(points)} points.")
        return {"extracted_points": points}
    except Exception as e:
        logger.error(f"PRD extraction failed: {e}")
        return {"extracted_points": []}

from app.services.neural_design.autogen_scenarist import run_scenarist_group_chat

async def node_scenarist(state: GraphState) -> Dict[str, Any]:
    """Generate test scenarios from extracted points via AutoGen Group Chat"""
    logger.info("[Graph Node] Entering AutoGen Multi-Agent Discussion Room...")
    
    extracted_points = state.get("extracted_points", [])
    requirement_text = state.get("requirement_text", "")
    target = state.get("target_type", "MIXED")
    context_info = state.get("context", "")
    
    user_id = state.get("project_id", "default_user")
    project_id = state.get("project_id", "default_proj")
    memory_context = memory_base.search_memory(
        query="business scenario generation guidance and testcase preferences",
        user_id=user_id,
        project_id=project_id,
    )
    
    feedback_str = f"Critical Critic Feedback to address (MUST FIX):\n{state.get('feedback', '')}" if state.get("feedback") else ""
    full_context = (
        f"[Original PRD - Highest Priority]\n{requirement_text}\n\n"
        f"[System Constraints and Context]\n{context_info}\n\n"
        f"{memory_context}\n\n{feedback_str}\n"
        "(If PRD explicitly specifies target URL/domain, always prioritize PRD URL over default Base URL.)"
    )
    
    try:
        final_merged_json = await run_scenarist_group_chat(
            extracted_points=extracted_points,
            target_type=target,
            target_url=state.get("target_url", ""),
            context=full_context
        )
        
        data = repair_json(final_merged_json)
        scenarios = data.get("scenarios", [])
        
        for s in scenarios:
            if "scenario_id" not in s:
                s["scenario_id"] = f"SC-{uuid.uuid4().hex[:8]}"
            if "[AutoGen-Merged]" not in s.get("name", ""):
                s["name"] = "[AutoGen-Merged] " + s.get("name", "Scenario")
                
        return {"scenarios": scenarios}
    except Exception as e:
        logger.error(f"Scenarist Agent Chat failed: {e}")
        fallback = _fallback_scenarios_from_points(
            extracted_points=extracted_points,
            target_type=target,
            target_url=state.get("target_url", ""),
        )
        if fallback:
            logger.warning(
                f"[Graph Node] Using fallback scenarios due to AutoGen failure, count={len(fallback)}"
            )
            return {"scenarios": fallback}
        return {"scenarios": state.get("scenarios", [])}

async def node_critic(state: GraphState) -> Dict[str, Any]:
    """Criticize generated scenarios"""
    logger.info(f"[Graph Node] Critic reviewing scenarios... (Revision {state.get('revision_count', 0)})")
    
    if not state.get("scenarios"):
        return {"feedback": "No scenarios were generated. Please extract points and try again.", "revision_count": state.get("revision_count", 0) + 1}
        
    ai = get_ai_manager()
    prompt = f"Review the generated test scenarios for quality and completeness:\n{json.dumps(state['scenarios'], ensure_ascii=False)}\n\nAre they logically sound? Do they match the Target Type '{state.get('target_type')}'? Output a JSON object with boolean 'approved'. If false, provide detailed string 'feedback' on what to fix."
    
    messages = [
        Message(role="system", content="You are a strict QA QA Lead Critic. Output a JSON object. If approved, set 'approved': true. If rejected, set 'approved': false and provide 'feedback' explaining what needs to be fixed."),
        Message(role="user", content=prompt)
    ]
    
    try:
        response = await ai.invoke(AIModule.AGENT_NEURAL_MERGER, messages)
        data = repair_json(response.content)
        
        is_approved = data.get("approved", False)
        feedback = data.get("feedback", "")
        
        if is_approved:
            logger.info("[Graph Node] Critic APPROVED.")
            return {"feedback": ""} # Cleared, meaning success
        else:
            logger.info(f"[Graph Node] Critic REJECTED. Feedback: {feedback}")
            return {"feedback": feedback, "revision_count": state.get("revision_count", 0) + 1}
    except Exception as e:
        logger.error(f"Critic failed: {e}")
        return {"feedback": ""} # Pass if critic breaks

from app.services.neural_design.autogen_editor import run_editor_agent

async def node_editor(state: GraphState) -> Dict[str, Any]:
    """Execute single-agent Editor to fix scenarios based on Critic feedback"""
    logger.info(f"[Graph Node] Editor Agent fixing scenarios... (Revision {state.get('revision_count', 0)})")
    
    scenarios = state.get("scenarios", [])
    feedback = state.get("feedback", "")
    context_info = state.get("context", "")
    
    if not scenarios or not feedback:
        return {} # Nothing to do
        
    try:
        final_merged_json = await run_editor_agent(
            scenarios=scenarios,
            feedback=feedback,
            context=context_info
        )
        
        data = repair_json(final_merged_json)
        updated_scenarios = data.get("scenarios", [])
        
        # Ensure we don't lose all our scenarios if editor breaks completely
        if not updated_scenarios:
            logger.warning("[Graph Node] Editor returned empty scenarios, retaining old ones.")
            return {"editor_output": final_merged_json}
            
        for s in updated_scenarios:
            if "scenario_id" not in s:
                s["scenario_id"] = f"SC-{uuid.uuid4().hex[:8]}"
            if "[Edited]" not in s.get("name", ""):
                 s["name"] = "[Edited] " + s.get("name", "Scenario")
                 
        return {"scenarios": updated_scenarios, "editor_output": final_merged_json}
    except Exception as e:
        logger.error(f"Editor Agent failed: {e}")
        return {}


# === Edges ===
def route_after_router(state: GraphState) -> str:
    if state.get("is_swagger"):
        return "swagger_parser"
    return "prd_extractor"

def route_after_critic(state: GraphState) -> str:
    # If approved (feedback is empty) or max revisions reached, end
    feedback = state.get("feedback")
    rev_count = state.get("revision_count", 0)
    
    if not feedback:
        return END
    if rev_count >= 2:
        logger.warning("[Graph Router] Max revisions reached. Forcing END.")
        return END
        
    return "editor"

# === Build Graph ===
def build_neural_design_graph():
    builder = StateGraph(GraphState)
    
    builder.add_node("router", node_router)
    builder.add_node("swagger_parser", node_swagger_parser)
    builder.add_node("prd_extractor", node_prd_extractor)
    builder.add_node("scenarist", node_scenarist)
    builder.add_node("critic", node_critic)
    builder.add_node("editor", node_editor)
    
    builder.add_edge(START, "router")
    
    builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            "swagger_parser": "swagger_parser",
            "prd_extractor": "prd_extractor"
        }
    )
    
    builder.add_edge("swagger_parser", "critic")
    
    builder.add_edge("prd_extractor", "scenarist")
    builder.add_edge("scenarist", "critic")
    
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            END: END,
            "editor": "editor"
        }
    )
    
    builder.add_edge("editor", "critic")
    
    return builder.compile()

neural_design_graph = build_neural_design_graph()

