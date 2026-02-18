
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.execution import Execution, ExecutionStep, ExecutionStatus
from app.core.database import get_db_session

class ExecutionService:
    """
    执行记录服务
    负责 Execution 和 ExecutionStep 的 CRUD
    """

    @staticmethod
    async def create_execution(
        execution_id: str,
        tc_ids: List[str],
        config: Dict[str, Any]
    ) -> Execution:
        """创建执行记录"""
        async with get_db_session() as session:
            execution = Execution(
                id=execution_id,
                config=config,
                status=ExecutionStatus.PENDING,
                total_cases=len(tc_ids),
                start_time=datetime.utcnow()
            )
            session.add(execution)
            await session.commit()
            return execution

    @staticmethod
    async def update_execution_status(
        execution_id: str,
        status: ExecutionStatus,
        summary: Dict[str, int] = None,
        duration_ms: float = 0.0
    ):
        """更新执行状态"""
        async with get_db_session() as session:
            stmt = select(Execution).where(Execution.id == execution_id)
            result = await session.execute(stmt)
            execution = result.scalar_one_or_none()
            
            if execution:
                execution.status = status
                if summary:
                    execution.passed_cases = summary.get("passed", 0)
                    execution.failed_cases = summary.get("failed", 0)
                    execution.skipped_cases = summary.get("skipped", 0)
                    # total is set on creation
                
                if status in [ExecutionStatus.PASSED, ExecutionStatus.FAILED, ExecutionStatus.ERROR, ExecutionStatus.CANCELLED]:
                    execution.end_time = datetime.utcnow()
                    execution.duration_ms = duration_ms
                
                await session.commit()

    @staticmethod
    async def create_step_result(
        execution_id: str,
        tc_id: str,
        status: ExecutionStatus,
        result_data: Dict[str, Any],
        duration_ms: float = 0.0,
        error: str = None
    ):
        """创建步骤(用例)执行结果"""
        async with get_db_session() as session:
            step = ExecutionStep(
                execution_id=execution_id,
                tc_id=tc_id,
                status=status,
                step_results=result_data, # Detailed step results
                duration_ms=duration_ms,
                error_message=error,
                start_time=datetime.utcnow(), # Approximate
                end_time=datetime.utcnow()    # Approximate
            )
            # Debug Log for Persistence Verification
            from loguru import logger
            logger.info(f"💾 Saving Step Result for {tc_id}: Details Keys={[s.get('details', {}).keys() for s in result_data.get('steps', [])]}")
            
            session.add(step)
            await session.commit()

    @staticmethod
    async def get_execution(execution_id: str) -> Optional[Execution]:
        """获取执行详情"""
        async with get_db_session() as session:
            stmt = select(Execution).where(Execution.id == execution_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    async def list_executions(limit: int = 20, offset: int = 0) -> List[Execution]:
        """获取执行列表"""
        async with get_db_session() as session:
            stmt = select(Execution).order_by(desc(Execution.created_at)).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def get_execution_steps(execution_id: str) -> List[ExecutionStep]:
        """获取执行步骤列表"""
        async with get_db_session() as session:
            stmt = select(ExecutionStep).where(ExecutionStep.execution_id == execution_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def run_ui_task(prompt: str, url: str) -> List[dict]:
        """
        执行 UI 自动化任务 (Right Pupil) - 同步 Debug 模式

        封装 RightPupilEngine，避免 API 层直接依赖 engines。
        """
        from app.engines.right_pupil import RightPupilEngine
        engine = RightPupilEngine()
        return await engine.run_task(prompt, url)

    @staticmethod
    async def get_execution_status_dict(execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取执行状态的纯字典表示

        封装 DB model 访问，避免 API 层直接依赖 models。
        """
        execution = await ExecutionService.get_execution(execution_id)
        if not execution:
            return None

        is_terminal = execution.status in [ExecutionStatus.PASSED, ExecutionStatus.FAILED]
        return {
            "execution_id": execution.id,
            "status": execution.status.value,
            "progress": 100.0 if is_terminal else 0.0,
            "passed": execution.passed_cases,
            "failed": execution.failed_cases,
            "skipped": execution.skipped_cases,
            "running": 0,
            "pending": 0,
            "start_time": execution.start_time.isoformat() if execution.start_time else "",
            "elapsed_seconds": execution.duration_ms / 1000.0 if execution.duration_ms else 0.0,
        }

    @staticmethod
    async def get_execution_result_dict(execution_id: str, strip_screenshots: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取执行结果的纯字典表示

        封装 DB model 访问，避免 API 层直接依赖 models。
        strip_screenshots=True 时，将 base64 截图替换为 URL 引用以减小响应体积。
        """
        execution = await ExecutionService.get_execution(execution_id)
        if not execution:
            return None

        steps = await ExecutionService.get_execution_steps(execution_id)
        case_results = []
        for case_idx, step in enumerate(steps):
            step_list = step.step_results.get("steps", []) if step.step_results else []
            
            if strip_screenshots:
                step_list = ExecutionService._strip_screenshots(
                    execution_id, case_idx, step_list
                )
            
            case_results.append({
                "tc_id": step.tc_id,
                "status": step.status.value,
                "duration_ms": step.duration_ms,
                "steps": step_list,
                "variable_trace": step.step_results.get("variable_trace", []) if step.step_results else [],
                "error": step.error_message,
            })

        return {
            "execution_id": execution.id,
            "status": execution.status.value,
            "summary": {
                "total": execution.total_cases,
                "passed": execution.passed_cases,
                "failed": execution.failed_cases,
                "skipped": execution.skipped_cases,
            },
            "cases": case_results,
            "duration_seconds": execution.duration_ms / 1000.0 if execution.duration_ms else 0.0,
            "report_url": execution.report_url,
        }

    @staticmethod
    def _strip_screenshots(execution_id: str, case_idx: int, step_list: list) -> list:
        """
        将步骤中的 base64 截图替换为按需加载的 URL。
        保持数据结构不变，仅替换 screenshot_before / screenshot_after 的值。
        """
        for step_idx, step_data in enumerate(step_list):
            details = step_data.get("details", {})
            if not details:
                continue
            
            for field in ("screenshot_before", "screenshot_after"):
                val = details.get(field)
                if val and (val.startswith("data:image") or len(str(val)) > 1000):
                    img_type = field.replace("screenshot_", "")  # "before" or "after"
                    details[field] = f"/api/v1/executions/{execution_id}/screenshot/{case_idx}/{step_idx}/{img_type}"
        
        return step_list

    @staticmethod
    async def list_executions_dicts(limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取执行列表的纯字典列表

        封装 DB model 访问，避免 API 层直接依赖 models。
        """
        executions = await ExecutionService.list_executions(limit=limit)
        result = []
        for exec_record in executions:
            is_terminal = exec_record.status in [ExecutionStatus.PASSED, ExecutionStatus.FAILED]
            result.append({
                "execution_id": exec_record.id,
                "status": exec_record.status.value,
                "progress": 100.0 if is_terminal else 0.0,
                "passed": exec_record.passed_cases,
                "failed": exec_record.failed_cases,
                "skipped": exec_record.skipped_cases,
                "running": 0,
                "pending": 0,
                "start_time": exec_record.start_time.isoformat() if exec_record.start_time else "",
                "elapsed_seconds": exec_record.duration_ms / 1000.0 if exec_record.duration_ms else 0.0,
            })
        return result
