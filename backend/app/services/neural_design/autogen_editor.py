import json
import logging
from typing import Any, Dict, List

from app.core.ai_client import Message, get_ai_manager
from app.core.ai_models import AIModule

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start:end + 1]


async def run_editor_agent(
    scenarios: List[Dict[str, Any]],
    issues: List[str],
    target_type: str,
) -> str:
    """
    Repair generated scenarios with a single standard LLM call.

    This avoids AutoGen's interactive session management, which is unstable in
    non-interactive service processes on Windows.
    """
    logger.info("[Editor] Starting scenario correction.")
    ai = get_ai_manager()

    scenarios_str = json.dumps(scenarios, ensure_ascii=False, indent=2)
    issues_str = json.dumps(issues or [], ensure_ascii=False, indent=2)
    messages = [
        Message(
            role="system",
            content="""
You are a JSON repair editor for QA scenarios.

Task:
Repair the scenarios so they become executable.

Rules:
1. Output exactly one valid JSON object with a top-level key `scenarios`.
2. Do not output markdown or explanations.
3. Keep the original scenario intent.
4. Fix only the listed issues.
5. For UI scenarios, each step should use explicit fields:
   - step_type
   - action
   - target
   - value
   - description
6. For API scenarios, keep method, url, and assertions explicit.
7. If a field is unknown, keep the step minimal and executable instead of inventing extra business logic.
8. Field names must stay in English JSON keys, but all user-facing text values should default to Simplified Chinese.
9. Scenario `name`, scenario `description`, and each step `description` must be in Simplified Chinese unless the input already contains a required product term in English.
10. Do not translate technical selectors, URLs, methods, payload keys, or assertion paths.
""".strip(),
        ),
        Message(
            role="user",
            content=f"""
Target Type: {target_type}

Issues:
{issues_str}

Scenarios:
{scenarios_str}

Return corrected JSON only.
Default all scenario titles, scenario descriptions, and step descriptions to Simplified Chinese.
""".strip(),
        ),
    ]

    try:
        response = await ai.invoke(
            module=AIModule.AGENT_NEURAL_ADMIN,
            messages=messages,
        )
        final_output = _extract_json_object(response.content)
        logger.info("[Editor] Correction finished.")
        return final_output
    except Exception as exc:
        logger.error(f"[Editor] Failed to correct scenarios: {exc}")
        return ""
