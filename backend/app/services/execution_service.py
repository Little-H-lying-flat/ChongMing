
import re
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.execution import Execution, ExecutionStep, ExecutionStatus
from app.core.database import get_db_session

class ExecutionService:
    """
    执行记录服务
    负责 Execution 和 ExecutionStep 的 CRUD
    """

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

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
                start_time=ExecutionService._utcnow()
            )
            session.add(execution)
            await session.commit()
            return execution

    @staticmethod
    async def update_execution_status(
        execution_id: str,
        status: ExecutionStatus,
        summary: Dict[str, Any] | None = None,
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
                    execution.end_time = ExecutionService._utcnow()
                    execution.duration_ms = duration_ms
                
                await session.commit()

    @staticmethod
    async def create_step_result(
        execution_id: str,
        tc_id: str,
        status: ExecutionStatus,
        result_data: Dict[str, Any],
        duration_ms: float = 0.0,
        error: str | None = None
    ):
        """创建步骤(用例)执行结果"""
        import os
        import base64
        from loguru import logger
        import copy
        
        # Deep copy to avoid mutating the original dict if used elsewhere
        result_data_copy = copy.deepcopy(result_data)
        
        # 1. 拦截并剥离大 Base64 数据，落盘以防撑爆 DB JSONB
        try:
            screenshot_dir = os.path.join("data", "screenshots", execution_id)
            os.makedirs(screenshot_dir, exist_ok=True)
            
            steps_list = result_data_copy.get("steps", [])
            for step_idx, step_data in enumerate(steps_list):
                details = step_data.get("details", {})
                if not isinstance(details, dict):
                    continue
                for field in ("screenshot_before", "screenshot_after"):
                    val = details.get(field)
                    if val and isinstance(val, str) and len(val) > 1000:  # is Base64
                        img_type = field.replace("screenshot_", "")
                        safe_tc_id = ExecutionService._safe_filename_component(tc_id)
                        filename = f"{safe_tc_id}_{step_idx}_{img_type}.png"
                        filepath = os.path.join(screenshot_dir, filename)
                        
                        b64_data = val.split(",", 1)[-1] if val.startswith("data:image") else val
                        with open(filepath, "wb") as f:
                            f.write(base64.b64decode(b64_data))
                        
                        # Replace heavy base64 with a lightweight local marker
                        details[field] = f"LOCAL:{filename}"
        except Exception as e:
            logger.error(f"Failed to offload Base64 screenshots to disk for {tc_id}: {e}")

        async with get_db_session() as session:
            step = ExecutionStep(
                execution_id=execution_id,
                tc_id=tc_id,
                status=status,
                step_results=result_data_copy, # Stripped results
                duration_ms=duration_ms,
                error_message=error,
                start_time=ExecutionService._utcnow(),
                end_time=ExecutionService._utcnow()
            )
            logger.info(f"💾 Saving Step Result for {tc_id}: Details Keys={[(s.get('details') or {}).keys() for s in result_data_copy.get('steps', [])]}")
            
            session.add(step)
            await session.commit()

    @staticmethod
    def _safe_filename_component(value: str) -> str:
        """Normalize potentially unsafe filename components before writing to disk."""
        normalized = re.sub(r"[^A-Za-z0-9._-]", "_", value or "")
        return normalized or "unknown"

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
    async def delete_execution(execution_id: str) -> bool:
        """删除执行记录及其关联步骤和截图"""
        import os
        import shutil
        from sqlalchemy import delete
        
        async with get_db_session() as session:
            # 1. Check if exists
            stmt = select(Execution).where(Execution.id == execution_id)
            exec_obj = (await session.execute(stmt)).scalar_one_or_none()
            if not exec_obj:
                return False
                
            # 2. Delete execution steps
            del_steps_stmt = delete(ExecutionStep).where(ExecutionStep.execution_id == execution_id)
            await session.execute(del_steps_stmt)
            
            # 3. Delete execution
            del_exec_stmt = delete(Execution).where(Execution.id == execution_id)
            await session.execute(del_exec_stmt)
            
            await session.commit()
            
            # 4. Clean up disk screenshots
            try:
                screenshot_dir = os.path.join("data", "screenshots", execution_id)
                if os.path.exists(screenshot_dir):
                    shutil.rmtree(screenshot_dir)
            except Exception as e:
                logger.error(f"Failed to delete screenshot dir for {execution_id}: {e}")
                
            return True

    @staticmethod
    async def count_executions() -> int:
        """获取执行总数"""
        from sqlalchemy import func
        async with get_db_session() as session:
            stmt = select(func.count(Execution.id))
            result = await session.execute(stmt)
            return result.scalar() or 0

    @staticmethod
    async def get_execution_stats() -> dict:
        """获取执行统计大盘数据"""
        from sqlalchemy import func
        async with get_db_session() as session:
            active_stmt = select(func.count(Execution.id)).where(Execution.status.in_([ExecutionStatus.PENDING, ExecutionStatus.RUNNING]))
            active_count = (await session.execute(active_stmt)).scalar() or 0
            
            total_stmt = select(func.count(Execution.id))
            total_count = (await session.execute(total_stmt)).scalar() or 0
            
            passed_stmt = select(func.count(Execution.id)).where(Execution.status == ExecutionStatus.PASSED)
            passed_count = (await session.execute(passed_stmt)).scalar() or 0
            
            success_rate = round((passed_count / total_count * 100), 1) if total_count > 0 else 0.0
            
            duration_stmt = select(func.avg(Execution.duration_ms)).where(Execution.status.in_([ExecutionStatus.PASSED, ExecutionStatus.FAILED]))
            avg_duration_ms = (await session.execute(duration_stmt)).scalar() or 0.0
            avg_duration = round(avg_duration_ms / 1000.0, 1)
            
            return {
                "active": active_count,
                "success_rate": success_rate,
                "avg_duration": avg_duration,
                "total": total_count
            }

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
                    execution_id, case_idx, step_list, step.tc_id
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
    def _strip_screenshots(execution_id: str, case_idx: int, step_list: list, tc_id: str = "") -> list:
        """
        将步骤中的截图标记替换为按需加载的 URL。
        保持数据结构不变，仅替换 screenshot_before / screenshot_after 的值。
        """
        for step_idx, step_data in enumerate(step_list):
            details = step_data.get("details", {})
            if not details:
                continue
            
            for field in ("screenshot_before", "screenshot_after"):
                val = details.get(field)
                if val: # it has image info (either LOCAL: marker or legacy data URI)
                    img_type = field.replace("screenshot_", "")  # "before" or "after"
                    details[field] = f"/api/v1/executions/{execution_id}/screenshot/{case_idx}/{step_idx}/{img_type}?tc_id={tc_id}"
        
        return step_list

    @staticmethod
    async def list_executions_dicts(skip: int = 0, limit: int = 20) -> Dict[str, Any]:
        """
        获取执行列表的纯字典列表
        返回 {"total": x, "items": [...]}
        """
        total = await ExecutionService.count_executions()
        executions = await ExecutionService.list_executions(limit=limit, offset=skip)
        
        items = []
        for exec_record in executions:
            is_terminal = exec_record.status in [ExecutionStatus.PASSED, ExecutionStatus.FAILED, ExecutionStatus.ERROR, ExecutionStatus.CANCELLED]
            items.append({
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
        return {"total": total, "items": items}
