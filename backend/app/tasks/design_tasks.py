"""
设计任务 - Celery Tasks

负责异步 AI 用例生成
"""

from celery import shared_task
from loguru import logger


@shared_task(bind=True, name="app.tasks.generate_test_cases")
def generate_test_cases(
    self,
    intent: str,
    constraints: dict = None,
    context: list = None,
    max_cases: int = 10,
):
    """
    AI 生成测试用例
    
    Args:
        intent: 用户意图
        constraints: 约束条件
        context: 历史上下文
        max_cases: 最大生成数量
        
    Returns:
        生成的草稿列表
    """
    import uuid
    session_id = f"SESSION_{uuid.uuid4().hex[:8].upper()}"
    
    logger.info(f"开始生成用例: {session_id}, 意图: {intent}")
    
    # 更新任务状态
    self.update_state(
        state="PROGRESS",
        meta={
            "session_id": session_id,
            "step": "parsing_intent",
            "message": "解析用户意图...",
        }
    )
    
    # TODO: 实际生成逻辑
    # 1. 调用 LLM 解析意图
    # 2. 推理测试场景
    # 3. 生成 TC-IR 草稿
    # 4. Critic Agent 审核
    
    drafts = [
        {
            "id": f"DRAFT_{uuid.uuid4().hex[:8].upper()}",
            "name": f"测试用例 - {intent}",
            "description": f"自动生成的 {intent} 测试用例",
            "mode": "UI",
            "priority": "P1",
            "steps": [
                {"action": "navigate", "target": "目标页面"},
                {"action": "verify", "target": "页面加载完成"},
            ],
            "critic_score": 0.85,
            "status": "draft",
        }
    ]
    
    logger.info(f"用例生成完成: {session_id}, 生成数量: {len(drafts)}")
    
    return {
        "session_id": session_id,
        "status": "completed",
        "drafts": drafts,
    }


@shared_task(name="app.tasks.confirm_drafts")
def confirm_drafts(draft_ids: list, modifications: dict = None):
    """确认草稿，转为正式 TC-IR"""
    logger.info(f"确认草稿: {draft_ids}")
    # TODO: 保存到资产库
    return {"confirmed_count": len(draft_ids)}
