"""
左瞳引擎

API 测试自动化引擎入口
"""

from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

from app.services.left_pupil.context_memory import ContextMemory
from app.services.left_pupil.spec_ingestor import SpecIngestor
from app.services.left_pupil.rag_retriever import RagRetriever, ApiContext
from app.services.left_pupil.dependency_planner import DependencyPlanner, ExecutionPlan
from app.services.left_pupil.api_runner import ApiRunner, ApiIRStep, RequestSpec, ExecutionResult


@dataclass
class ExecutionReport:
    """执行报告"""
    id: str
    status: str  # "passed", "failed", "error"
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    results: list[ExecutionResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "results": [r.to_dict() for r in self.results],
        }


class LeftPupilEngine:
    """
    左瞳引擎
    
    API 测试自动化引擎，提供：
    - 意图驱动执行
    - API-IR 直接执行
    - 自动依赖规划
    """
    
    def __init__(
        self,
        base_url: str,
        project_id: str,
        default_headers: Optional[dict] = None,
    ):
        """
        初始化引擎
        
        Args:
            base_url: API 基础 URL
            project_id: 项目 ID
            default_headers: 默认请求头
        """
        self.base_url = base_url
        self.project_id = project_id
        self.default_headers = default_headers or {}
        
        # 初始化组件
        self.memory = ContextMemory()
        self.ingestor = SpecIngestor()
        self.retriever = RagRetriever(self.ingestor)
        self.planner = DependencyPlanner(self.retriever)
        self.runner = ApiRunner(base_url, self.memory, default_headers)
    
    async def execute_intent(
        self,
        intent: str,
        additional_vars: Optional[dict] = None,
    ) -> ExecutionReport:
        """
        从用户意图执行
        
        Args:
            intent: 用户意图（如 "创建订单"）
            additional_vars: 额外变量
        
        Returns:
            执行报告
        """
        report_id = f"RPT_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            # 导入额外变量
            if additional_vars:
                self.memory.from_dict(additional_vars, source="input")
            
            # 1. 检索相关 API
            apis = await self.retriever.retrieve(
                intent=intent,
                project_id=self.project_id,
                top_k=5,
            )
            
            if not apis:
                return ExecutionReport(
                    id=report_id,
                    status="error",
                    start_time=start_time,
                    end_time=datetime.now(timezone.utc),
                    error="未找到相关 API",
                )
            
            # 选择最相关的 API
            target_api = apis[0]
            
            # 2. 依赖规划
            plan = await self.planner.plan(
                target_api=target_api,
                project_id=self.project_id,
                memory=self.memory,
            )
            
            # 3. 执行计划
            return await self._execute_plan(plan, report_id, start_time)
            
        except Exception as e:
            return ExecutionReport(
                id=report_id,
                status="error",
                start_time=start_time,
                end_time=datetime.now(timezone.utc),
                error=str(e),
            )
    
    async def execute_api_ir(
        self,
        api_ir_steps: list[dict],
        additional_vars: Optional[dict] = None,
    ) -> ExecutionReport:
        """
        执行 API-IR 步骤列表
        
        Args:
            api_ir_steps: API-IR 步骤字典列表
            additional_vars: 额外变量
        
        Returns:
            执行报告
        """
        report_id = f"RPT_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            # 导入额外变量
            if additional_vars:
                self.memory.from_dict(additional_vars, source="input")
            
            # 转换为执行步骤
            steps = []
            for step_data in api_ir_steps:
                request_data = step_data.get("request", {})
                steps.append(ApiIRStep(
                    id=step_data.get("id", f"STEP_{len(steps)+1:02d}"),
                    name=step_data.get("name", ""),
                    request=RequestSpec(
                        method=request_data.get("method", "GET"),
                        url=request_data.get("url", "/"),
                        headers=request_data.get("headers", {}),
                        body=request_data.get("body"),
                        query_params=request_data.get("query_params", {}),
                        timeout_ms=request_data.get("timeout_ms", 30000),
                    ),
                    extraction=step_data.get("extraction", {}),
                    assertion=step_data.get("assertion", {}),
                    retry_config=step_data.get("retry", {}),
                ))
            
            # 执行
            results = []
            passed = 0
            failed = 0
            
            for step in steps:
                result = await self.runner.execute(step)
                results.append(result)
                
                if result.status == "passed":
                    passed += 1
                else:
                    failed += 1
                    # 是否继续执行？
                    if step_data.get("stop_on_failure", True):
                        break
            
            end_time = datetime.now(timezone.utc)
            return ExecutionReport(
                id=report_id,
                status="passed" if failed == 0 else "failed",
                total_steps=len(steps),
                passed_steps=passed,
                failed_steps=failed,
                results=results,
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
            )
            
        except Exception as e:
            return ExecutionReport(
                id=report_id,
                status="error",
                start_time=start_time,
                end_time=datetime.now(timezone.utc),
                error=str(e),
            )
    
    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        report_id: str,
        start_time: datetime,
    ) -> ExecutionReport:
        """执行计划"""
        results = []
        passed = 0
        failed = 0
        
        for step in plan.steps:
            # 转换为 ApiIRStep
            api_step = ApiIRStep(
                id=step.id,
                name=step.api.summary or step.api.endpoint_id,
                request=RequestSpec(
                    method=step.api.method,
                    url=step.api.path,
                    headers={"Authorization": "Bearer ${token}"} if step.api.metadata.get("requires_auth") else {},
                ),
                extraction=step.extraction,
                assertion={"status_code": [200, 201]},
            )
            
            result = await self.runner.execute(api_step)
            results.append(result)
            
            if result.status == "passed":
                passed += 1
            else:
                failed += 1
                break  # 停止执行
        
        end_time = datetime.now(timezone.utc)
        return ExecutionReport(
            id=report_id,
            status="passed" if failed == 0 else "failed",
            total_steps=len(plan.steps),
            passed_steps=passed,
            failed_steps=failed,
            results=results,
            start_time=start_time,
            end_time=end_time,
            duration_ms=(end_time - start_time).total_seconds() * 1000,
        )
    
    def set_variable(self, key: str, value, source: str = "manual"):
        """设置变量"""
        self.memory.set(key, value, source)
    
    def get_variable(self, key: str, default=None):
        """获取变量"""
        return self.memory.get(key, default)
    
    def get_all_variables(self) -> dict:
        """获取所有变量"""
        return self.memory.to_dict()
    
    async def close(self):
        """关闭引擎"""
        await self.runner.close()
        await self.retriever.close()
        await self.planner.close()
