from typing import Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.ai_client import Message, get_ai_manager
from app.core.ai_models import AIModule
from app.core.config import settings
from app.models.visual_ui import VisualUseCase, VisualStep, VisualStepAction, VisualUseCaseStatus
from app.schemas.visual_ui import (
    VisualStepCreate,
    VisualUIDraftRequest,
    VisualUIDraftResponse,
    VisualUseCaseCreate,
    VisualUseCaseUpdate,
)
from app.utils.json_repair import repair_json


class VisualUIService:
    @staticmethod
    async def generate_draft(data: VisualUIDraftRequest) -> VisualUIDraftResponse:
        prompt = data.prompt.strip()
        if not prompt:
            return VisualUIDraftResponse(status="needs_clarification", questions=["请描述要生成的 UI 测试流程。"])

        response = await get_ai_manager().invoke(
            AIModule.AGENT_RIGHT_VISUAL,
            [
                Message(role="system", content=VisualUIService._draft_system_prompt()),
                Message(role="user", content=VisualUIService._draft_user_prompt(data, prompt)),
            ],
            model_override=settings.VISUAL_UI_DRAFT_MODEL or None,
            temperature=0.2,
            max_tokens=2000,
        )
        parsed = repair_json(response.content)
        if not isinstance(parsed, dict):
            raise ValueError("AI draft response must be a JSON object")
        return VisualUIService._normalize_draft(parsed, data)

    @staticmethod
    def _draft_system_prompt() -> str:
        return """
你是 UI 自动化测试用例设计助手。把用户的自然语言需求转换为 Visual UI 用例草稿。
只返回 JSON，不要返回 Markdown。
如果请求已提供 base_url，并且用户目标清楚，就必须用 base_url 生成 GOTO 步骤，不要再追问页面 URL。
只有缺少测试目标、必要账号密码、关键断言或操作目标时，才返回 needs_clarification。
不要编造敏感凭据，不要直接执行测试。
允许的 action 只有 GOTO, CLICK, TYPE, WAIT, ASSERT, SCROLL。
TYPE 的 value 是要输入的文本；GOTO 的 value 是 URL；ASSERT 的 value 是期望看到的文本。
如果用户说“verify/assert/check/确认/验证 某文字可见”，生成 ASSERT，target_description 可以是“页面正文”或具体区域，value 是期望文字。
""".strip()

    @staticmethod
    def _draft_user_prompt(data: VisualUIDraftRequest, prompt: str) -> str:
        return f"""
请求上下文：
- project_id: {data.project_id}
- base_url: {data.base_url or "未提供"}

规则：
- 如果 base_url 已提供，把第一个导航步骤设为 GOTO，value 使用该 base_url。
- 如果用户明确要验证某段文字可见，生成 ASSERT，target_description 使用“页面正文”，value 使用该文字。
- 不要因为 base_url 已提供还追问 URL。

请生成如下 JSON 结构：
{{
  "status": "ok",
  "draft": {{
    "project_id": "{data.project_id}",
    "name": "简短用例名",
    "description": "用例说明",
    "status": "draft",
    "base_url": {data.base_url!r},
    "steps": [
      {{"step_index": 0, "action": "GOTO", "target_description": null, "value": "https://example.com", "screenshot_baseline": null}}
    ]
  }},
  "questions": []
}}

信息不足时返回：
{{"status": "needs_clarification", "questions": ["需要用户补充的问题"]}}

用户需求：{prompt}
""".strip()

    @staticmethod
    def _normalize_draft(raw: dict[str, Any], data: VisualUIDraftRequest) -> VisualUIDraftResponse:
        if raw.get("status") == "needs_clarification":
            questions = raw.get("questions") if isinstance(raw.get("questions"), list) else []
            normalized_questions = [str(question).strip() for question in questions if str(question).strip()]
            if data.base_url and VisualUIService._only_needs_url(normalized_questions):
                return VisualUIService._simple_base_url_draft(data)
            return VisualUIDraftResponse(status="needs_clarification", questions=normalized_questions)

        draft = raw.get("draft")
        if not isinstance(draft, dict):
            return VisualUIDraftResponse(status="needs_clarification", questions=["请补充要生成的用例名称、目标页面和测试步骤。"])

        base_url = data.base_url or draft.get("base_url")
        if isinstance(base_url, str):
            base_url = base_url.strip() or None

        steps_raw = draft.get("steps") if isinstance(draft.get("steps"), list) else []
        if not steps_raw:
            return VisualUIDraftResponse(status="needs_clarification", questions=["请补充至少一个 UI 操作或断言步骤。"])

        steps: list[VisualStepCreate] = []
        questions: list[str] = []
        for step_raw in steps_raw:
            if not isinstance(step_raw, dict):
                continue

            try:
                action = VisualStepAction(str(step_raw.get("action") or "").upper())
            except ValueError:
                questions.append("生成的步骤包含不支持的动作，请重新描述测试流程。")
                continue

            target_description = VisualUIService._optional_text(step_raw.get("target_description"))
            value = VisualUIService._optional_text(step_raw.get("value"))
            screenshot_baseline = VisualUIService._optional_text(step_raw.get("screenshot_baseline"))

            if action == VisualStepAction.GOTO and not value:
                value = base_url
            if action == VisualStepAction.GOTO and not value:
                questions.append("请提供要打开的页面 URL。")
            if action == VisualStepAction.TYPE and not value:
                questions.append("请提供输入步骤要填写的文本。")
            if action in {VisualStepAction.CLICK, VisualStepAction.ASSERT, VisualStepAction.SCROLL} and not target_description:
                questions.append(f"请补充 {action.value} 步骤的目标元素描述。")

            steps.append(VisualStepCreate(
                step_index=len(steps),
                action=action,
                target_description=target_description,
                value=value,
                screenshot_baseline=screenshot_baseline,
            ))

        if questions or not steps:
            return VisualUIDraftResponse(status="needs_clarification", questions=list(dict.fromkeys(questions or ["请补充可执行的 UI 测试步骤。"])))

        generated = VisualUseCaseCreate(
            project_id=data.project_id,
            name=VisualUIService._optional_text(draft.get("name")) or "AI 生成视觉用例",
            description=VisualUIService._optional_text(draft.get("description")),
            status=VisualUseCaseStatus.draft,
            base_url=base_url,
            steps=steps,
        )
        return VisualUIDraftResponse(status="ok", draft=generated)

    @staticmethod
    def _only_needs_url(questions: list[str]) -> bool:
        if not questions:
            return False
        url_markers = ("url", "URL", "页面", "网址", "地址", "目标站点", "目标页面")
        return all(any(marker in question for marker in url_markers) for question in questions)

    @staticmethod
    def _simple_base_url_draft(data: VisualUIDraftRequest) -> VisualUIDraftResponse:
        steps = [
            VisualStepCreate(
                step_index=0,
                action=VisualStepAction.GOTO,
                target_description=None,
                value=data.base_url,
                screenshot_baseline=None,
            )
        ]
        return VisualUIDraftResponse(
            status="ok",
            draft=VisualUseCaseCreate(
                project_id=data.project_id,
                name="AI 生成视觉用例",
                description=data.prompt.strip(),
                status=VisualUseCaseStatus.draft,
                base_url=data.base_url,
                steps=steps,
            ),
        )

    @staticmethod
    def _optional_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    async def get_case(db: AsyncSession, case_id: str) -> Optional[VisualUseCase]:
        stmt = select(VisualUseCase).options(selectinload(VisualUseCase.steps)).where(VisualUseCase.id == case_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_cases_by_project(db: AsyncSession, project_id: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[VisualUseCase]:
        stmt = select(VisualUseCase)
        if project_id:
            stmt = stmt.where(VisualUseCase.project_id == project_id)
        
        stmt = (
            stmt.order_by(VisualUseCase.created_at.desc())
            .options(selectinload(VisualUseCase.steps))
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_case(db: AsyncSession, data: VisualUseCaseCreate) -> VisualUseCase:
        # Create base entity
        db_case = VisualUseCase(
            project_id=data.project_id,
            name=data.name,
            description=data.description,
            status=data.status,
            base_url=data.base_url
        )
        db.add(db_case)
        await db.flush()  # To gain the UUID

        # Create steps
        for step_dto in data.steps:
            db_step = VisualStep(
                case_id=db_case.id,
                step_index=step_dto.step_index,
                action=step_dto.action,
                target_description=step_dto.target_description,
                value=step_dto.value,
                screenshot_baseline=step_dto.screenshot_baseline
            )
            db.add(db_step)
        
        await db.commit()
        await db.refresh(db_case)
        return await VisualUIService.get_case(db, db_case.id)

    @staticmethod
    async def update_case(db: AsyncSession, case_id: str, data: VisualUseCaseUpdate) -> Optional[VisualUseCase]:
        # 1. Fetch current case
        stmt = select(VisualUseCase).options(selectinload(VisualUseCase.steps)).where(VisualUseCase.id == case_id)
        result = await db.execute(stmt)
        db_case = result.scalar_one_or_none()
        
        if not db_case:
            return None

        # 2. Update primitive fields
        if data.project_id is not None: db_case.project_id = data.project_id
        if data.name is not None: db_case.name = data.name
        if data.description is not None: db_case.description = data.description
        if data.status is not None: db_case.status = data.status
        if data.base_url is not None: db_case.base_url = data.base_url

        # 3. Replace steps if provided
        if data.steps is not None:
            # Delete old steps manually if cascade is not entirely synchronous
            for old_step in db_case.steps:
                await db.delete(old_step)
            db_case.steps.clear()
            await db.flush()

            # Insert new steps
            for st in data.steps:
                new_step = VisualStep(
                    case_id=db_case.id,
                    step_index=st.step_index,
                    action=st.action,
                    target_description=st.target_description,
                    value=st.value,
                    screenshot_baseline=st.screenshot_baseline
                )
                db.add(new_step)
        
        await db.commit()
        return await VisualUIService.get_case(db, case_id)

    @staticmethod
    async def delete_case(db: AsyncSession, case_id: str) -> bool:
        stmt = select(VisualUseCase).where(VisualUseCase.id == case_id)
        result = await db.execute(stmt)
        db_case = result.scalar_one_or_none()
        if not db_case:
            return False
        
        await db.delete(db_case)
        await db.commit()
        return True
