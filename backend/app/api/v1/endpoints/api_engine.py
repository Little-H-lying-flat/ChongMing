"""
左瞳引擎 API 端点

对应 Issue: #LP-007
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger


router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic 模型
# ═══════════════════════════════════════════════════════════════════════════════

class AuthConfigRequest(BaseModel):
    """认证配置请求"""
    auth_type: str = Field(default="none", description="认证类型: none, bearer, basic, api_key")
    token: Optional[str] = Field(default=None, description="Bearer Token")
    username: Optional[str] = Field(default=None, description="Basic Auth 用户名")
    password: Optional[str] = Field(default=None, description="Basic Auth 密码")
    api_key_name: Optional[str] = Field(default=None, description="API Key 名称")
    api_key_value: Optional[str] = Field(default=None, description="API Key 值")
    api_key_location: str = Field(default="header", description="API Key 位置: header, query")


class AssertionRequest(BaseModel):
    """断言配置"""
    type: str = Field(..., description="断言类型")
    expected: Optional[Any] = Field(default=None, description="期望值")
    path: Optional[str] = Field(default=None, description="JSONPath")
    operator: Optional[str] = Field(default="equals", description="操作符")


class APIIRRequest(BaseModel):
    """API-IR 请求"""
    method: str = Field(default="GET", description="HTTP 方法")
    url: str = Field(..., description="请求 URL")
    headers: Dict[str, str] = Field(default_factory=dict, description="请求头")
    query_params: Dict[str, Any] = Field(default_factory=dict, description="查询参数")
    path_params: Dict[str, Any] = Field(default_factory=dict, description="路径参数")
    body: Optional[Any] = Field(default=None, description="请求体")
    content_type: str = Field(default="application/json", description="Content-Type")
    timeout: float = Field(default=30.0, description="超时时间(秒)")
    assertions: List[AssertionRequest] = Field(default_factory=list, description="断言列表")
    extract: Dict[str, str] = Field(default_factory=dict, description="变量提取规则")


class ExecuteAPIRequest(BaseModel):
    """执行 API 请求"""
    api_ir: APIIRRequest
    auth_config: Optional[AuthConfigRequest] = None
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文变量")
    async_mode: bool = Field(default=False, description="异步执行")


class ExecuteChainRequest(BaseModel):
    """执行链式 API 请求"""
    chain: List[APIIRRequest]
    auth_config: Optional[AuthConfigRequest] = None
    initial_context: Dict[str, Any] = Field(default_factory=dict, description="初始上下文")
    async_mode: bool = Field(default=False, description="异步执行")


class SwaggerParseRequest(BaseModel):
    """Swagger 解析请求"""
    url: Optional[str] = Field(default=None, description="Swagger URL")
    content: Optional[str] = Field(default=None, description="Swagger 内容")
    content_type: str = Field(default="json", description="内容类型: json, yaml")


class AssertionResultResponse(BaseModel):
    """断言结果响应"""
    type: str
    expected: Any
    actual: Any
    passed: bool
    message: str


class ExecuteResultResponse(BaseModel):
    """执行结果响应"""
    success: bool
    status_code: Optional[int]
    duration_ms: Optional[float]
    body: Optional[Any]
    assertions_passed: List[str]
    assertions_failed: List[str]
    extracted_values: Dict[str, Any]
    error: Optional[str]


class AsyncTaskResponse(BaseModel):
    """异步任务响应"""
    task_id: str
    status: str
    message: str


# ═══════════════════════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/execute",
    response_model=ExecuteResultResponse,
    summary="执行单个 API 测试",
)
async def execute_api(request: ExecuteAPIRequest):
    """
    执行单个 API 测试
    
    支持同步和异步执行模式
    """
    if request.async_mode:
        # 异步执行
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
    
    # 同步执行
    from app.engines.left_pupil import APIExecutor, APIIR, AuthConfig, AuthType
    
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
        
    except Exception as e:
        logger.error(f"API 执行失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/execute/chain",
    summary="执行链式 API 测试",
)
async def execute_api_chain(request: ExecuteChainRequest):
    """
    执行链式 API 测试
    
    支持变量提取和自动注入
    """
    if request.async_mode:
        from app.tasks.api_tasks import execute_api_chain as task_chain
        
        task = task_chain.delay(
            chain=[ir.model_dump() for ir in request.chain],
            auth_config=request.auth_config.model_dump() if request.auth_config else None,
            initial_context=request.initial_context,
        )
        
        return AsyncTaskResponse(
            task_id=task.id,
            status="pending",
            message="链式执行任务已提交",
        )
    
    # 同步执行
    from app.engines.left_pupil import APIExecutor, APIIR, AuthConfig, AuthType
    
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
                
                results.append({
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
                })
                
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
        
    except Exception as e:
        logger.error(f"链式执行失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/swagger/parse", summary="解析 Swagger 文档")
async def parse_swagger(request: SwaggerParseRequest):
    """
    解析 Swagger/OpenAPI 文档
    
    支持 URL 和内容解析
    """
    from app.engines.left_pupil import SwaggerParser
    
    try:
        parser = SwaggerParser()
        
        if request.url:
            spec = await parser.load_from_url(request.url)
        elif request.content:
            import json
            import yaml
            
            if request.content_type == "yaml":
                data = yaml.safe_load(request.content)
            else:
                data = json.loads(request.content)
            
            spec = parser.load_from_dict(data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="必须提供 url 或 content",
            )
        
        return {
            "title": spec.title,
            "version": spec.version,
            "description": spec.description,
            "base_url": spec.base_url,
            "openapi_version": spec.openapi_version.value,
            "endpoints_count": len(spec.endpoints),
            "endpoints": [
                {
                    "path": e.path,
                    "method": e.method,
                    "operation_id": e.operation_id,
                    "summary": e.summary,
                    "tags": e.tags,
                    "deprecated": e.deprecated,
                }
                for e in spec.endpoints
            ],
            "security_schemes": spec.security_schemes,
        }
        
    except Exception as e:
        logger.error(f"Swagger 解析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/swagger/generate-ir", summary="从 Swagger 生成 API-IR")
async def generate_api_ir_from_swagger(
    swagger_url: str,
    endpoint_path: str,
    method: str = "GET",
):
    """
    从 Swagger 文档生成指定端点的 API-IR
    """
    from app.engines.left_pupil import SwaggerParser
    
    try:
        parser = SwaggerParser()
        spec = await parser.load_from_url(swagger_url)
        
        # 查找端点
        endpoint = None
        for e in spec.endpoints:
            if e.path == endpoint_path and e.method == method.upper():
                endpoint = e
                break
        
        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到端点: {method} {endpoint_path}",
            )
        
        # 生成 API-IR
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
    except Exception as e:
        logger.error(f"生成 API-IR 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
