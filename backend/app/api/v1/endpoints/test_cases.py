"""
测试用例管理端点

对应 TC-IR 资产的 CRUD 操作
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.test_case_service import TestCaseService

router = APIRouter()


# ===================== 数据模型 =====================


class TCIRCreate(BaseModel):
    """创建测试用例请求"""
    name: str = Field(..., description="用例名称", max_length=200)
    description: Optional[str] = Field(None, description="用例描述")
    mode: str = Field("UI", description="执行模式: UI, API, HYBRID")
    priority: str = Field("P1", description="优先级: P0, P1, P2, P3")
    steps: List[Dict[str, Any]] = Field(..., description="执行步骤")
    tags: List[str] = Field(default_factory=list, description="标签")


class TCIRResponse(BaseModel):
    """测试用例响应"""
    id: str
    name: str
    description: Optional[str]
    mode: str
    priority: str
    status: str
    steps: List[Dict[str, Any]]
    tags: List[str]
    created_at: str
    updated_at: str


class TCIRListResponse(BaseModel):
    """测试用例列表响应"""
    items: List[TCIRResponse]
    total: int
    page: int
    page_size: int


# ===================== API 端点 =====================

@router.get("", response_model=TCIRListResponse)
async def list_test_cases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态过滤"),
    mode: Optional[str] = Query(None, description="模式过滤"),
    tag: Optional[str] = Query(None, description="标签过滤"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取测试用例列表
    
    支持分页和过滤
    """
    service = TestCaseService(db)
    items = await service.list(page=page, page_size=page_size, status=status, mode=mode, tag=tag)
    total = await service.count(status=status, mode=mode)
    
    # Model conversion
    # Note: DB model fields need to map to Pydantic model
    # Simple conversion here for MVP
    response_items = []
    for item in items:
        response_items.append(TCIRResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            mode=item.mode.value,
            priority=item.priority.value,
            status=item.status.value,
            steps=item.steps, # Assumes dict matches Pydantic model
            tags=item.tags,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat()
        ))

    return TCIRListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TCIRResponse, status_code=201)
async def create_test_case(tc: TCIRCreate, db: AsyncSession = Depends(get_db)):
    """
    创建测试用例
    
    将 TC-IR 存入资产库
    """
    service = TestCaseService(db)
    
    # Convert Pydantic to Dict
    tc_data = tc.dict()
    # Pydantic model uses 'steps' as List[TCIRStep], DB uses JSON.
    # .dict() conversion should be fine for JSON field if compatible.
    # Enum handling: Pydantic 'mode' is string, DB expects Enum? 
    # Actually DB model uses String Enum, it should digest string values fine if they match.
    
    try:
        created = await service.create(tc_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create test case: {str(e)}")
        
    return TCIRResponse(
            id=created.id,
            name=created.name,
            description=created.description,
            mode=created.mode.value,
            priority=created.priority.value,
            status=created.status.value,
            steps=created.steps,
            tags=created.tags,
            created_at=created.created_at.isoformat(),
            updated_at=created.updated_at.isoformat()
    )


@router.get("/{tc_id}", response_model=TCIRResponse)
async def get_test_case(tc_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取单个测试用例详情
    """
    service = TestCaseService(db)
    item = await service.get(tc_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"测试用例 {tc_id} 不存在")
        
    return TCIRResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            mode=item.mode.value,
            priority=item.priority.value,
            status=item.status.value,
            steps=item.steps,
            tags=item.tags,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat()
    )


@router.put("/{tc_id}", response_model=TCIRResponse)
async def update_test_case(tc_id: str, tc: TCIRCreate, db: AsyncSession = Depends(get_db)):
    """
    更新测试用例
    """
    service = TestCaseService(db)
    item = await service.update(tc_id, tc.dict(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=404, detail=f"测试用例 {tc_id} 不存在")
        
    return TCIRResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            mode=item.mode.value,
            priority=item.priority.value,
            status=item.status.value,
            steps=item.steps,
            tags=item.tags,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat()
    )


@router.delete("/{tc_id}", status_code=204)
async def delete_test_case(tc_id: str, db: AsyncSession = Depends(get_db)):
    """
    删除测试用例
    """
    service = TestCaseService(db)
    deleted = await service.delete(tc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"测试用例 {tc_id} 不存在")
