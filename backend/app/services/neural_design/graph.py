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

class GraphState(TypedDict):
    project_id: str
    requirement_text: str
    target_type: str
    context: str
    
    # Internal state
    extracted_points: List[str]
    scenarios: List[Dict[str, Any]]
    feedback: str
    revision_count: int
    is_swagger: bool

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
        response = await ai.invoke(AIModule.NEURAL_SCENARIO_GENERATOR, messages)
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
    prompt = f"Extract the key business requirements and testing points from this PRD:\n{state['requirement_text']}\n\nTarget Type: {state.get('target_type', 'MIXED')}"
    messages = [
        Message(role="system", content="You are a strict QA requirement analyzer. Output ONLY clear, concise testing points as a JSON list of strings under the key 'points'. DO NOT add markdown markers outside the JSON."),
        Message(role="user", content=prompt)
    ]
    try:
        response = await ai.invoke(AIModule.NEURAL_SCENARIO_GENERATOR, messages)
        data = repair_json(response.content)
        points = data.get("points", [])
        logger.info(f"[Graph Node] Extracted {len(points)} points.")
        return {"extracted_points": points}
    except Exception as e:
        logger.error(f"PRD extraction failed: {e}")
        return {"extracted_points": []}

async def node_scenarist(state: GraphState) -> Dict[str, Any]:
    """Generate test scenarios from extracted points"""
    logger.info("[Graph Node] Generating scenarios...")
    ai = get_ai_manager()
    
    feedback_str = f"Critical Critic Feedback to address (MUST FIX):\n{state.get('feedback', '')}" if state.get("feedback") else "No previous feedback."
    
    prompt = f"""
    Context Info: {state.get('context', '')}
    Target Testing Type: {state.get('target_type', 'MIXED')}
    
    Extracted Test Points:
    {json.dumps(state.get('extracted_points', []), ensure_ascii=False)}
    
    {feedback_str}
    
    Generate deep, robust test scenarios covering the points. Return a JSON object with a 'scenarios' list.
    Every scenario must include: 'name', 'priority' (e.g. P0, P1), 'description', and 'steps' (list of detailed steps).
    """
    
    messages = [
        Message(role="system", content="You are an elite QA Scenarist. Generate a JSON with a 'scenarios' list."),
        Message(role="user", content=prompt)
    ]
    
    try:
        response = await ai.invoke(AIModule.NEURAL_SCENARIO_GENERATOR, messages)
        data = repair_json(response.content)
        
        scenarios = data.get("scenarios", [])
        for s in scenarios:
            if "scenario_id" not in s:
                s["scenario_id"] = f"SC-{uuid.uuid4().hex[:8]}"
                
        return {"scenarios": scenarios}
    except Exception as e:
        logger.error(f"Scenarist failed: {e}")
        return {"scenarios": state.get("scenarios", [])} # fallback to old if failed

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
        response = await ai.invoke(AIModule.NEURAL_SCENARIO_GENERATOR, messages)
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
        
    return "scenarist"

# === Build Graph ===
def build_neural_design_graph():
    builder = StateGraph(GraphState)
    
    builder.add_node("router", node_router)
    builder.add_node("swagger_parser", node_swagger_parser)
    builder.add_node("prd_extractor", node_prd_extractor)
    builder.add_node("scenarist", node_scenarist)
    builder.add_node("critic", node_critic)
    
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
            "scenarist": "scenarist"
        }
    )
    
    return builder.compile()

neural_design_graph = build_neural_design_graph()
