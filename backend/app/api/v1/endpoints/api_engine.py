"""Compatibility API endpoints for legacy /api-engine routes."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Response, status
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter()

DEPRECATION_NOTICE = "true"
SUNSET_DATE = "2026-09-30"
MIGRATION_DOC = "/docs/api-migration-left-pupil.md"


def _mark_api_engine_deprecated(response: Response) -> None:
    response.headers["Deprecation"] = DEPRECATION_NOTICE
    response.headers["Sunset"] = SUNSET_DATE
    response.headers["Link"] = f"<{MIGRATION_DOC}>; rel=\"deprecation\""
    logger.warning("Deprecated endpoint '/api-engine/*' called. Migrate to '/left-pupil/*'.")


class AuthConfigRequest(BaseModel):
    auth_type: str = Field(default="none", description="none, bearer, basic, api_key")
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key_name: Optional[str] = None
    api_key_value: Optional[str] = None
    api_key_location: str = Field(default="header", description="header or query")


class AssertionRequest(BaseModel):
    type: str
    expected: Optional[Any] = None
    path: Optional[str] = None
    operator: Optional[str] = "equals"


class APIIRRequest(BaseModel):
    method: str = "GET"
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, Any] = Field(default_factory=dict)
    path_params: Dict[str, Any] = Field(default_factory=dict)
    body: Optional[Any] = None
    content_type: str = "application/json"
    timeout: float = 30.0
    assertions: List[AssertionRequest] = Field(default_factory=list)
    extract: Dict[str, str] = Field(default_factory=dict)


class ExecuteAPIRequest(BaseModel):
    api_ir: APIIRRequest
    auth_config: Optional[AuthConfigRequest] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = False


class ExecuteChainRequest(BaseModel):
    chain: List[APIIRRequest]
    auth_config: Optional[AuthConfigRequest] = None
    initial_context: Dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = False


class SwaggerParseRequest(BaseModel):
    url: Optional[str] = None
    content: Optional[str] = None
    content_type: str = "json"


class ExecuteResultResponse(BaseModel):
    success: bool
    status_code: Optional[int]
    duration_ms: Optional[float]
    body: Optional[Any]
    assertions_passed: List[str]
    assertions_failed: List[str]
    extracted_values: Dict[str, Any]
    error: Optional[str]


class AsyncTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


@router.post("/execute", response_model=ExecuteResultResponse, summary="Execute single API test")
async def execute_api(request: ExecuteAPIRequest, response: Response):
    _mark_api_engine_deprecated(response)

    if request.async_mode:
        from app.tasks.api_tasks import execute_api_test

        task = execute_api_test.delay(
            api_ir=request.api_ir.model_dump(),
            auth_config=request.auth_config.model_dump() if request.auth_config else None,
            context=request.context,
        )
        return {
            "success": True,
            "status_code": None,
            "duration_ms": None,
            "body": None,
            "assertions_passed": [],
            "assertions_failed": [],
            "extracted_values": {"task_id": task.id},
            "error": None,
        }

    from app.engines.left_pupil import APIExecutor, AuthConfig, AuthType
    from app.schemas.execution import APIIR

    try:
        ir = APIIR(
            method=request.api_ir.method,
            url=request.api_ir.url,
            headers=request.api_ir.headers,
            query_params=request.api_ir.query_params,
            path_params=request.api_ir.path_params,
            body=request.api_ir.body,
            content_type=request.api_ir.content_type,
            timeout=request.api_ir.timeout,
            assertions=[a.model_dump() for a in request.api_ir.assertions],
            extract=request.api_ir.extract,
        )

        auth = None
        if request.auth_config:
            auth = AuthConfig(
                auth_type=AuthType(request.auth_config.auth_type),
                token=request.auth_config.token,
                username=request.auth_config.username,
                password=request.auth_config.password,
                api_key_name=request.auth_config.api_key_name,
                api_key_value=request.auth_config.api_key_value,
                api_key_location=request.auth_config.api_key_location,
            )

        async with APIExecutor(auth_config=auth) as executor:
            if request.context:
                executor.update_context(request.context)
            result = await executor.execute(ir)

        return ExecuteResultResponse(
            success=result.success,
            status_code=result.response.status_code if result.response else None,
            duration_ms=result.response.duration_ms if result.response else None,
            body=result.response.body if result.response else None,
            assertions_passed=result.assertions_passed,
            assertions_failed=result.assertions_failed,
            extracted_values=result.extracted_values,
            error=result.error,
        )
    except Exception as exc:
        logger.error(f"API execution failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/execute/chain", summary="Execute chained API tests")
async def execute_api_chain(request: ExecuteChainRequest, response: Response):
    _mark_api_engine_deprecated(response)

    if request.async_mode:
        from app.tasks.api_tasks import execute_api_chain as task_chain

        task = task_chain.delay(
            chain=[ir.model_dump() for ir in request.chain],
            auth_config=request.auth_config.model_dump() if request.auth_config else None,
            initial_context=request.initial_context,
        )
        return AsyncTaskResponse(task_id=task.id, status="pending", message="Chain task submitted")

    from app.engines.left_pupil import APIExecutor, AuthConfig, AuthType
    from app.schemas.execution import APIIR

    try:
        auth = None
        if request.auth_config:
            auth = AuthConfig(
                auth_type=AuthType(request.auth_config.auth_type),
                token=request.auth_config.token,
                username=request.auth_config.username,
                password=request.auth_config.password,
                api_key_name=request.auth_config.api_key_name,
                api_key_value=request.auth_config.api_key_value,
                api_key_location=request.auth_config.api_key_location,
            )

        results = []
        context = request.initial_context.copy()

        async with APIExecutor(auth_config=auth) as executor:
            executor.update_context(context)
            for i, api_ir in enumerate(request.chain):
                ir = APIIR(
                    method=api_ir.method,
                    url=api_ir.url,
                    headers=api_ir.headers,
                    query_params=api_ir.query_params,
                    path_params=api_ir.path_params,
                    body=api_ir.body,
                    content_type=api_ir.content_type,
                    assertions=[a.model_dump() for a in api_ir.assertions],
                    extract=api_ir.extract,
                )
                result = await executor.execute(ir)
                context.update(result.extracted_values)
                results.append(
                    {
                        "step": i + 1,
                        "url": api_ir.url,
                        "method": api_ir.method,
                        "success": result.success,
                        "status_code": result.response.status_code if result.response else None,
                        "duration_ms": result.response.duration_ms if result.response else None,
                        "assertions_passed": result.assertions_passed,
                        "assertions_failed": result.assertions_failed,
                        "extracted_values": result.extracted_values,
                        "error": result.error,
                    }
                )
                if not result.success:
                    break

        passed = sum(1 for r in results if r["success"])
        return {
            "total": len(request.chain),
            "executed": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "results": results,
            "final_context": context,
        }
    except Exception as exc:
        logger.error(f"Chain execution failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/swagger/parse", summary="Parse Swagger")
async def parse_swagger(request: SwaggerParseRequest, response: Response):
    _mark_api_engine_deprecated(response)
    from app.engines.left_pupil import SwaggerParser

    try:
        parser = SwaggerParser()
        if request.url:
            spec = await parser.load_from_url(request.url)
        elif request.content:
            import json
            import yaml

            data = yaml.safe_load(request.content) if request.content_type == "yaml" else json.loads(request.content)
            spec = parser.load_from_dict(data)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url or content is required")

        return {
            "title": spec.title,
            "version": spec.version,
            "description": spec.description,
            "base_url": spec.base_url,
            "openapi_version": spec.openapi_version.value,
            "endpoints_count": len(spec.endpoints),
            "endpoints": [
                {
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "operation_id": endpoint.operation_id,
                    "summary": endpoint.summary,
                    "tags": endpoint.tags,
                    "deprecated": endpoint.deprecated,
                }
                for endpoint in spec.endpoints
            ],
            "security_schemes": spec.security_schemes,
        }
    except Exception as exc:
        logger.error(f"Swagger parse failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/swagger/generate-ir", summary="Generate API-IR from Swagger")
async def generate_api_ir_from_swagger(
    swagger_url: str,
    endpoint_path: str,
    method: str = "GET",
    response: Optional[Response] = None,
):
    if response is not None:
        _mark_api_engine_deprecated(response)

    from app.engines.left_pupil import SwaggerParser

    try:
        parser = SwaggerParser()
        spec = await parser.load_from_url(swagger_url)

        endpoint = None
        for item in spec.endpoints:
            if item.path == endpoint_path and item.method == method.upper():
                endpoint = item
                break

        if endpoint is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Endpoint not found: {method} {endpoint_path}",
            )

        api_ir = parser.generate_api_ir(endpoint, spec.base_url)
        return {
            "endpoint": {
                "path": endpoint.path,
                "method": endpoint.method,
                "summary": endpoint.summary,
            },
            "api_ir": api_ir,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Generate API-IR failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


for route in router.routes:
    route.deprecated = True
