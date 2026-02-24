"""
凤凰涅槃层端点

Trace → 脚本编译
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.ai_client import get_ai_manager
from app.services.phoenix.service import PhoenixService
from app.services.phoenix.git_manager import GitManager
from app.core.config import settings
from app.core.database import get_db
from app.models.script import Script, CompilationStrategy

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

@router.get("/scripts", response_model=List[ScriptInfo])
async def list_scripts(
    skip: int = 0, 
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """获取全部编译脚本列表"""
    stmt = select(Script).order_by(Script.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    return [
        ScriptInfo(
            script_id=r.id,
            file_path=r.file_path,
            name=r.name,
            source_tc_id=r.source_tc_id,
            strategy=r.strategy.value,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat()
        )
        for r in records
    ]


@router.post("/compile", response_model=CompileResponse)
async def compile_trace(request: CompileRequest, ai_manager = Depends(get_ai_manager), db: AsyncSession = Depends(get_db)):
    """编译执行轨迹为测试脚本"""
    service = PhoenixService(ai_manager)
    trace_data = request.trace_data
    
    if not trace_data:
        raise HTTPException(
            status_code=400, 
            detail="trace_data is currently required in request body (DB lookup not implemented)"
        )
    
    try:
        script_content = await service.compile_trace_to_script(trace_data)
        
        script_id = f"SCRIPT_{uuid.uuid4().hex[:8]}"
        file_name = f"{script_id}.py"
        relative_path = os.path.join("scripts", file_name).replace("\\", "/")
        absolute_path = os.path.join(settings.GIT_REPO_PATH, relative_path)
        
        # 1. 保存到文件系统
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, "w", encoding="utf-8") as f:
            f.write(script_content)
            
        # 2. 提交到 Git 仓库
        git_manager = GitManager()
        commit_hash = git_manager.commit_file(relative_path, f"Auto-compiled script {script_id} from trace")
        
        # 3. 提取步数等信息并保存至 DB
        steps_count = len(trace_data.get("actions", [])) if isinstance(trace_data.get("actions"), list) else 0
        new_script = Script(
            id=script_id,
            name=trace_data.get("name", f"Compiled Script {script_id}"),
            source_tc_id=trace_data.get("scenario_id", ""),
            source_trace_id=request.trace_id,
            file_path=relative_path,
            strategy=CompilationStrategy.OPTIMIZED,
            step_count=steps_count,
            git_commit=commit_hash
        )
        db.add(new_script)
        await db.commit()
        
        return CompileResponse(
            script_id=script_id,
            file_path=relative_path,
            code_preview=script_content,
            parameters_extracted=0,
            steps_generated=steps_count
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scripts/{script_id}", response_model=ScriptInfo)
async def get_script(script_id: str, db: AsyncSession = Depends(get_db)):
    """获取脚本信息"""
    stmt = select(Script).where(Script.id == script_id)
    result = await db.execute(stmt)
    script = result.scalars().first()
    
    if not script:
        raise HTTPException(status_code=404, detail=f"脚本 {script_id} 不存在")
        
    return ScriptInfo(
        script_id=script.id,
        file_path=script.file_path,
        name=script.name,
        source_tc_id=script.source_tc_id,
        strategy=script.strategy.value,
        created_at=script.created_at.isoformat(),
        updated_at=script.updated_at.isoformat()
    )


@router.get("/scripts/{script_id}/code")
async def get_script_code(script_id: str, db: AsyncSession = Depends(get_db)):
    """获取脚本代码内容"""
    stmt = select(Script).where(Script.id == script_id)
    result = await db.execute(stmt)
    script = result.scalars().first()
    
    if not script:
        raise HTTPException(status_code=404, detail=f"脚本 {script_id} 不存在")
        
    absolute_path = os.path.join(settings.GIT_REPO_PATH, script.file_path)
    if not os.path.exists(absolute_path):
        raise HTTPException(status_code=404, detail=f"物理文件丢失: {script.file_path}")
        
    with open(absolute_path, "r", encoding="utf-8") as f:
        code = f.read()
        
    return {"code": code}


@router.get("/scripts/{script_id}/history", response_model=List[VersionInfo])
async def get_script_history(
    script_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取脚本版本历史"""
    stmt = select(Script).where(Script.id == script_id)
    result = await db.execute(stmt)
    script = result.scalars().first()
    
    if not script:
        raise HTTPException(status_code=404, detail=f"脚本 {script_id} 不存在")
        
    git_manager = GitManager()
    commits = git_manager.get_history(max_count=limit, file_path=script.file_path)
    
    history = []
    for commit in commits:
        history.append(VersionInfo(
            version=commit["hash"][:7],
            author=commit["author"],
            date=commit["date"],
            message=commit["message"],
            changes=""
        ))
    return history


@router.post("/scripts/{script_id}/heal")
async def apply_healing(
    request: HealingRequest,
    ai_manager = Depends(get_ai_manager)
):
    """应用自愈修复"""
    service = PhoenixService(ai_manager)
    healing_result = await service.heal_script(request.broken_code, request.error_log)
    return {
        "script_id": request.script_id,
        "status": "healed",
        "original_code": request.broken_code,
        "fixed_code": healing_result.get("fix_code"),
        "analysis": healing_result.get("analysis")
    }
