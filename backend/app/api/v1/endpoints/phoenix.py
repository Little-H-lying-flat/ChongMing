"""
凤凰涅槃层端点

Trace → 脚本编译
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.core.ai_client import get_ai_manager
from app.services.phoenix.service import PhoenixService

router = APIRouter()


# ===================== 数据模型 =====================

class CompileRequest(BaseModel):
    """编译请求"""
    trace_id: str = Field(..., description="Trace ID")
    trace_data: Optional[Dict[str, Any]] = Field(None, description="完整 Trace 数据 (优先使用)")
    strategy: str = Field("optimized", description="编译策略: exact, optimized, data_driven, hybrid")
    output_format: str = Field("pytest", description="输出格式: pytest, unittest")
    options: dict = Field(default_factory=dict, description="编译选项")


class CompileResponse(BaseModel):
    """编译响应"""
    script_id: str
    file_path: str
    code_preview: str
    parameters_extracted: int
    steps_generated: int


class ScriptInfo(BaseModel):
    """脚本信息"""
    script_id: str
    file_path: str
    name: str
    source_tc_id: str
    strategy: str
    created_at: str
    updated_at: str


class VersionInfo(BaseModel):
    """版本信息"""
    version: str
    author: str
    date: str
    message: str
    changes: str

class HealingRequest(BaseModel):
    """自愈请求"""
    script_id: str
    healing_record_id: str
    error_log: str = Field(..., description="错误日志")
    broken_code: str = Field(..., description="报错的代码片段")


# ===================== API 端点 =====================

@router.post("/compile", response_model=CompileResponse)
async def compile_trace(request: CompileRequest, ai_manager = Depends(get_ai_manager)):
    """
    编译执行轨迹为测试脚本
    
    将 Trace Log 转化为 Python 测试代码
    """
    service = PhoenixService(ai_manager)
    
    # Prioritize trace_data from request body
    trace_data = request.trace_data
    
    if not trace_data:
        # Fallback: Fetch from DB using trace_id (Not implemented yet)
        # For now, if no data provided, we must fail rather than using hardcoded mock
        raise HTTPException(
            status_code=400, 
            detail="trace_data is currently required in request body (DB lookup not implemented)"
        )
    
    try:
        script_content = await service.compile_trace_to_script(trace_data)
        
        # In real implementation: Save script to file/db and return path
        import uuid
        script_id = f"SCRIPT_{uuid.uuid4().hex[:8]}"
        
        return CompileResponse(
            script_id=script_id,
            file_path=f"/scripts/{script_id}.py",
            code_preview=script_content,
            parameters_extracted=0,
            # Estimate steps from actions if available
            steps_generated=len(trace_data.get("actions", [])) if isinstance(trace_data.get("actions"), list) else 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scripts/{script_id}", response_model=ScriptInfo)
async def get_script(script_id: str):
    """
    获取脚本信息
    """
    # TODO: 从资产库查询
    raise HTTPException(status_code=404, detail=f"脚本 {script_id} 不存在")


@router.get("/scripts/{script_id}/code")
async def get_script_code(script_id: str):
    """
    获取脚本代码内容
    """
    # TODO: 从文件系统读取
    raise HTTPException(status_code=404, detail=f"脚本 {script_id} 不存在")


@router.get("/scripts/{script_id}/history")
async def get_script_history(
    script_id: str,
    limit: int = 20,
):
    """
    获取脚本版本历史
    """
    # TODO: 从 Git 查询
    return []


@router.post("/scripts/{script_id}/heal")
async def apply_healing(
    request: HealingRequest,
    ai_manager = Depends(get_ai_manager)
):
    """
    应用自愈修复
    
    将成功的修复策略固化到脚本
    """
    service = PhoenixService(ai_manager)
    
    healing_result = await service.heal_script(request.broken_code, request.error_log)
    
    return {
        "script_id": request.script_id,
        "status": "healed",
        "original_code": request.broken_code,
        "fixed_code": healing_result.get("fix_code"),
        "analysis": healing_result.get("analysis")
    }
