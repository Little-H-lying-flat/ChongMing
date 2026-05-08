"""
Neural Design Service

Convert requirements into structured scenarios and refined test cases.
"""

import json
import logging
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from app.core.ai_client import AIClientManager, Message, get_ai_manager
from app.core.ai_models import AIModule
from app.core.prompts.neural_design import (
    CRITIC_SYSTEM_PROMPT,
    CRITIC_USER_TEMPLATE,
    PRD_ANALYSIS_SYSTEM_PROMPT,
    PRD_ANALYSIS_USER_TEMPLATE,
    TC_GENERATION_SYSTEM_PROMPT,
    TC_GENERATION_USER_TEMPLATE,
)
from app.services.left_pupil.knowledge_retriever import KnowledgeRetriever
from app.services.left_pupil.rag_retriever import RagRetriever
from app.services.neural_design.analysis_cache import (
    build_analysis_cache_key,
    get_cached_analysis,
    set_cached_analysis,
)
from app.services.neural_design.analysis_progress import (
    reset_progress_reporter,
    set_progress_reporter,
    report_progress,
)
from app.services.neural_design.graph import neural_design_graph
from app.services.neural_design.models import (
    DesignRequest,
    DraftTestCase,
    RefinedApiStep,
    RefinedAssertionSpec,
    RefinedRequestSpec,
    RefinedTestCase,
    RefinedUiStep,
)
from app.utils.json_repair import repair_json

logger = logging.getLogger(__name__)
_VARIABLE_REF_PATTERN = re.compile(r"\$\{([^}]+)\}|\{\{([^}]+)\}\}")


def _collect_required_variables(value: Any, bucket: set[str]) -> None:
    if isinstance(value, str):
        for match in _VARIABLE_REF_PATTERN.finditer(value):
            variable_name = (match.group(1) or match.group(2) or "").strip()
            if variable_name:
                bucket.add(variable_name)
        return

    if isinstance(value, dict):
        for nested_value in value.values():
            _collect_required_variables(nested_value, bucket)
        return

    if isinstance(value, list):
        for item in value:
            _collect_required_variables(item, bucket)


def _annotate_required_variables(scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for scenario in scenarios:
        required_variables: set[str] = set()
        _collect_required_variables(scenario.get("steps", []), required_variables)
        if required_variables:
            scenario["required_variables"] = sorted(required_variables)
        else:
            scenario["required_variables"] = []
    return scenarios


class DesignService:
    """
    Core service for neural design flows.

    Responsibilities:
    1. analyze_requirement: requirement -> scenarios
    2. generate_test_case: scenario -> refined executable test case
    """

    def __init__(
        self,
        ai_manager: Optional[AIClientManager] = None,
        retriever: Optional[RagRetriever] = None,
        knowledge_retriever: Optional[KnowledgeRetriever] = None,
    ):
        self.ai = ai_manager or get_ai_manager()
        self._retriever = retriever
        self._knowledge_retriever = knowledge_retriever

    @property
    def retriever(self) -> RagRetriever:
        if not self._retriever:
            self._retriever = RagRetriever()
        return self._retriever

    @property
    def knowledge_retriever(self) -> KnowledgeRetriever:
        if not self._knowledge_retriever:
            self._knowledge_retriever = KnowledgeRetriever()
        return self._knowledge_retriever

    async def analyze_requirement(
        self,
        request: DesignRequest,
        progress_callback: Optional[Callable[[str, int, Optional[Dict[str, Any]]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze requirements and extract test scenarios through the LangGraph flow.
        """
        logger.info(f"Requirement analysis started. project={request.project_id}")

        started_at = time.perf_counter()
        reporter_token = set_progress_reporter(progress_callback)
        cache_key = build_analysis_cache_key(request)
        report_progress("cache_lookup", 10)
        try:
            cached_result = get_cached_analysis(cache_key)
            if cached_result:
                cached_source = cached_result.get("generation_source", "")
                cached_scenarios = cached_result.get("scenarios", [])
                if cached_source == "fallback" or any(
                    (scenario.get("metadata") or {}).get("origin") == "local_fallback"
                    for scenario in cached_scenarios
                    if isinstance(scenario, dict)
                ):
                    logger.info("Requirement analysis cache hit ignored because it contains legacy local fallback scenarios.")
                else:
                    scenarios = _annotate_required_variables(cached_scenarios)
                    timings = cached_result.get("timings", {})
                    report_progress(
                        "completed",
                        100,
                        {
                            "source": cached_result.get("generation_source", "cache"),
                            "fallback_reason": cached_result.get("fallback_reason", ""),
                            "timings": timings,
                        },
                    )
                    logger.info(
                        f"Requirement analysis cache hit. scenarios={len(scenarios)}, "
                        f"source={cached_result.get('generation_source', 'cache')}, "
                        f"fallback_reason={cached_result.get('fallback_reason', 'none') or 'none'}, "
                        f"timings={timings}"
                    )
                    return scenarios

            constraint = ""
            if request.target_type == "API":
                constraint = (
                    "Absolute rule: generate only HTTP/API-oriented test steps. "
                    "Do not include browser DOM or UI click operations."
                )
            elif request.target_type == "UI":
                constraint = (
                    "Absolute rule: generate only browser-based UI automation steps. "
                    "Do not include raw HTTP/API calls."
                )
            elif request.target_type == "MIXED":
                constraint = (
                    "You are a full-stack QA engineer. Combine API and UI steps "
                    "only when the requirement needs both."
                )

            initial_state = {
                "project_id": request.project_id,
                "requirement_text": request.requirement_text,
                "target_type": request.target_type,
                "target_url": request.target_url or "",
                "context": (request.context or "No additional context") + f"\n\nConstraints:\n{constraint}",
                "extracted_points": [],
                "scenarios": [],
                "feedback": "",
                "issues": [],
                "approved": False,
                "revision_count": 0,
                "is_swagger": False,
                "editor_output": "",
                "fallback_reason": "",
                "generation_source": "",
                "timings": {},
            }

            try:
                final_state = await neural_design_graph.ainvoke(initial_state)
                scenarios = _annotate_required_variables(final_state.get("scenarios", []))
                generation_source = final_state.get("generation_source", "unknown")
                fallback_reason = final_state.get("fallback_reason", "")
                timings = dict(final_state.get("timings", {}))
                timings["total_ms"] = round((time.perf_counter() - started_at) * 1000, 2)

                set_cached_analysis(
                    cache_key,
                    {
                        "scenarios": scenarios,
                        "generation_source": generation_source,
                        "fallback_reason": fallback_reason,
                        "timings": timings,
                    },
                )
                report_progress(
                    "completed",
                    100,
                    {
                        "source": generation_source,
                        "fallback_reason": fallback_reason,
                        "timings": timings,
                    },
                )

                logger.info(
                    f"Requirement analysis completed with {len(scenarios)} scenarios. "
                    f"source={generation_source}, fallback_reason={fallback_reason or 'none'}, timings={timings}"
                )
                return scenarios

            except Exception as e:
                logger.error(f"Requirement analysis failed: {e}")
                raise RuntimeError(f"Requirement analysis failed: {str(e)}") from e
        finally:
            reset_progress_reporter(reporter_token)

    async def generate_test_case(self, scenario: Dict[str, Any], project_id: str) -> RefinedTestCase:
        """
        Generate a refined executable test case from a scenario.

        Flow: Retrieve -> Draft -> Critic -> Refine
        """
        scenario_name = scenario.get("name", "Unnamed Scenario")
        logger.info(f"Generating test case for scenario: {scenario_name}")

        steps_desc = " ".join([s.get("description", "") for s in scenario.get("steps", [])])
        query = f"{scenario.get('description', '')} {steps_desc}"
        relevant_apis = await self.retriever.retrieve(query, project_id)

        api_context_str = "\n".join(
            [f"- {api.method} {api.path}: {api.metadata.get('summary', '')}" for api in relevant_apis]
        )
        if not api_context_str:
            api_context_str = "No concrete API definitions found. Generate using standard RESTful conventions."

        knowledge_context = await self.knowledge_retriever.retrieve(query, project_id)
        knowledge_str = "\n".join([f"- {k.content}" for k in knowledge_context])
        if not knowledge_str:
            knowledge_str = "No additional domain knowledge found."

        user_content = TC_GENERATION_USER_TEMPLATE.format(
            scenario_description=json.dumps(scenario, ensure_ascii=False),
            available_apis=api_context_str,
            domain_knowledge=knowledge_str,
        )

        messages = [
            Message(role="system", content=TC_GENERATION_SYSTEM_PROMPT),
            Message(role="user", content=user_content),
        ]

        draft_data = await self._invoke_with_retry(messages, AIModule.AGENT_NEURAL_ADMIN)

        try:
            critic_user_content = CRITIC_USER_TEMPLATE.format(
                draft_test_case=json.dumps(draft_data, ensure_ascii=False, indent=2)
            )
            critic_messages = [
                Message(role="system", content=CRITIC_SYSTEM_PROMPT),
                Message(role="user", content=critic_user_content),
            ]

            logger.info("Running critic self-review for generated test case.")
            critic_response = await self.ai.invoke(
                module=AIModule.AGENT_NEURAL_ADMIN,
                messages=critic_messages,
            )

            try:
                critic_data = self._parse_json(critic_response.content)
                if "steps" in critic_data and isinstance(critic_data["steps"], list):
                    logger.info("Critic returned a corrected test case. Applying correction.")
                    draft_data = critic_data
                else:
                    logger.info("Critic returned valid JSON but not a test case. Keeping draft.")
            except Exception:
                logger.debug("Critic output was not valid JSON. Ignoring correction.")

        except Exception as e:
            logger.warning(f"Critic step failed, falling back to original draft: {e}")

        try:
            refined_case = self._convert_draft_to_refined(draft_data)
            logger.info(f"Test case generated successfully: {refined_case.id} - {refined_case.name}")
            return refined_case
        except Exception as e:
            logger.error(f"Failed to convert draft test case: {e}")
            logger.error(f"Draft Data: {json.dumps(draft_data, ensure_ascii=False)}")
            raise ValueError("Generated test case format is invalid and cannot be converted to API-IR") from e

    async def _invoke_with_retry(
        self,
        messages: List[Message],
        module: AIModule,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Invoke the LLM with semantic retry on JSON parse failures.
        """
        current_messages = messages.copy()

        for attempt in range(max_retries + 1):
            try:
                response = await self.ai.invoke(module, current_messages)
                return self._parse_json(response.content)
            except ValueError as e:
                logger.warning(f"JSON parsing failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    current_messages.append(Message(role="assistant", content=response.content))
                    current_messages.append(
                        Message(
                            role="user",
                            content=f"JSON Parse Error: {str(e)}. Please fix the JSON and output ONLY the JSON object.",
                        )
                    )
                else:
                    raise
            except Exception as e:
                logger.error(f"LLM invocation failed critically: {e}")
                raise

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM output robustly.
        """
        try:
            return repair_json(text)
        except Exception as e:
            logger.error(f"Final JSON parsing failed: {text[:100]}...")
            raise ValueError(f"Invalid JSON: {str(e)}") from e

    def _convert_draft_to_refined(self, draft: Dict[str, Any]) -> RefinedTestCase:
        """
        Convert draft JSON into a RefinedTestCase object.
        """

        def _normalize_ui_action(raw_action: str) -> str:
            action = (raw_action or "").strip().lower()
            if not action:
                return "click"

            alias_map = {
                "open": "goto",
                "open_page": "goto",
                "navigate": "goto",
                "visit": "goto",
                "tap": "click",
                "press": "click",
                "submit": "click",
                "input": "type",
                "fill": "type",
                "enter": "type",
                "check": "assert",
                "verify": "assert",
                "validate": "assert",
                "assert_visible": "assert",
                "sleep": "wait",
                "pause": "wait",
                "delay": "wait",
                "resize": "wait",
                "swipe": "scroll",
                "drag": "scroll",
            }
            normalized = alias_map.get(action, action)
            allowed = {"goto", "click", "type", "assert", "screenshot", "wait", "scroll", "hover"}
            if normalized not in allowed:
                logger.warning(f"Unknown UI action '{raw_action}', fallback to 'click'")
                return "click"
            return normalized

        steps_data = draft.get("steps", [])
        if not steps_data:
            raise ValueError("Generated test case does not contain any steps")

        refined_steps = []
        for step in steps_data:
            step_type = step.get("step_type", "API").upper()
            step_id = step.get("step_id") or uuid.uuid4().hex[:8]

            if step_type == "UI":
                refined_step = RefinedUiStep(
                    id=step_id,
                    name=step.get("intent") or "UI Step",
                    step_type="UI",
                    description=step.get("description", ""),
                    action=_normalize_ui_action(step.get("action", "click")),
                    target=step.get("target", "unknown"),
                    value=step.get("value"),
                    dependencies=step.get("dependencies", []),
                )
            else:
                req_spec = RefinedRequestSpec(
                    method=step.get("method", "GET").upper(),
                    url=step.get("url_path", "/"),
                    body=step.get("input_data"),
                )

                expected_status = step.get("expected_status_code", 200)
                json_asserts = step.get("json_assertions") or {}

                refined_step = RefinedApiStep(
                    id=step_id,
                    name=step.get("intent") or "API Step",
                    step_type="API",
                    description=step.get("description", ""),
                    request=req_spec,
                    expected_status_code=int(expected_status),
                    json_assertions=json_asserts,
                    extract=step.get("extract", {}),
                )

            refined_steps.append(refined_step)

        return RefinedTestCase(
            id=uuid.uuid4().hex[:8],
            name=draft.get("case_name", "Generated Case"),
            description=draft.get("description", ""),
            steps=refined_steps,
            metadata={"origin": "neural_design"},
        )
