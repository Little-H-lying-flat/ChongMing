"""
神经设计层端点

PRD 驱动的智能用例生成
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


# ===================== 数据模型 =====================

class DesignRequest(BaseModel):
    """设计请求"""
    intent: str = Field(..., description="用户意图，如 '测试登录功能'")
    constraints: Optional[dict] = Field(None, description="约束条件")
    context: List[str] = Field(default_factory=list, description="历史上下文")
    max_cases: int = Field(10, ge=1, le=50, description="最大生成用例数")


class DesignDraft(BaseModel):
    """设计草稿"""
    id: str
    name: str
    description: str
    mode: str
    priority: str
    steps: List[dict]
    critic_score: Optional[float]
    critic_feedback: Optional[str]
    status: str


class DesignResponse(BaseModel):
    """设计响应"""
    session_id: str
    status: str
    drafts: List[DesignDraft]
    message: str


class ConfirmRequest(BaseModel):
    """确认请求"""
    draft_ids: List[str] = Field(..., description="要确认的草稿 ID 列表")
    modifications: Optional[dict] = Field(None, description="修改意见")


# ===================== API 端点 =====================

@router.post("/generate", response_model=DesignResponse)
async def generate_test_cases(request: DesignRequest):
    """
    智能生成测试用例
    
    基于用户意图，使用 LLM 生成测试用例草稿
    """
    # TODO: 调用神经设计层
    return DesignResponse(
        session_id="SESSION_PLACEHOLDER",
        status="draft",
        drafts=[],
        message="正在分析需求...",
    )


@router.post("/generate/stream")
async def generate_test_cases_stream(request: DesignRequest):
    """
    流式生成测试用例
    
    使用 SSE 实时推送生成进度
    """
    async def event_generator():
        # TODO: 实现流式生成
        yield {"event": "start", "data": '{"message": "开始生成"}'}
        yield {"event": "progress", "data": '{"step": 1, "message": "解析意图..."}'}
        yield {"event": "complete", "data": '{"drafts": []}'}
    
    return EventSourceResponse(event_generator())


@router.post("/confirm")
async def confirm_drafts(request: ConfirmRequest):
    """
    确认测试用例草稿
    
    将草稿转为正式 TC-IR 资产
    """
    # TODO: 保存到资产库
    return {
        "confirmed_count": len(request.draft_ids),
        "tc_ids": [f"TC_{id}" for id in request.draft_ids],
    }


@router.get("/sessions/{session_id}")
async def get_design_session(session_id: str):
    """
    获取设计会话状态
    """
    # TODO: 查询会话状态
    raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
