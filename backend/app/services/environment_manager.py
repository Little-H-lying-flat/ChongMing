"""
环境管理服务

对应 Issue #EM-001, #EM-002, #EM-005
- 环境 CRUD 操作
- 变量管理与加密存储
- 环境切换与变量注入
- 健康检查
"""

import re
import uuid
import base64
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.environment import Environment
from app.core.config import settings


class EnvironmentManager:
    """
    环境管理服务
    
    提供环境配置的 CRUD、变量加密、变量注入等功能
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._fernet = self._init_fernet()
    
    def _init_fernet(self) -> Fernet | None:
        """初始化加密器"""
        key = getattr(settings, "ENCRYPTION_KEY", None)
        if key:
            # 确保 key 是 32 字节 base64 编码
            if len(key) < 32:
                key = key.ljust(32, "0")
            key_bytes = base64.urlsafe_b64encode(key[:32].encode())
            return Fernet(key_bytes)
        return None
    
    def _encrypt(self, value: str) -> str:
        """加密敏感值"""
        if self._fernet:
            return self._fernet.encrypt(value.encode()).decode()
        return value
    
    def _decrypt(self, value: str) -> str:
        """解密敏感值"""
        if self._fernet:
            try:
                return self._fernet.decrypt(value.encode()).decode()
            except Exception:
                return value
        return value

    # ========== CRUD 操作 ==========
    
    async def create(
        self,
        name: str,
        base_url: str,
        description: str | None = None,
        variables: dict | None = None,
        headers: dict | None = None,
        auth_type: str | None = None,
        auth_config: dict | None = None,
        is_default: bool = False,
        tenant_id: str | None = None,
    ) -> Environment:
        """创建环境"""
        env_id = f"env-{uuid.uuid4().hex[:8]}"
        
        # 如果设为默认，先取消其他默认环境
        if is_default:
            await self._clear_default(tenant_id)
        
        # 处理变量加密
        processed_vars = self._process_variables_for_storage(variables or {})
        
        env = Environment(
            id=env_id,
            name=name,
            description=description,
            base_url=base_url,
            variables=processed_vars,
            headers=headers or {},
            auth_type=auth_type,
            auth_config=auth_config or {},
            is_default=is_default,
            tenant_id=tenant_id,
        )
        
        self.db.add(env)
        await self.db.flush()
        return env
    
    async def get(self, env_id: str) -> Environment | None:
        """获取单个环境"""
        result = await self.db.execute(
            select(Environment).where(Environment.id == env_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str, tenant_id: str | None = None) -> Environment | None:
        """按名称获取环境"""
        query = select(Environment).where(Environment.name == name)
        if tenant_id:
            query = query.where(Environment.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_default(self, tenant_id: str | None = None) -> Environment | None:
        """获取默认环境"""
        query = select(Environment).where(Environment.is_default == True)
        if tenant_id:
            query = query.where(Environment.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_all(
        self,
        tenant_id: str | None = None,
        active_only: bool = True,
    ) -> list[Environment]:
        """列出所有环境"""
        query = select(Environment)
        if tenant_id:
            query = query.where(Environment.tenant_id == tenant_id)
        if active_only:
            query = query.where(Environment.is_active == True)
        query = query.order_by(Environment.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update(
        self,
        env_id: str,
        **kwargs,
    ) -> Environment | None:
        """更新环境"""
        env = await self.get(env_id)
        if not env:
            return None
        
        # 处理特殊字段
        if "variables" in kwargs:
            kwargs["variables"] = self._process_variables_for_storage(kwargs["variables"])
        
        if kwargs.get("is_default"):
            await self._clear_default(env.tenant_id)
        
        for key, value in kwargs.items():
            if hasattr(env, key):
                setattr(env, key, value)
        
        await self.db.flush()
        return env
    
    async def delete(self, env_id: str) -> bool:
        """删除环境"""
        result = await self.db.execute(
            delete(Environment).where(Environment.id == env_id)
        )
        return result.rowcount > 0
    
    async def _clear_default(self, tenant_id: str | None = None):
        """清除默认环境标记"""
        query = update(Environment).values(is_default=False)
        if tenant_id:
            query = query.where(Environment.tenant_id == tenant_id)
        await self.db.execute(query)

    # ========== 变量管理 ==========
    
    def _process_variables_for_storage(self, variables: dict) -> dict:
        """处理变量用于存储（加密敏感值）"""
        processed = {}
        for key, var in variables.items():
            if isinstance(var, str):
                # 简单字符串格式
                processed[key] = {"value": var, "encrypted": False, "description": ""}
            elif isinstance(var, dict):
                value = var.get("value", "")
                encrypted = var.get("encrypted", False)
                if encrypted and value:
                    value = self._encrypt(value)
                processed[key] = {
                    "value": value,
                    "encrypted": encrypted,
                    "description": var.get("description", ""),
                }
        return processed
    
    async def set_variable(
        self,
        env_id: str,
        key: str,
        value: str,
        encrypted: bool = False,
        description: str = "",
    ) -> bool:
        """设置单个变量"""
        env = await self.get(env_id)
        if not env:
            return False
        
        stored_value = self._encrypt(value) if encrypted else value
        env.variables[key] = {
            "value": stored_value,
            "encrypted": encrypted,
            "description": description,
        }
        await self.db.flush()
        return True
    
    async def get_variable(
        self,
        env_id: str,
        key: str,
        decrypt: bool = True,
    ) -> str | None:
        """获取单个变量值"""
        env = await self.get(env_id)
        if not env:
            return None
        
        var = env.variables.get(key)
        if not var:
            return None
        
        value = var.get("value")
        if var.get("encrypted") and decrypt:
            value = self._decrypt(value)
        return value
    
    async def delete_variable(self, env_id: str, key: str) -> bool:
        """删除变量"""
        env = await self.get(env_id)
        if not env or key not in env.variables:
            return False
        
        del env.variables[key]
        await self.db.flush()
        return True

    # ========== 变量注入 (Issue #EM-002) ==========
    
    async def inject_variables(
        self,
        env_id: str,
        text: str,
        additional_vars: dict | None = None,
    ) -> str:
        """
        在文本中注入环境变量
        
        支持格式: ${variable_name} 或 {{variable_name}}
        
        Args:
            env_id: 环境 ID
            text: 包含变量占位符的文本
            additional_vars: 额外的变量（优先级高于环境变量）
        
        Returns:
            注入变量后的文本
        """
        env = await self.get(env_id)
        if not env:
            return text
        
        # 合并变量（additional_vars 优先）
        all_vars = {}
        
        # 添加内置变量
        all_vars["base_url"] = env.base_url
        all_vars["env_name"] = env.name
        
        # 添加环境变量
        for key, var in env.variables.items():
            value = var.get("value", "")
            if var.get("encrypted"):
                value = self._decrypt(value)
            all_vars[key] = value
        
        # 添加额外变量
        if additional_vars:
            all_vars.update(additional_vars)
        
        # 替换 ${var} 格式
        def replace_dollar(match):
            var_name = match.group(1)
            return all_vars.get(var_name, match.group(0))
        
        text = re.sub(r"\$\{(\w+)\}", replace_dollar, text)
        
        # 替换 {{var}} 格式
        def replace_braces(match):
            var_name = match.group(1)
            return all_vars.get(var_name, match.group(0))
        
        text = re.sub(r"\{\{(\w+)\}\}", replace_braces, text)
        
        return text
    
    async def get_injected_url(
        self,
        env_id: str,
        path: str,
        additional_vars: dict | None = None,
    ) -> str:
        """
        获取完整的 URL（base_url + path，并注入变量）
        
        Args:
            env_id: 环境 ID
            path: 相对路径（可包含变量）
            additional_vars: 额外变量
        
        Returns:
            完整 URL
        """
        env = await self.get(env_id)
        if not env:
            return path
        
        # 注入 path 中的变量
        injected_path = await self.inject_variables(env_id, path, additional_vars)
        
        # 拼接 URL
        base = env.base_url.rstrip("/")
        path_clean = injected_path.lstrip("/")
        
        return f"{base}/{path_clean}"


# ========== 健康检查数据模型 (Issue #EM-005) ==========

@dataclass
class CheckResult:
    """单项检查结果"""
    status: str  # healthy, unhealthy, error
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class HealthReport:
    """健康检查报告"""
    environment: str
    environment_name: str
    timestamp: str
    overall_status: str  # healthy, degraded, unhealthy
    details: dict = field(default_factory=dict)


class HealthChecker:
    """
    环境健康检查器
    
    检查环境的 Web 和 API 端点可用性
    """
    
    DEFAULT_TIMEOUT = 10.0  # 默认超时 10 秒
    HEALTH_ENDPOINTS = ["/health", "/api/health", "/ping", "/api/ping"]
    
    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
    
    async def check_environment(self, env: Environment) -> HealthReport:
        """
        检查环境健康状态
        
        Args:
            env: 环境配置对象
        
        Returns:
            HealthReport: 健康检查报告
        """
        details = {}
        
        # 检查基础 URL
        web_result = await self._check_url(env.base_url)
        details["base_url"] = {
            "url": env.base_url,
            "status": web_result.status,
            "latency_ms": web_result.latency_ms,
            "error": web_result.error,
        }
        
        # 尝试检查健康端点
        health_result = await self._check_health_endpoint(env.base_url)
        if health_result:
            details["health_endpoint"] = {
                "status": health_result.status,
                "latency_ms": health_result.latency_ms,
                "error": health_result.error,
            }
        
        # 计算总体状态
        overall_status = self._calculate_overall_status(details)
        
        return HealthReport(
            environment=env.id,
            environment_name=env.name,
            timestamp=datetime.now(UTC).isoformat() + "Z",
            overall_status=overall_status,
            details=details,
        )
    
    async def _check_url(self, url: str) -> CheckResult:
        """检查单个 URL"""
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, follow_redirects=True)
                latency = (time.time() - start) * 1000
                
                if response.status_code < 400:
                    return CheckResult(status="healthy", latency_ms=round(latency, 2))
                else:
                    return CheckResult(
                        status="unhealthy",
                        latency_ms=round(latency, 2),
                        error=f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return CheckResult(status="unhealthy", error="Connection timeout")
        except httpx.ConnectError as e:
            return CheckResult(status="unhealthy", error=f"Connection failed: {str(e)[:100]}")
        except Exception as e:
            return CheckResult(status="error", error=str(e)[:100])
    
    async def _check_health_endpoint(self, base_url: str) -> CheckResult | None:
        """尝试检查健康端点"""
        base = base_url.rstrip("/")
        
        for endpoint in self.HEALTH_ENDPOINTS:
            url = f"{base}{endpoint}"
            result = await self._check_url(url)
            if result.status == "healthy":
                return result
        
        # 如果所有健康端点都失败，返回最后一个结果
        return None
    
    def _calculate_overall_status(self, details: dict) -> str:
        """计算总体健康状态"""
        statuses = [d.get("status") for d in details.values() if d.get("status")]
        
        if all(s == "healthy" for s in statuses):
            return "healthy"
        elif any(s == "error" for s in statuses):
            return "unhealthy"
        elif any(s == "unhealthy" for s in statuses):
            return "degraded"
        else:
            return "unknown"
    
    async def quick_check(self, url: str) -> bool:
        """
        快速检查 URL 是否可达
        
        Args:
            url: 要检查的 URL
        
        Returns:
            bool: 是否可达
        """
        result = await self._check_url(url)
        return result.status == "healthy"

