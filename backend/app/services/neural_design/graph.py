import asyncio
import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.core.ai_client import Message, get_ai_manager
from app.core.ai_models import AIModule
from app.core.logging import logger
from app.core.memory_base import memory_base
from app.services.neural_design.analysis_progress import report_progress
from app.services.neural_design.autogen_editor import run_editor_agent
from app.services.neural_design.autogen_scenarist import run_scenarist_group_chat
from app.utils.json_repair import repair_json


class GraphState(TypedDict):
    project_id: str
    requirement_text: str
    target_type: str
    target_url: str
    context: str
    extracted_points: List[str]
    scenarios: List[Dict[str, Any]]
    feedback: str
    issues: List[str]
    approved: bool
    revision_count: int
    is_swagger: bool
    editor_output: str
    fallback_reason: str
    generation_source: str
    timings: Dict[str, float]


_URL_PATTERN = re.compile(r"https?://[^\s'\"<>)\]}]+", re.IGNORECASE)


def _normalize_critic_issues(data: Dict[str, Any]) -> List[str]:
    raw_issues = data.get("issues", [])
    if isinstance(raw_issues, list):
        issues = [str(issue).strip() for issue in raw_issues if str(issue).strip()]
        if issues:
            return issues

    feedback = str(data.get("feedback", "")).strip()
    if feedback:
        return [feedback]
    return []


def _with_timing(state: GraphState, key: str, elapsed_ms: float) -> Dict[str, float]:
    timings = dict(state.get("timings", {}))
    timings[key] = round(elapsed_ms, 2)
    return timings


def _truncate_text(text: str, max_chars: int) -> str:
    normalized = (text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 12].rstrip() + "\n...[truncated]"


def _trim_memory_context(text: str, max_chars: int = 1200) -> str:
    if not text:
        return ""
    return _truncate_text(text, max_chars)


def _extract_first_url(text: str) -> str:
    if not text:
        return ""
    match = _URL_PATTERN.search(text)
    if not match:
        return ""
    return match.group(0).rstrip(".,;)]}\"'")


def _resolve_effective_target_url(
    target_url: str = "",
    requirement_text: str = "",
    context: str = "",
    extracted_points: Optional[List[str]] = None,
) -> str:
    candidates = [
        target_url,
        requirement_text,
        context,
        "\n".join(extracted_points or []),
    ]
    for candidate in candidates:
        normalized = (candidate or "").strip()
        if not normalized:
            continue
        if normalized.startswith(("http://", "https://")):
            return normalized.rstrip(".,;)]}\"'")

        inferred = _extract_first_url(normalized)
        if inferred:
            return inferred
    return ""


def _limit_points(points: List[str], max_items: int = 12, max_chars_per_item: int = 180) -> List[str]:
    limited: List[str] = []
    for point in points[:max_items]:
        trimmed = _truncate_text(str(point), max_chars_per_item)
        if trimmed:
            limited.append(trimmed)
    return limited


def _fallback_scenarios_from_points(points: List[str], target_type: str) -> List[Dict[str, Any]]:
    limited_points = _limit_points(points)
    normalized_target = (target_type or "MIXED").upper()

    if normalized_target == "API":
        return [
            {
                "scenario_id": f"SC-{uuid.uuid4().hex[:8]}",
                "name": "[Fallback] API Scenario",
                "type": "API",
                "priority": "P2",
                "metadata": {"origin": "local_fallback"},
                "steps": [
                    {
                        "step_type": "API",
                        "description": point,
                        "method": "GET",
                        "url": "/",
                        "expected_status_code": 200,
                        "json_assertions": {},
                    }
                    for point in limited_points
                ],
            }
        ]

    def _matches(point: str, keywords: List[str]) -> bool:
        lowered = point.lower()
        return any(
            re.search(rf"\b{re.escape(keyword)}\b", lowered)
            for keyword in keywords
        )

    buckets = [
        ("UI Happy Path Login", ["valid", "visible", "redirect", "home", "success"]),
        ("UI Negative Login", ["invalid", "error", "fail", "wrong"]),
        ("UI Remember Me", ["remember", "prefill", "prefilled"]),
    ]
    scenarios: List[Dict[str, Any]] = []
    used_indexes: set[int] = set()

    for name, keywords in buckets:
        matched_points = [
            point
            for index, point in enumerate(limited_points)
            if index not in used_indexes and _matches(point, keywords)
        ]
        for index, point in enumerate(limited_points):
            if point in matched_points:
                used_indexes.add(index)
        if not matched_points and name == "UI Happy Path Login" and limited_points:
            matched_points = [limited_points[0]]
            used_indexes.add(0)
        if not matched_points:
            continue

        steps = []
        if name == "UI Happy Path Login":
            steps.append({"step_type": "UI", "action": "goto", "target": "/", "description": matched_points[0]})
            steps.append({"step_type": "UI", "action": "input", "target": "input[name='username']", "description": matched_points[0]})
        elif name == "UI Negative Login":
            steps.append({"step_type": "UI", "action": "click", "target": "button[type='submit']", "description": matched_points[0]})
            steps.append({"step_type": "UI", "action": "assert_visible", "target": "[data-testid='login-error']", "description": matched_points[0]})
        else:
            steps.append({"step_type": "UI", "action": "click", "target": "input[name='remember']", "description": matched_points[0]})

        scenarios.append(
            {
                "scenario_id": f"SC-{uuid.uuid4().hex[:8]}",
                "name": name,
                "type": "UI",
                "priority": "P2",
                "metadata": {"origin": "local_fallback"},
                "steps": steps,
            }
        )

    return scenarios


def _build_scenario_summary(
    scenarios: List[Dict[str, Any]],
    *,
    max_scenarios: int = 5,
    max_steps: int = 6,
) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for scenario in scenarios[:max_scenarios]:
        steps = scenario.get("steps", [])
        step_summaries: List[Dict[str, Any]] = []
        for step in steps[:max_steps]:
            step_type = str(step.get("step_type") or scenario.get("type") or "").upper()
            step_summaries.append(
                {
                    "step_type": step_type,
                    "action": step.get("action"),
                    "method": step.get("method"),
                    "target": _truncate_text(str(step.get("target") or ""), 80) if step.get("target") else "",
                    "url": _truncate_text(str(step.get("url") or step.get("url_path") or ""), 120)
                    if (step.get("url") or step.get("url_path"))
                    else "",
                    "has_value": bool(step.get("value")),
                    "description": _truncate_text(str(step.get("description") or ""), 100),
                }
            )

        summary.append(
            {
                "name": scenario.get("name", "Scenario"),
                "priority": scenario.get("priority", ""),
                "type": scenario.get("type", ""),
                "step_count": len(steps),
                "steps": step_summaries,
            }
        )
    return summary


async def node_router(state: GraphState) -> Dict[str, Any]:
    """Determine if the input is OpenAPI/Swagger or standard PRD."""
    req_text = state.get("requirement_text", "").strip()
    is_swagger = False

    if req_text.startswith("{") or req_text.startswith("["):
        try:
            data = repair_json(req_text)
            if "openapi" in data or "swagger" in data or "paths" in data:
                is_swagger = True
        except Exception:
            pass

    logger.info(f"[Graph Router] is_swagger = {is_swagger}")
    return {"is_swagger": is_swagger, "revision_count": 0, "issues": [], "approved": False}


async def node_swagger_parser(state: GraphState) -> Dict[str, Any]:
    """Parse Swagger JSON into basic API scenarios."""
    logger.info("[Graph Node] Parsing Swagger/OpenAPI...")
    ai = get_ai_manager()
    prompt = (
        "Convert the following OpenAPI/Swagger schema into a list of automated API test "
        f"scenarios. Extract endpoints, methods, and expected statuses.\n\nSchema:\n{state['requirement_text']}"
    )
    messages = [
        Message(
            role="system",
            content=(
                "You are a senior API testing expert. Output a JSON object with a 'scenarios' list. "
                "Each scenario should have 'scenario_id' (string), 'name' (string), "
                "'priority' (P0/P1/P2), 'description' (string), and 'steps' "
                "(a list of objects with 'step_type': 'API', 'method': 'GET/POST', "
                "'url': '/api/...', 'description': 'summary')."
            ),
        ),
        Message(role="user", content=prompt),
    ]
    try:
        response = await ai.invoke(AIModule.AGENT_NEURAL_MERGER, messages)
        data = repair_json(response.content)
        scenarios = data.get("scenarios", [])

        for scenario in scenarios:
            if "scenario_id" not in scenario:
                scenario["scenario_id"] = f"SC-{uuid.uuid4().hex[:8]}"

        return {"scenarios": scenarios, "extracted_points": ["Parsed from OpenAPI structure directly."]}
    except Exception as exc:
        logger.error(f"Swagger parse failed: {exc}")
        return {"scenarios": [], "feedback": str(exc)}


async def node_prd_extractor(state: GraphState) -> Dict[str, Any]:
    """Extract test points from PRD text."""
    logger.info("[Graph Node] Extracting test points from PRD...")
    report_progress("extracting_points", 25)
    ai = get_ai_manager()
    requirement_excerpt = _truncate_text(state.get("requirement_text", ""), 8000)

    user_id = state.get("project_id", "default_user")
    project_id = state.get("project_id", "default_proj")

    memory_context = memory_base.search_memory(
        query=f"test preference and requirement analysis guidance: {state['requirement_text'][:200]}",
        user_id=user_id,
        project_id=project_id,
    )
    memory_context = _trim_memory_context(memory_context, 1200)

    prompt = (
        "Extract the key business requirements and testing points from this PRD excerpt:\n"
        f"{requirement_excerpt}\n\nTarget Type: {state.get('target_type', 'MIXED')}"
    )
    if memory_context:
        prompt = f"[Memory Hints]\n{memory_context}\n\n{prompt}"

    messages = [
        Message(
            role="system",
            content=(
                "You are a strict QA requirement analyzer. Output ONLY clear, concise testing points "
                "as a JSON list of strings under the key 'points'. DO NOT add markdown markers outside the JSON."
            ),
        ),
        Message(role="user", content=prompt),
    ]
    try:
        response = await ai.invoke(AIModule.AGENT_NEURAL_MERGER, messages)
        data = repair_json(response.content)
        points = data.get("points", [])
        logger.info(f"[Graph Node] Extracted {len(points)} points.")
        return {"extracted_points": points}
    except Exception as exc:
        logger.error(f"PRD extraction failed: {exc}")
        return {"extracted_points": []}


async def node_scenarist(state: GraphState) -> Dict[str, Any]:
    """Generate test scenarios from extracted points via AutoGen Group Chat."""
    logger.info("[Graph Node] Entering AutoGen Multi-Agent Discussion Room...")
    report_progress("generating_scenarios", 60)
    started_at = time.perf_counter()

    extracted_points = _limit_points(state.get("extracted_points", []), max_items=12, max_chars_per_item=180)
    requirement_excerpt = _truncate_text(state.get("requirement_text", ""), 1200)
    target = state.get("target_type", "MIXED")
    context_info = _truncate_text(state.get("context", ""), 2000)
    effective_target_url = _resolve_effective_target_url(
        target_url=state.get("target_url", ""),
        requirement_text=state.get("requirement_text", ""),
        context=state.get("context", ""),
        extracted_points=extracted_points,
    )

    user_id = state.get("project_id", "default_user")
    project_id = state.get("project_id", "default_proj")
    memory_context = memory_base.search_memory(
        query="business scenario generation guidance and testcase preferences",
        user_id=user_id,
        project_id=project_id,
    )
    memory_context = _trim_memory_context(memory_context, 1200)

    feedback_text = _truncate_text(state.get("feedback", ""), 600) if state.get("feedback") else ""
    context_sections: List[str] = [
        f"[Target Type]\n{target}",
        f"[Target URL]\n{effective_target_url or 'N/A'}",
        "[Rule]\nIf the PRD specifies a target URL/domain, always prioritize that over any default base URL.",
    ]
    if requirement_excerpt:
        context_sections.append(f"[PRD Excerpt]\n{requirement_excerpt}")
    if context_info:
        context_sections.append(f"[Context Summary]\n{context_info}")
    if memory_context:
        context_sections.append(f"[Memory Hints]\n{memory_context}")
    if feedback_text:
        context_sections.append(f"[Critic Issues]\n{feedback_text}")
    full_context = "\n\n".join(context_sections)

    logger.info(
        f"[Graph Node] Scenarist input compressed: points={len(extracted_points)}, "
        f"context_chars={len(full_context)}, memory_chars={len(memory_context)}"
    )

    try:
        final_merged_json = await run_scenarist_group_chat(
            extracted_points=extracted_points,
            target_type=target,
            target_url=effective_target_url,
            context=full_context,
        )

        data = repair_json(final_merged_json)
        scenarios = data.get("scenarios", [])
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        for scenario in scenarios:
            if "scenario_id" not in scenario:
                scenario["scenario_id"] = f"SC-{uuid.uuid4().hex[:8]}"
            if "[AutoGen-Merged]" not in scenario.get("name", ""):
                scenario["name"] = "[AutoGen-Merged] " + scenario.get("name", "Scenario")

        logger.info(f"[Graph Node] Scenarist produced {len(scenarios)} scenarios in {elapsed_ms:.2f}ms.")
        return {
            "scenarios": scenarios,
            "generation_source": "autogen_scenarist",
            "fallback_reason": "",
            "timings": _with_timing(state, "scenarist_ms", elapsed_ms),
        }
    except ValueError as exc:
        logger.error(f"Scenarist output parsing failed: {exc}")
        raise RuntimeError("scenarist_invalid_json") from exc
    except Exception as exc:
        logger.error(f"Scenarist Agent Chat failed: {exc}")
        raise RuntimeError("scenarist_exception") from exc


async def node_critic(state: GraphState) -> Dict[str, Any]:
    """Criticize generated scenarios."""
    logger.info(f"[Graph Node] Critic reviewing scenarios... (Revision {state.get('revision_count', 0)})")
    report_progress("validating_schema", 75)

    scenarios = state.get("scenarios", [])
    target_type = (state.get("target_type") or "").upper()

    if not scenarios:
        issues = ["No scenarios were generated. Please extract points and try again."]
        return {
            "feedback": "\n".join(issues),
            "issues": issues,
            "approved": False,
            "revision_count": state.get("revision_count", 0) + 1,
        }

    ai = get_ai_manager()
    report_progress("reviewing", 90)
    scenario_summary = _build_scenario_summary(scenarios)
    messages = [
        Message(
            role="system",
            content="""
You are a QA execution critic.

Your job is to check whether the scenarios are directly executable.

Check only these rules:
1. Every scenario matches the target type.
2. Every step has the minimum required execution fields.
3. Steps are unambiguous enough for automation.
4. Do not judge writing style or business completeness unless it blocks execution.

Output JSON only:
{
  "approved": true,
  "issues": []
}

or

{
  "approved": false,
  "issues": [
    "short issue 1",
    "short issue 2"
  ]
}

Rules:
- Keep issues short and concrete.
- No markdown.
- No long explanations.
- If executable, return approved=true and issues=[].
- Assume all human-facing fields should default to Simplified Chinese:
  scenario name, scenario description, and step description.
- If those fields are mainly English without a clear product-term exception,
  add an issue asking to rewrite them in Simplified Chinese.
""".strip(),
        ),
        Message(
            role="user",
            content=(
                f"Target Type: {target_type or state.get('target_type')}\n\n"
                "Language Rule: titles, descriptions, and step descriptions should default to "
                "Simplified Chinese. Keep JSON keys and technical fields in English.\n\n"
                f"Scenario Summary:\n{json.dumps(scenario_summary, ensure_ascii=False)}"
            ),
        ),
    ]

    try:
        response = await ai.invoke(AIModule.AGENT_NEURAL_MERGER, messages)
        data = repair_json(response.content)

        is_approved = data.get("approved", False)
        issues = _normalize_critic_issues(data)
        feedback = "\n".join(issues)

        if is_approved:
            logger.info("[Graph Node] Critic APPROVED.")
            return {"feedback": "", "issues": [], "approved": True}

        logger.info(f"[Graph Node] Critic REJECTED. Issues: {issues}")
        return {
            "feedback": feedback,
            "issues": issues,
            "approved": False,
            "revision_count": state.get("revision_count", 0) + 1,
        }
    except Exception as exc:
        logger.error(f"Critic failed: {exc}")
        raise RuntimeError("critic_exception") from exc


async def node_editor(state: GraphState) -> Dict[str, Any]:
    """Execute single-agent Editor to fix scenarios based on Critic feedback."""
    logger.info(f"[Graph Node] Editor Agent fixing scenarios... (Revision {state.get('revision_count', 0)})")

    scenarios = state.get("scenarios", [])
    issues = state.get("issues", [])
    target_type = (state.get("target_type") or "").upper()

    if not scenarios or not issues:
        return {}

    try:
        final_merged_json = await run_editor_agent(
            scenarios=scenarios,
            issues=issues,
            target_type=target_type or "MIXED",
        )

        if not final_merged_json.strip():
            logger.warning("[Graph Node] Editor returned empty output, keeping current scenarios and ending revision loop.")
            return {
                "feedback": "",
                "issues": [],
                "approved": True,
                "editor_output": "",
            }

        data = repair_json(final_merged_json)
        updated_scenarios = data.get("scenarios", [])

        if not updated_scenarios:
            logger.warning("[Graph Node] Editor returned empty scenarios, keeping current scenarios and ending revision loop.")
            return {
                "feedback": "",
                "issues": [],
                "approved": True,
                "editor_output": final_merged_json,
            }

        for scenario in updated_scenarios:
            if "scenario_id" not in scenario:
                scenario["scenario_id"] = f"SC-{uuid.uuid4().hex[:8]}"
            if "[Edited]" not in scenario.get("name", ""):
                scenario["name"] = "[Edited] " + scenario.get("name", "Scenario")

        return {
            "scenarios": updated_scenarios,
            "feedback": "",
            "issues": [],
            "approved": True,
            "editor_output": final_merged_json,
        }
    except Exception as exc:
        logger.error(f"Editor Agent failed: {exc}")
        raise RuntimeError("editor_exception") from exc


def route_after_router(state: GraphState) -> str:
    if state.get("is_swagger"):
        return "swagger_parser"
    return "prd_extractor"


def route_after_critic(state: GraphState) -> str:
    approved = state.get("approved", False)
    feedback = state.get("feedback")
    rev_count = state.get("revision_count", 0)

    if approved or not feedback:
        return END
    if rev_count >= 2:
        logger.warning("[Graph Router] Max revisions reached. Forcing END.")
        return END

    return "editor"


def route_after_editor(state: GraphState) -> str:
    if state.get("editor_output"):
        return "critic"
    return END


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
            "prd_extractor": "prd_extractor",
        },
    )

    builder.add_edge("swagger_parser", "critic")
    builder.add_edge("prd_extractor", "scenarist")
    builder.add_edge("scenarist", "critic")

    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            END: END,
            "editor": "editor",
        },
    )

    builder.add_conditional_edges(
        "editor",
        route_after_editor,
        {
            "critic": "critic",
            END: END,
        },
    )

    return builder.compile()


neural_design_graph = build_neural_design_graph()
