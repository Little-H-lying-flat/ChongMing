"""Test case management endpoints (TC-IR CRUD)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.api_case_ir_converter import normalize_api_case_payload_v2, normalize_api_steps_v2
from app.services.test_case_service import TestCaseService

router = APIRouter()


class TCIRCreate(BaseModel):
    name: str = Field(..., description="Case name", max_length=200)
    description: Optional[str] = Field(None, description="Case description")
    mode: str = Field("UI", description="Execution mode: UI, API, HYBRID")
    priority: str = Field("P1", description="Priority: P0, P1, P2, P3")
    status: Optional[str] = Field(None, description="Lifecycle state")
    steps: List[Dict[str, Any]] = Field(..., description="Execution steps")
    tags: List[str] = Field(default_factory=list, description="Tags")


class TCIRResponse(BaseModel):
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
    items: List[TCIRResponse]
    total: int
    page: int
    page_size: int


def _to_response(item) -> TCIRResponse:
    mode = item.mode.value if hasattr(item.mode, "value") else item.mode
    priority = item.priority.value if hasattr(item.priority, "value") else item.priority
    status = item.status.value if hasattr(item.status, "value") else item.status
    return TCIRResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        mode=mode,
        priority=priority,
        status=status,
        steps=normalize_api_steps_v2(item.steps or [], mode),
        tags=item.tags,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("", response_model=TCIRListResponse)
async def list_test_cases(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    status: Optional[str] = Query(None, description="Status filter"),
    mode: Optional[str] = Query(None, description="Mode filter"),
    tag: Optional[str] = Query(None, description="Tag filter"),
    db: AsyncSession = Depends(get_db),
):
    service = TestCaseService(db)
    items = await service.list(page=page, page_size=page_size, status=status, mode=mode, tag=tag)
    total = await service.count(status=status, mode=mode)

    return TCIRListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TCIRResponse, status_code=201)
async def create_test_case(tc: TCIRCreate, db: AsyncSession = Depends(get_db)):
    service = TestCaseService(db)
    tc_data = tc.model_dump(exclude_none=True)

    try:
        created = await service.create(normalize_api_case_payload_v2(tc_data))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create test case: {exc}")

    return _to_response(created)


@router.get("/{tc_id}", response_model=TCIRResponse)
async def get_test_case(tc_id: str, db: AsyncSession = Depends(get_db)):
    service = TestCaseService(db)
    item = await service.get(tc_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Test case {tc_id} not found")
    return _to_response(item)


@router.put("/{tc_id}", response_model=TCIRResponse)
async def update_test_case(tc_id: str, tc: TCIRCreate, db: AsyncSession = Depends(get_db)):
    service = TestCaseService(db)

    try:
        item = await service.update(
            tc_id,
            normalize_api_case_payload_v2(tc.model_dump(exclude_unset=True, exclude_none=True)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not item:
        raise HTTPException(status_code=404, detail=f"Test case {tc_id} not found")

    return _to_response(item)


@router.delete("/{tc_id}", status_code=204)
async def delete_test_case(tc_id: str, db: AsyncSession = Depends(get_db)):
    service = TestCaseService(db)
    result = await service.delete(tc_id)

    if result == "not_found":
        raise HTTPException(status_code=404, detail=f"Test case {tc_id} not found")
    if result == "referenced":
        raise HTTPException(status_code=409, detail=f"Test case {tc_id} is referenced by executions")

    return None
