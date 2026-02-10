"""
环境管理模型

对应 Issue #EM-001: 环境配置
支持多环境管理、变量存储、加密敏感信息
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, JSON, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Environment(Base):
    """
    测试环境配置模型
    
    支持多环境 (dev/test/staging/prod) 配置管理
    """
    __tablename__ = "environments"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 基础配置
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 变量存储 (JSON 格式)
    # 格式: {"key": {"value": "xxx", "encrypted": false, "description": "..."}}
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # 请求头配置
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # 认证配置
    auth_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # none/basic/bearer/oauth2
    auth_config: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # 商业化预留: 租户隔离
    tenant_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def get_variable(self, key: str, default: str | None = None) -> str | None:
        """获取变量值"""
        var = self.variables.get(key)
        if var is None:
            return default
        return var.get("value", default)
    
    def to_dict(self, include_secrets: bool = False) -> dict:
        """转换为字典，可选择是否包含敏感信息"""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "base_url": self.base_url,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "headers": self.headers,
            "auth_type": self.auth_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        # 处理变量 - 隐藏加密值
        variables = {}
        for key, var in self.variables.items():
            if var.get("encrypted") and not include_secrets:
                variables[key] = {
                    "value": "******",
                    "encrypted": True,
                    "description": var.get("description", ""),
                }
            else:
                variables[key] = var
        result["variables"] = variables
        
        return result
