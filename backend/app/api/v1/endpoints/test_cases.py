"""
测试用例管理端点

对应 TC-IR 资产的 CRUD 操作
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


# ===================== 数据模型 =====================

class TCIRStep(BaseModel):
    """TC-IR 步骤"""
    action: str = Field(..., description="动作类型: click, input, verify, etc.")
    target: str = Field(..., description="目标描述")
    value: Optional[str] = Field(None, description="输入值")
    expected: Optional[str] = Field(None, description="预期结果")


class TCIRCreate(BaseModel):
    """创建测试用例请求"""
    name: str = Field(..., description="用例名称", max_length=200)
    description: Optional[str] = Field(None, description="用例描述")
    mode: str = Field("UI", description="执行模式: UI, API, HYBRID")
    priority: str = Field("P1", description="优先级: P0, P1, P2, P3")
    steps: List[TCIRStep] = Field(..., description="执行步骤")
    tags: List[str] = Field(default_factory=list, description="标签")


class TCIRResponse(BaseModel):
    """测试用例响应"""
    id: str
    name: str
    description: Optional[str]
    mode: str
    priority: str
    status: str
    steps: List[TCIRStep]
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
):
    """
    获取测试用例列表
    
    支持分页和过滤
    """
    # TODO: 从数据库查询
    return TCIRListResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TCIRResponse, status_code=201)
async def create_test_case(tc: TCIRCreate):
    """
    创建测试用例
    
    将 TC-IR 存入资产库
    """
    # TODO: 保存到数据库
    raise HTTPException(status_code=501, detail="尚未实现")


@router.get("/{tc_id}", response_model=TCIRResponse)
async def get_test_case(tc_id: str):
    """
    获取单个测试用例详情
    """
    # TODO: 从数据库查询
    raise HTTPException(status_code=404, detail=f"测试用例 {tc_id} 不存在")


@router.put("/{tc_id}", response_model=TCIRResponse)
async def update_test_case(tc_id: str, tc: TCIRCreate):
    """
    更新测试用例
    """
    # TODO: 更新数据库
    raise HTTPException(status_code=501, detail="尚未实现")


@router.delete("/{tc_id}", status_code=204)
async def delete_test_case(tc_id: str):
    """
    删除测试用例
    """
    # TODO: 从数据库删除
    raise HTTPException(status_code=501, detail="尚未实现")
