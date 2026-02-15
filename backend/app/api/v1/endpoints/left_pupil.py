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


router = APIRouter(tags=["Flow 4: Left Pupil (API Automation)"])


# ═══════════════════════════════════════════════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════════════════════════════════════════════

class RequestSpecModel(BaseModel):
    """请求规格"""
    method: str = Field("GET", description="HTTP 方法", example="GET")
    url: str = Field(..., description="请求 URL (支持 ${var} 变量)", example="https://api.example.com/users/${user_id}")
    headers: Dict[str, str] = Field(default_factory=dict, description="请求头", example={"Authorization": "Bearer ${token}"})
    body: Optional[Dict[str, Any]] = Field(None, description="请求体 (JSON)", example={"name": "test_user"})
    query_params: Dict[str, str] = Field(default_factory=dict, description="查询参数", example={"page": "1"})
    timeout_ms: int = Field(30000, description="超时时间(毫秒)", example=5000)


class AssertionModel(BaseModel):
    """断言配置"""
    status_code: Optional[int] = Field(None, description="期望状态码", example=200)
    json_assertions: Dict[str, Any] = Field(default_factory=dict, description="JsonPath 断言 (路径 -> 期望值)", example={"$.code": 0})
    contains: Optional[str] = Field(None, description="响应体包含文本", example="Success")
    not_contains: Optional[str] = Field(None, description="响应体不包含文本", example="Error")
    expression: Optional[str] = Field(None, description="自定义 Python 表达式 (response.json()['id'] > 0)", example="len(response.json()['items']) > 0")


class ApiIRStepModel(BaseModel):
    """API-IR 步骤"""
    id: str = Field(..., description="步骤 ID (唯一)", example="STEP_001")
    name: str = Field("", description="步骤名称", example="获取用户信息")
    request: RequestSpecModel = Field(..., description="请求详情")
    extraction: Dict[str, str] = Field(default_factory=dict, description="变量提取规则 (变量名 -> JsonPath)", example={"user_token": "$.data.token"})
    assertion: Optional[AssertionModel] = Field(None, description="断言配置")
    
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
    base_url: str = Field(..., description="API 基础 URL", example="https://api.example.com")
    step: ApiIRStepModel = Field(..., description="API-IR 步骤定义")
    context: Dict[str, Any] = Field(default_factory=dict, description="初始上下文变量", example={"env": "dev"})
    default_headers: Dict[str, str] = Field(default_factory=dict, description="默认请求头 (如 Auth Token)", example={"X-Request-ID": "123"})


class ExecuteChainRequest(BaseModel):
    """执行链式请求"""
    base_url: str = Field(..., description="API 基础 URL")
    steps: List[ApiIRStepModel] = Field(..., description="步骤列表")
    context: Dict[str, Any] = Field(default_factory=dict, description="初始上下文变量")
    default_headers: Dict[str, str] = Field(default_factory=dict, description="默认请求头")
    stop_on_failure: bool = Field(True, description="遇到失败是否停止")


class StepResultResponse(BaseModel):
    """步骤执行结果"""
    step_id: str = Field(..., description="步骤 ID")
    status: str = Field(..., description="执行状态 (passed/failed/error)")
    status_code: int = Field(0, description="实际 HTTP 状态码")
    duration_ms: float = Field(0.0, description="耗时")
    extracted_values: Dict[str, Any] = Field(default_factory=dict, description="提取的变量值")
    assertion_passed: bool = Field(True, description="断言是否全部通过")
    assertion_details: Optional[Dict] = Field(None, description="断言详情报告")
    error: Optional[str] = Field(None, description="错误信息")


class ChainResultResponse(BaseModel):
    """链式执行结果"""
    success: bool = Field(..., description="总体是否成功")
    total_steps: int = Field(..., description="总步骤数")
    passed_steps: int = Field(..., description="通过步骤数")
    failed_steps: int = Field(..., description="失败步骤数")
    results: List[StepResultResponse] = Field(..., description="详细步骤结果")
    final_context: Dict[str, Any] = Field(..., description="最终上下文状态")


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
    summary="执行单步 (Execute Step)",
    description="""
    **Flow 4 核心接口**: 执行单个 API 测试步骤。
    
    - **功能**:
        1. 变量注入: 将 `${var}` 替换为上下文中的值。
        2. HTTP 请求: 使用 `httpx` 发送请求。
        3. 变量提取: 解析响应并提取新变量。
        4. 断言验证: 验证响应是否符合预期。
    """
)
async def execute_step(request: ExecuteStepRequest):
    """
    执行单个 API 测试步骤
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
    summary="执行链路 (Execute Chain)",
    description="""
    **Flow 4 核心接口**: 按顺序执行一组 API 测试步骤 (链路)。
    
    - **特性**:
        - **上下文共享**: 步骤 1 提取的变量可被步骤 2 使用。
        - **条件停止**: 支持 `stop_on_failure`。
        - **最终状态**: 返回链路执行报告和最终上下文。
    """
)
async def execute_chain(request: ExecuteChainRequest):
    """
    执行链式 API 测试
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
    summary="解析协议 (Parse Swagger)",
    description="""
    **导入工具**: 解析 OpenAPI/Swagger 文档并提取端点信息。
    
    - **支持**: OpenAPI 3.0+, Swagger 2.0。
    - **用途**: 将 swagger.json 转换为内部 API-IR 结构的前置步骤。
    """
)
async def parse_swagger(request: SwaggerParseRequest):
    """
    解析 Swagger/OpenAPI 文档
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
    summary="断言验证 (Run Assertions)",
    description="独立运行断言逻辑，用于调试或验证响应数据。",
)
async def run_assertions(request: AssertRequest):
    """
    执行响应断言
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
    summary="生成 IR 模板 (Generate IR)",
    description="快速生成 API-IR JSON 结构模板。",
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
    summary="健康检查 (Health Check)",
    description="检查引擎依赖组件状态。",
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
