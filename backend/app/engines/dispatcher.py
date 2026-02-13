"""
调度器 (Dispatcher)

智能路由 TC-IR 到正确的执行引擎
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Any
from loguru import logger



from app.engines.right_pupil import RightPupilEngine
from app.engines.left_pupil import LeftPupilEngine

# Import schemas from new location
from app.schemas.execution import (
    ExecutionMode,
    TCIR,
    StepResult,
    ExecutionResult,
    AUIIR,
    APIIR as SchemaAPIIR
)
from app.engines.left_pupil import APIIR as EngineAPIIR, ExecutionResult as APIExecutionResult

class Dispatcher:
    """
    调度器 - 智能路由引擎
    
    职责:
    1. 解析 TC-IR 的执行模式
    2. 将步骤路由到对应引擎 (UI → 右瞳, API → 左瞳)
    3. 管理执行上下文
    4. 收集执行轨迹
    """
    
    def __init__(self):
        self.right_pupil: Optional[RightPupilEngine] = None
        self.left_pupil: Optional[LeftPupilEngine] = None
        self._trace_log: List[dict] = []
    
    def attach_engines(
        self,
        right_pupil: RightPupilEngine = None,
        left_pupil: LeftPupilEngine = None,
    ):
        """附加执行引擎"""
        self.right_pupil = right_pupil
        self.left_pupil = left_pupil
    
    async def execute(self, tc_ir: TCIR) -> ExecutionResult:
        """
        执行测试用例
        
        Args:
            tc_ir: 测试用例中间表示
            
        Returns:
            ExecutionResult: 执行结果
        """
        import time
        import uuid
        
        trace_id = f"TRACE_{uuid.uuid4().hex[:8].upper()}"
        start_time = time.time()
        step_results: List[StepResult] = []
        overall_success = True
        
        logger.info(f"开始执行用例: {tc_ir.id} - {tc_ir.name}")
        
        for i, step in enumerate(tc_ir.steps):
            step_start = time.time()
            
            try:
                result = await self._execute_step(step, tc_ir.mode)
                
                step_result = StepResult(
                    step_index=i,
                    success=result.get("success", False),
                    duration_ms=(time.time() - step_start) * 1000,
                    screenshot=result.get("screenshot"),
                    details=result,
                )
                
                if not step_result.success:
                    overall_success = False
                    step_result.error = result.get("error")
                    
            except Exception as e:
                overall_success = False
                step_result = StepResult(
                    step_index=i,
                    success=False,
                    duration_ms=(time.time() - step_start) * 1000,
                    error=str(e),
                )
            
            step_results.append(step_result)
            
            # 记录轨迹
            self._trace_log.append({
                "trace_id": trace_id,
                "tc_id": tc_ir.id,
                "step_index": i,
                "step": step,
                "result": step_result.__dict__,
            })
            
            # 失败立即停止 (可配置)
            if not step_result.success:
                logger.warning(f"步骤 {i} 失败，终止执行")
                break
        
        total_duration = (time.time() - start_time) * 1000
        status = "passed" if overall_success else "failed"
        
        logger.info(f"用例 {tc_ir.id} 执行完成: {status}")
        
        return ExecutionResult(
            tc_id=tc_ir.id,
            success=overall_success,
            status=status,
            step_results=step_results,
            total_duration_ms=total_duration,
            trace_id=trace_id,
        )
    
    async def _execute_step(self, step: dict, mode: ExecutionMode) -> dict:
        """执行单个步骤"""
        step_type = step.get("type", "UI" if mode == ExecutionMode.UI else "API")
        
        if step_type == "UI":
            if not self.right_pupil:
                raise RuntimeError("右瞳引擎未初始化")
            
            aui_ir = AUIIR(
                action_type=step.get("action", "click"), # Correct field name
                target=step.get("target"),
                params=step.get("params", {}), # Pass params
                expected_visual_change=step.get("expected")
            )
            
            result = await self.right_pupil.execute(aui_ir)
            
            strategy_val = "unknown"
            if getattr(result, "strategy_used", None):
                 strategy_val = result.strategy_used.value
            
            return {
                "success": result.success,
                "strategy": strategy_val,
                "screenshot": result.screenshot_after,
                "error": result.error,
            }
        
        elif step_type == "API":
            if not self.left_pupil:
                raise RuntimeError("左瞳引擎未初始化")
            
            # Use EngineAPIIR which has path_params
            api_ir = EngineAPIIR(
                method=step.get("method", "GET"),
                url=step.get("url", ""),
                headers=step.get("headers", {}),
                query_params=step.get("params", {}),
                path_params=step.get("path_params", {}), # Added path_params
                body=step.get("body"),
                assertions=step.get("assertions", []),
                extract=step.get("extract", {}),
            )
            
            try:
                # Returns Engine's ExecutionResult
                result: APIExecutionResult = await self.left_pupil.execute(api_ir)
                
                status_code = 0
                if result.response:
                    status_code = result.response.status_code
                
                return {
                    "success": result.success,
                    "status_code": status_code,
                    "assertions_failed": result.assertions_failed,
                    "error": result.error,
                }
            except Exception as e:
                 logger.error(f"API Step Failed inside Dispatcher: {e}")
                 # Return failed result structure instead of raising to keep execution flowing if handled
                 return {
                    "success": False,
                    "status_code": 0,
                    "assertions_failed": [],
                    "error": str(e),
                }
        
        else:
            raise ValueError(f"不支持的步骤类型: {step_type}")
    
    def get_trace_log(self) -> List[dict]:
        """获取执行轨迹"""
        return self._trace_log
    
    def clear_trace_log(self):
        """清空轨迹日志"""
        self._trace_log = []
