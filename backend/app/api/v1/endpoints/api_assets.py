"""API asset catalog endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.api_asset import ApiAsset
from app.services.api_asset_service import ApiAssetConflictError, ApiAssetService

router = APIRouter()


class ApiAssetCreate(BaseModel):
    method: str = Field(..., description="HTTP method")
    path: str = Field(..., description="Endpoint path")
    name: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    operation_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Any] = Field(default_factory=dict)
    security: List[Dict[str, Any]] = Field(default_factory=list)
    base_url: Optional[str] = None
    source_name: Optional[str] = None
    deprecated: bool = False


class ApiAssetUpdate(BaseModel):
    method: Optional[str] = None
    path: Optional[str] = None
    name: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    operation_id: Optional[str] = None
    tags: Optional[List[str]] = None
    parameters: Optional[List[Dict[str, Any]]] = None
    request_body: Optional[Dict[str, Any]] = None
    responses: Optional[Dict[str, Any]] = None
    security: Optional[List[Dict[str, Any]]] = None
    base_url: Optional[str] = None
    source_name: Optional[str] = None
    deprecated: Optional[bool] = None


class ApiAssetResponse(BaseModel):
    id: str
    asset_key: str
    source_name: str
    source_type: str
    source_url: Optional[str]
    spec_title: Optional[str]
    spec_version: Optional[str]
    base_url: Optional[str]
    name: str
    method: str
    path: str
    summary: Optional[str]
    description: Optional[str]
    operation_id: Optional[str]
    tags: List[str]
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[str, Any]
    security: List[Dict[str, Any]]
    deprecated: bool
    created_at: str
    updated_at: str


class ApiAssetListResponse(BaseModel):
    items: List[ApiAssetResponse]
    total: int
    page: int
    page_size: int


class OpenAPIImportRequest(BaseModel):
    url: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    source_name: Optional[str] = None


class OpenAPIImportResponse(BaseModel):
    success: bool
    source_name: str
    spec_title: str = ""
    spec_version: str = ""
    parsed_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    asset_ids: List[str] = Field(default_factory=list)


class ApiIRStepResponse(BaseModel):
    step: Dict[str, Any]


def _to_response(asset: ApiAsset) -> ApiAssetResponse:
    return ApiAssetResponse(
        id=asset.id,
        asset_key=asset.asset_key,
        source_name=asset.source_name,
        source_type=asset.source_type,
        source_url=asset.source_url,
        spec_title=asset.spec_title,
        spec_version=asset.spec_version,
        base_url=asset.base_url,
        name=asset.name,
        method=asset.method,
        path=asset.path,
        summary=asset.summary,
        description=asset.description,
        operation_id=asset.operation_id,
        tags=asset.tags or [],
        parameters=asset.parameters or [],
        request_body=asset.request_body,
        responses=asset.responses or {},
        security=asset.security or [],
        deprecated=asset.deprecated,
        created_at=asset.created_at.isoformat(),
        updated_at=asset.updated_at.isoformat(),
    )


@router.post("/import-openapi", response_model=OpenAPIImportResponse)
async def import_openapi(request: OpenAPIImportRequest, db: AsyncSession = Depends(get_db)):
    has_url = bool(request.url)
    has_content = request.content is not None
    if has_url == has_content:
        raise HTTPException(status_code=400, detail="必须且只能提供 url 或 content")

    service = ApiAssetService(db)
    try:
        if request.url:
            result = await service.import_from_url(request.url, source_name=request.source_name)
        else:
            result = await service.import_from_spec(request.content or {}, source_name=request.source_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OpenAPI 导入失败: {exc}")

    return OpenAPIImportResponse(**result)


@router.get("", response_model=ApiAssetListResponse)
async def list_api_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    source_name: Optional[str] = Query(None),
    deprecated: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = ApiAssetService(db)
    items = await service.list(
        page=page,
        page_size=page_size,
        keyword=keyword,
        method=method,
        tag=tag,
        source_name=source_name,
        deprecated=deprecated,
    )
    total = await service.count(
        keyword=keyword,
        method=method,
        tag=tag,
        source_name=source_name,
        deprecated=deprecated,
    )
    return ApiAssetListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ApiAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_api_asset(payload: ApiAssetCreate, db: AsyncSession = Depends(get_db)):
    service = ApiAssetService(db)
    try:
        created = await service.create(payload.model_dump(exclude_none=True))
    except ApiAssetConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_response(created)


@router.get("/{asset_id}/api-ir-step", response_model=ApiIRStepResponse)
async def get_api_asset_ir_step(asset_id: str, db: AsyncSession = Depends(get_db)):
    service = ApiAssetService(db)
    asset = await service.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"API asset {asset_id} not found")
    return ApiIRStepResponse(step=service.to_api_ir_step(asset))


@router.get("/{asset_id}", response_model=ApiAssetResponse)
async def get_api_asset(asset_id: str, db: AsyncSession = Depends(get_db)):
    service = ApiAssetService(db)
    asset = await service.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"API asset {asset_id} not found")
    return _to_response(asset)


@router.put("/{asset_id}", response_model=ApiAssetResponse)
async def update_api_asset(asset_id: str, payload: ApiAssetUpdate, db: AsyncSession = Depends(get_db)):
    service = ApiAssetService(db)
    try:
        asset = await service.update(asset_id, payload.model_dump(exclude_unset=True, exclude_none=True))
    except ApiAssetConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if asset is None:
        raise HTTPException(status_code=404, detail=f"API asset {asset_id} not found")
    return _to_response(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_asset(asset_id: str, db: AsyncSession = Depends(get_db)):
    service = ApiAssetService(db)
    deleted = await service.delete(asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"API asset {asset_id} not found")
    return None
