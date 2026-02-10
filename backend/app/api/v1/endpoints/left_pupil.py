"""
左瞳引擎 API 端点

提供 API 测试执行、Swagger 解析、向量检索等功能
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field
from loguru import logger

from app.services.left_pupil.context_memory import ContextMemory
from app.services.left_pupil.swagger_parser import SwaggerParser
from app.services.left_pupil.asserter import Asserter, create_rules_from_dict
from app.services.left_pupil.api_runner import ApiRunner, ApiIRStep, RequestSpec
from app.models.api_ir import ApiIR, ApiIRChain, create_api_ir


router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════════════════════════════════════════════

class RequestSpecModel(BaseModel):
    """请求规格"""
    method: str = Field(default="GET", description="HTTP 方法")
    url: str = Field(..., description="请求 URL (支持 ${var} 变量)")
    headers: Dict[str, str] = Field(default_factory=dict, description="请求头")
    body: Optional[Dict[str, Any]] = Field(default=None, description="请求体")
    query_params: Dict[str, str] = Field(default_factory=dict, description="查询参数")
    timeout_ms: int = Field(default=30000, description="超时时间(毫秒)")


class AssertionModel(BaseModel):
    """断言配置"""
    status_code: Optional[int] = Field(default=None, description="期望状态码")
    json_assertions: Dict[str, Any] = Field(default_factory=dict, description="JsonPath 断言")
    contains: Optional[str] = Field(default=None, description="包含文本")
    not_contains: Optional[str] = Field(default=None, description="不包含文本")
    expression: Optional[str] = Field(default=None, description="自定义表达式")


class ApiIRStepModel(BaseModel):
    """API-IR 步骤"""
    id: str = Field(..., description="步骤 ID")
    name: str = Field(default="", description="步骤名称")
    request: RequestSpecModel
    extraction: Dict[str, str] = Field(default_factory=dict, description="变量提取规则")
    assertion: Optional[AssertionModel] = Field(default=None, description="断言配置")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "STEP_01",
                "name": "获取用户列表",
                "request": {
                    "method": "GET",
                    "url": "/users",
                },
                "extraction": {"first_user_id": "$.0.id"},
                "assertion": {"status_code": 200},
            }
        }


class ExecuteStepRequest(BaseModel):
    """执行单步请求"""
    base_url: str = Field(..., description="API 基础 URL")
    step: ApiIRStepModel
    context: Dict[str, Any] = Field(default_factory=dict, description="初始上下文变量")
    default_headers: Dict[str, str] = Field(default_factory=dict, description="默认请求头")


class ExecuteChainRequest(BaseModel):
    """执行链式请求"""
    base_url: str = Field(..., description="API 基础 URL")
    steps: List[ApiIRStepModel]
    context: Dict[str, Any] = Field(default_factory=dict, description="初始上下文变量")
    default_headers: Dict[str, str] = Field(default_factory=dict, description="默认请求头")
    stop_on_failure: bool = Field(default=True, description="失败时停止")


class StepResultResponse(BaseModel):
    """步骤执行结果"""
    step_id: str
    status: str  # passed, failed, error
    status_code: int = 0
    duration_ms: float = 0.0
    extracted_values: Dict[str, Any] = Field(default_factory=dict)
    assertion_passed: bool = True
    assertion_details: Optional[Dict] = None
    error: Optional[str] = None


class ChainResultResponse(BaseModel):
    """链式执行结果"""
    success: bool
    total_steps: int
    passed_steps: int
    failed_steps: int
    results: List[StepResultResponse]
    final_context: Dict[str, Any]


class SwaggerParseRequest(BaseModel):
    """Swagger 解析请求"""
    url: Optional[str] = Field(default=None, description="Swagger 文档 URL")
    content: Optional[Dict[str, Any]] = Field(default=None, description="Swagger 文档内容")


class EndpointInfo(BaseModel):
    """端点信息"""
    id: str
    method: str
    path: str
    summary: str = ""
    tags: List[str] = Field(default_factory=list)
    parameters: List[Dict] = Field(default_factory=list)
    has_request_body: bool = False
    requires_auth: bool = False


class SwaggerParseResponse(BaseModel):
    """Swagger 解析响应"""
    success: bool
    title: str = ""
    version: str = ""
    endpoints_count: int = 0
    endpoints: List[EndpointInfo] = Field(default_factory=list)
    error: Optional[str] = None


class AssertRequest(BaseModel):
    """断言请求"""
    response_data: Dict[str, Any] = Field(..., description="响应数据")
    status_code: int = Field(default=200, description="状态码")
    assertions: AssertionModel


class AssertResponse(BaseModel):
    """断言响应"""
    passed: bool
    passed_count: int
    failed_count: int
    details: List[Dict]


# ═══════════════════════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/execute",
    response_model=StepResultResponse,
    summary="执行单个 API 步骤",
    description="执行单个 API-IR 步骤，支持变量注入和提取",
)
async def execute_step(request: ExecuteStepRequest):
    """
    执行单个 API 测试步骤
    
    - 支持变量模板注入 (${var})
    - 支持 JsonPath 变量提取
    - 支持多种断言类型
    """
    try:
        # 初始化
        memory = ContextMemory()
        memory.from_dict(request.context)
        
        runner = ApiRunner(
            base_url=request.base_url,
            memory=memory,
            default_headers=request.default_headers,
        )
        
        # 构建步骤
        step = ApiIRStep(
            id=request.step.id,
            name=request.step.name,
            request=RequestSpec(
                method=request.step.request.method,
                url=request.step.request.url,
                headers=request.step.request.headers,
                body=request.step.request.body,
                query_params=request.step.request.query_params,
                timeout_ms=request.step.request.timeout_ms,
            ),
            extraction=request.step.extraction,
            assertion=request.step.assertion.model_dump(exclude_none=True) if request.step.assertion else {},
        )
        
        # 执行
        result = await runner.execute(step)
        await runner.close()
        
        return StepResultResponse(
            step_id=result.step_id,
            status=result.status,
            status_code=result.status_code,
            duration_ms=result.duration_ms,
            extracted_values=result.extracted_values,
            assertion_passed=result.assertion_report.passed if result.assertion_report else True,
            assertion_details=result.assertion_report.to_dict() if result.assertion_report else None,
            error=result.error,
        )
        
    except Exception as e:
        logger.exception("执行 API 步骤失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行失败: {str(e)}",
        )


@router.post(
    "/execute-chain",
    response_model=ChainResultResponse,
    summary="执行链式 API 步骤",
    description="按顺序执行多个 API-IR 步骤，支持变量传递",
)
async def execute_chain(request: ExecuteChainRequest):
    """
    执行链式 API 测试
    
    - 步骤按顺序执行
    - 变量自动在步骤间传递
    - 可配置失败时停止
    """
    try:
        memory = ContextMemory()
        memory.from_dict(request.context)
        
        runner = ApiRunner(
            base_url=request.base_url,
            memory=memory,
            default_headers=request.default_headers,
        )
        
        results = []
        passed_count = 0
        failed_count = 0
        
        for step_model in request.steps:
            step = ApiIRStep(
                id=step_model.id,
                name=step_model.name,
                request=RequestSpec(
                    method=step_model.request.method,
                    url=step_model.request.url,
                    headers=step_model.request.headers,
                    body=step_model.request.body,
                    query_params=step_model.request.query_params,
                    timeout_ms=step_model.request.timeout_ms,
                ),
                extraction=step_model.extraction,
                assertion=step_model.assertion.model_dump(exclude_none=True) if step_model.assertion else {},
            )
            
            result = await runner.execute(step)
            
            step_result = StepResultResponse(
                step_id=result.step_id,
                status=result.status,
                status_code=result.status_code,
                duration_ms=result.duration_ms,
                extracted_values=result.extracted_values,
                assertion_passed=result.assertion_report.passed if result.assertion_report else True,
                assertion_details=result.assertion_report.to_dict() if result.assertion_report else None,
                error=result.error,
            )
            results.append(step_result)
            
            if result.status == "passed":
                passed_count += 1
            else:
                failed_count += 1
                if request.stop_on_failure:
                    break
        
        await runner.close()
        
        return ChainResultResponse(
            success=failed_count == 0,
            total_steps=len(request.steps),
            passed_steps=passed_count,
            failed_steps=failed_count,
            results=results,
            final_context=memory.to_dict(),
        )
        
    except Exception as e:
        logger.exception("执行链式 API 失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行失败: {str(e)}",
        )


@router.post(
    "/parse-swagger",
    response_model=SwaggerParseResponse,
    summary="解析 Swagger 文档",
    description="解析 OpenAPI 3.0/Swagger 2.0 文档",
)
async def parse_swagger(request: SwaggerParseRequest):
    """
    解析 Swagger/OpenAPI 文档
    
    - 支持 URL 和内容两种方式
    - 支持 OpenAPI 3.0/3.1 和 Swagger 2.0
    """
    try:
        parser = SwaggerParser()
        
        if request.url:
            import asyncio
            endpoints = await asyncio.to_thread(parser.parse_url, request.url)
        elif request.content:
            endpoints = parser.parse(request.content)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="必须提供 url 或 content",
            )
        
        info = parser.get_info()
        
        endpoint_infos = []
        for ep in endpoints:
            endpoint_infos.append(EndpointInfo(
                id=ep.id,
                method=ep.method,
                path=ep.path,
                summary=ep.summary or "",
                tags=ep.tags,
                parameters=[{
                    "name": p.name,
                    "location": p.location,
                    "required": p.required,
                    "type": p.schema_type,
                } for p in ep.parameters],
                has_request_body=ep.request_body is not None,
                requires_auth=len(ep.security) > 0,
            ))
        
        return SwaggerParseResponse(
            success=True,
            title=info.get("title", ""),
            version=info.get("version", ""),
            endpoints_count=len(endpoints),
            endpoints=endpoint_infos,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("解析 Swagger 失败")
        return SwaggerParseResponse(
            success=False,
            error=str(e),
        )


@router.post(
    "/assert",
    response_model=AssertResponse,
    summary="执行断言验证",
    description="对响应数据执行断言验证",
)
async def run_assertions(request: AssertRequest):
    """
    执行响应断言
    
    - 支持状态码、JsonPath、包含、正则、表达式等断言
    """
    try:
        asserter = Asserter()
        
        # 构建断言配置
        assertion_config = {}
        if request.assertions.status_code:
            assertion_config["status_code"] = request.assertions.status_code
        if request.assertions.json_assertions:
            assertion_config["json_assertions"] = request.assertions.json_assertions
        if request.assertions.contains:
            assertion_config["contains"] = request.assertions.contains
        if request.assertions.not_contains:
            assertion_config["not_contains"] = request.assertions.not_contains
        if request.assertions.expression:
            assertion_config["expression"] = request.assertions.expression
        
        rules = create_rules_from_dict(assertion_config)
        report = asserter.assert_all(
            request.response_data,
            rules,
            status_code=request.status_code,
        )
        
        return AssertResponse(
            passed=report.passed,
            passed_count=report.passed_count,
            failed_count=report.failed_count,
            details=[r.to_dict() for r in report.results],
        )
        
    except Exception as e:
        logger.exception("断言执行失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"断言失败: {str(e)}",
        )


@router.post(
    "/generate-ir",
    summary="生成 API-IR",
    description="根据参数生成 API-IR 配置",
)
async def generate_ir(
    method: str = "GET",
    url: str = "/",
    name: str = "",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    extraction: Optional[Dict[str, str]] = None,
    expected_status: int = 200,
):
    """
    生成 API-IR 配置
    
    用于快速创建测试步骤配置
    """
    api_ir = create_api_ir(
        method=method,
        url=url,
        name=name,
        headers=headers or {},
        body=body,
        extraction=extraction or {},
        assertion={"status_code": expected_status},
    )
    
    return api_ir.to_dict()


@router.get(
    "/health",
    summary="健康检查",
    description="检查左瞳引擎服务状态",
)
async def health_check():
    """左瞳引擎健康检查"""
    return {
        "status": "healthy",
        "service": "left-pupil-engine",
        "components": {
            "context_memory": "ready",
            "swagger_parser": "ready",
            "api_runner": "ready",
            "asserter": "ready",
        },
    }
