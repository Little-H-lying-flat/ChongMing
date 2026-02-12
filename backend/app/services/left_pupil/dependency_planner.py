"""
依赖规划器

分析 API 间的参数依赖，构建执行 DAG
"""

from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict
import httpx

from app.core.config import settings
from app.services.left_pupil.rag_retriever import RagRetriever, ApiContext
from app.services.left_pupil.context_memory import ContextMemory


@dataclass
class Dependency:
    """参数依赖"""
    param_name: str          # 需要的参数名
    provider_api: ApiContext # 提供该参数的 API
    extraction_path: str     # 从响应中提取的路径


@dataclass
class ExecutionStep:
    """执行步骤"""
    id: str
    api: ApiContext
    dependencies: list[str] = field(default_factory=list)  # 依赖的步骤 ID
    extraction: dict[str, str] = field(default_factory=dict)  # 变量提取规则


@dataclass
class ExecutionPlan:
    """执行计划"""
    steps: list[ExecutionStep] = field(default_factory=list)
    target_api: Optional[ApiContext] = None
    
    def to_dict(self) -> dict:
        return {
            "steps": [
                {
                    "id": s.id,
                    "method": s.api.method,
                    "path": s.api.path,
                    "dependencies": s.dependencies,
                    "extraction": s.extraction,
                }
                for s in self.steps
            ],
            "total_steps": len(self.steps),
        }


class DependencyPlanner:
    """
    依赖规划器
    
    分析目标 API 的参数依赖，构建完整的执行链
    """
    
    # 常见参数到提供者 API 模式的映射
    PARAM_PROVIDERS = {
        "token": ["login", "auth", "signin"],
        "access_token": ["login", "auth", "oauth/token"],
        "user_id": ["login", "users/me", "profile"],
        "order_id": ["orders", "create.*order"],
        "product_id": ["products", "items"],
    }
    
    def __init__(self, retriever: Optional[RagRetriever] = None):
        """
        初始化规划器
        
        Args:
            retriever: RAG 检索器
        """
        self.retriever = retriever or RagRetriever()
    
    async def plan(
        self,
        target_api: ApiContext,
        project_id: str,
        memory: Optional[ContextMemory] = None,
    ) -> ExecutionPlan:
        """
        为目标 API 生成执行计划
        
        Args:
            target_api: 目标 API
            project_id: 项目 ID
            memory: 上下文内存（已有变量）
        
        Returns:
            执行计划
        """
        memory = memory or ContextMemory()
        
        # 1. 分析缺失参数
        missing_params = self._find_missing_params(target_api, memory)
        
        if not missing_params:
            # 无依赖，直接执行目标 API
            return ExecutionPlan(
                steps=[ExecutionStep(
                    id="STEP_01",
                    api=target_api,
                    extraction=self._infer_extraction(target_api),
                )],
                target_api=target_api,
            )
        
        # 2. 查找提供者 API
        dependencies = await self._find_providers(
            missing_params, project_id, target_api
        )
        
        # 3. 构建 DAG
        dag = self._build_dag(target_api, dependencies)
        
        # 4. 拓扑排序
        sorted_steps = self._topological_sort(dag)
        
        return ExecutionPlan(steps=sorted_steps, target_api=target_api)
    
    def _find_missing_params(
        self,
        api: ApiContext,
        memory: ContextMemory,
    ) -> list[str]:
        """找出缺失的必填参数"""
        missing = []
        
        # 从元数据获取必填参数
        required_params = api.metadata.get("required_params", "")
        if required_params:
            for param in required_params.split(","):
                param = param.strip()
                if param and not memory.has(param):
                    missing.append(param)
        
        # 检查认证需求
        if api.metadata.get("requires_auth") and not memory.has("token"):
            if "token" not in missing and "access_token" not in missing:
                missing.append("token")
        
        return missing
    
    async def _find_providers(
        self,
        missing_params: list[str],
        project_id: str,
        exclude_api: ApiContext,
    ) -> list[Dependency]:
        """为缺失参数查找提供者 API"""
        dependencies = []
        
        for param in missing_params:
            # 1. 使用预定义映射
            provider = await self._find_provider_by_pattern(
                param, project_id, exclude_api
            )
            
            if provider:
                dependencies.append(Dependency(
                    param_name=param,
                    provider_api=provider,
                    extraction_path=self._infer_extraction_path(param),
                ))
        
        return dependencies
    
    async def _find_provider_by_pattern(
        self,
        param: str,
        project_id: str,
        exclude_api: ApiContext,
    ) -> Optional[ApiContext]:
        """通过模式匹配查找提供者"""
        # 查找预定义模式
        patterns = self.PARAM_PROVIDERS.get(param, [param])
        
        for pattern in patterns:
            # 搜索相关 API
            results = await self.retriever.retrieve(
                intent=pattern,
                project_id=project_id,
                top_k=3,
                expand_intent=False,
            )
            
            for api in results:
                # 排除目标 API 自身
                if api.endpoint_id == exclude_api.endpoint_id:
                    continue
                
                # 检查是否可能提供该参数
                output_fields = api.metadata.get("output_fields", "")
                if param in output_fields or self._likely_provides(api, param):
                    return api
        
        return None
    
    def _likely_provides(self, api: ApiContext, param: str) -> bool:
        """判断 API 是否可能提供该参数"""
        # 登录类 API 提供 token
        if param in ["token", "access_token"]:
            path_lower = api.path.lower()
            if any(x in path_lower for x in ["login", "auth", "signin", "token"]):
                return True
        
        # 用户相关 API 提供 user_id
        if param == "user_id":
            path_lower = api.path.lower()
            if any(x in path_lower for x in ["user", "me", "profile"]):
                return True
        
        return False
    
    def _infer_extraction_path(self, param: str) -> str:
        """推断提取路径"""
        # 常见字段的提取路径
        paths = {
            "token": "$.data.token",
            "access_token": "$.data.access_token",
            "user_id": "$.data.user.id",
            "order_id": "$.data.id",
        }
        return paths.get(param, f"$.data.{param}")
    
    def _infer_extraction(self, api: ApiContext) -> dict[str, str]:
        """推断变量提取规则"""
        extraction = {}
        
        output_fields = api.metadata.get("output_fields", "")
        if output_fields:
            for field in output_fields.split(","):
                field = field.strip()
                if field:
                    extraction[field] = f"$.data.{field}"
        
        return extraction
    
    def _build_dag(
        self,
        target_api: ApiContext,
        dependencies: list[Dependency],
    ) -> dict[str, ExecutionStep]:
        """构建依赖图"""
        dag = {}
        step_counter = 1
        
        # 添加依赖步骤
        for dep in dependencies:
            step_id = f"STEP_{step_counter:02d}"
            dag[step_id] = ExecutionStep(
                id=step_id,
                api=dep.provider_api,
                dependencies=[],
                extraction={dep.param_name: dep.extraction_path},
            )
            step_counter += 1
        
        # 添加目标步骤
        target_step_id = f"STEP_{step_counter:02d}"
        dag[target_step_id] = ExecutionStep(
            id=target_step_id,
            api=target_api,
            dependencies=list(dag.keys()),  # 依赖所有前置步骤
            extraction=self._infer_extraction(target_api),
        )
        
        return dag
    
    def _topological_sort(self, dag: dict[str, ExecutionStep]) -> list[ExecutionStep]:
        """拓扑排序"""
        # 简单实现：按步骤 ID 排序（ID 已按依赖顺序编号）
        steps = list(dag.values())
        steps.sort(key=lambda s: s.id)
        return steps
    
    async def close(self):
        """关闭客户端"""
        if self._llm_client:
            await self._llm_client.aclose()
