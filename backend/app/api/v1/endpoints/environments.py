"""
环境管理 API 端点

对应 Issue #EM-003, #EM-005
- GET /environments - 列出所有环境
- POST /environments - 创建环境
- GET /environments/{id} - 获取环境详情
- PUT /environments/{id} - 更新环境
- DELETE /environments/{id} - 删除环境
- GET /environments/{id}/variables - 获取环境变量
- POST /environments/{id}/variables - 设置变量
- DELETE /environments/{id}/variables/{key} - 删除变量
- GET /environments/{id}/health - 健康检查
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.environment_manager import EnvironmentManager, HealthChecker


router = APIRouter()


# ========== Pydantic Schemas ==========

class VariableSchema(BaseModel):
    """变量定义"""
    value: str
    encrypted: bool = False
    description: str = ""


class EnvironmentCreate(BaseModel):
    """创建环境请求"""
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1)
    description: Optional[str] = None
    variables: dict[str, VariableSchema | str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    auth_type: Optional[str] = None
    auth_config: dict = Field(default_factory=dict)
    is_default: bool = False


class EnvironmentUpdate(BaseModel):
    """更新环境请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = None
    description: Optional[str] = None
    variables: Optional[dict[str, VariableSchema | str]] = None
    headers: Optional[dict[str, str]] = None
    auth_type: Optional[str] = None
    auth_config: Optional[dict] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class VariableSet(BaseModel):
    """设置变量请求"""
    key: str = Field(..., min_length=1, max_length=100)
    value: str
    encrypted: bool = False
    description: str = ""


class EnvironmentResponse(BaseModel):
    """环境响应"""
    id: str
    name: str
    description: Optional[str]
    base_url: str
    is_active: bool
    is_default: bool
    variables: dict
    headers: dict
    auth_type: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    environment: str
    environment_name: str
    timestamp: str
    overall_status: str
    details: dict


class InjectRequest(BaseModel):
    """变量注入请求"""
    text: str
    additional_vars: dict[str, str] = Field(default_factory=dict)


# ========== API Endpoints ==========

@router.get("", response_model=list[EnvironmentResponse])
async def list_environments(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """列出所有环境"""
    manager = EnvironmentManager(db)
    envs = await manager.list_all(active_only=active_only)
    return [env.to_dict() for env in envs]


@router.post("", response_model=EnvironmentResponse, status_code=status.HTTP_201_CREATED)
async def create_environment(
    data: EnvironmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建新环境"""
    manager = EnvironmentManager(db)
    
    # 检查名称是否已存在
    existing = await manager.get_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"环境名称 '{data.name}' 已存在",
        )
    
    # 转换变量格式
    variables = {}
    for key, var in data.variables.items():
        if isinstance(var, str):
            variables[key] = {"value": var, "encrypted": False, "description": ""}
        else:
            variables[key] = var.model_dump()
    
    env = await manager.create(
        name=data.name,
        base_url=data.base_url,
        description=data.description,
        variables=variables,
        headers=data.headers,
        auth_type=data.auth_type,
        auth_config=data.auth_config,
        is_default=data.is_default,
    )
    await db.commit()
    return env.to_dict()


@router.get("/default", response_model=EnvironmentResponse)
async def get_default_environment(
    db: AsyncSession = Depends(get_db),
):
    """获取默认环境"""
    manager = EnvironmentManager(db)
    env = await manager.get_default()
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未设置默认环境",
        )
    return env.to_dict()


@router.get("/{env_id}", response_model=EnvironmentResponse)
async def get_environment(
    env_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取环境详情"""
    manager = EnvironmentManager(db)
    env = await manager.get(env_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境 '{env_id}' 不存在",
        )
    return env.to_dict()


@router.get("/{env_id}/health", response_model=HealthCheckResponse)
async def check_environment_health(
    env_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    检查环境健康状态
    
    返回环境的可用性检查结果，包括:
    - base_url 可达性
    - 健康端点 (/health, /api/health 等)
    - 响应延迟
    """
    manager = EnvironmentManager(db)
    env = await manager.get(env_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境 '{env_id}' 不存在",
        )
    
    checker = HealthChecker(timeout=10.0)
    report = await checker.check_environment(env)
    
    return HealthCheckResponse(
        environment=report.environment,
        environment_name=report.environment_name,
        timestamp=report.timestamp,
        overall_status=report.overall_status,
        details=report.details,
    )


@router.put("/{env_id}", response_model=EnvironmentResponse)
async def update_environment(
    env_id: str,
    data: EnvironmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新环境"""
    manager = EnvironmentManager(db)
    
    # 构建更新数据
    update_data = data.model_dump(exclude_unset=True)
    
    # 转换变量格式
    if "variables" in update_data and update_data["variables"]:
        variables = {}
        for key, var in update_data["variables"].items():
            if isinstance(var, str):
                variables[key] = {"value": var, "encrypted": False, "description": ""}
            elif isinstance(var, dict):
                variables[key] = var
            else:
                variables[key] = var.model_dump()
        update_data["variables"] = variables
    
    env = await manager.update(env_id, **update_data)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境 '{env_id}' 不存在",
        )
    await db.commit()
    return env.to_dict()


@router.delete("/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    env_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除环境"""
    manager = EnvironmentManager(db)
    success = await manager.delete(env_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境 '{env_id}' 不存在",
        )
    await db.commit()


# ========== 变量管理端点 ==========

@router.get("/{env_id}/variables")
async def get_environment_variables(
    env_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取环境的所有变量"""
    manager = EnvironmentManager(db)
    env = await manager.get(env_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境 '{env_id}' 不存在",
        )
    
    # 返回变量（隐藏加密值）
    variables = {}
    for key, var in env.variables.items():
        variables[key] = {
            "value": "******" if var.get("encrypted") else var.get("value", ""),
            "encrypted": var.get("encrypted", False),
            "description": var.get("description", ""),
        }
    return {"env_id": env_id, "variables": variables}


@router.post("/{env_id}/variables")
async def set_environment_variable(
    env_id: str,
    data: VariableSet,
    db: AsyncSession = Depends(get_db),
):
    """设置环境变量"""
    manager = EnvironmentManager(db)
    success = await manager.set_variable(
        env_id=env_id,
        key=data.key,
        value=data.value,
        encrypted=data.encrypted,
        description=data.description,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境 '{env_id}' 不存在",
        )
    await db.commit()
    return {"message": f"变量 '{data.key}' 已设置"}


@router.delete("/{env_id}/variables/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment_variable(
    env_id: str,
    key: str,
    db: AsyncSession = Depends(get_db),
):
    """删除环境变量"""
    manager = EnvironmentManager(db)
    success = await manager.delete_variable(env_id, key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境 '{env_id}' 或变量 '{key}' 不存在",
        )
    await db.commit()


# ========== 变量注入端点 ==========

@router.post("/{env_id}/inject")
async def inject_variables(
    env_id: str,
    data: InjectRequest,
    db: AsyncSession = Depends(get_db),
):
    """在文本中注入环境变量"""
    manager = EnvironmentManager(db)
    result = await manager.inject_variables(
        env_id=env_id,
        text=data.text,
        additional_vars=data.additional_vars,
    )
    return {"original": data.text, "injected": result}
