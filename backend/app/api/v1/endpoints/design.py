"""
Neural Design Layer Endpoints

Exposes Neural Design Service capabilities via REST API.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest, RefinedTestCase
from app.core.ai_client import get_ai_manager
from app.services.left_pupil.rag_retriever import RagRetriever
from app.core.logging import logger
import traceback

router = APIRouter(tags=["Flow 1: Neural Design (需求解析)"])

# Dependency Injection
def get_design_service() -> DesignService:
    """Get DesignService instance"""
    # In a real app, we might want to cache this or use a proper DI container
    # Since DesignService holds references to stateless/singleton clients, instantiation is cheap
    return DesignService(ai_manager=get_ai_manager(), retriever=RagRetriever())

@router.post(
    "/analyze", 
    response_model=List[Dict[str, Any]],
    summary="需求分析 (Analyze PRD)",
    description="""
    **Flow 1 核心接口**: 接收自然语言需求或 PRD 文档，使用 Agent 进行语义分析。
    
    - **输入**: 项目 ID、需求文本、上下文。
    - **处理**: 
        1. 检索 RAG 知识库中的类似用例。
        2. 调用大模型 (Planning Agent) 拆解需求。
        3. 生成结构化的测试场景列表。
    - **输出**: 测试场景列表 (Scenarios)。
    """
)
async def analyze_prd(
    request: DesignRequest,
    service: DesignService = Depends(get_design_service)
):
    try:
        import asyncio
        from app.core.config import settings
        logger.info(f"Design Analysis Request [START]: Project={request.project_id}, Type={request.target_type}, Model={settings.MODEL_NEURAL_SCENARIO}")
        
        logger.info("准备调用大模型 API (via Service)...")
        # Enforce 120s timeout to allow for long generation times (and retries)
        scenarios = await asyncio.wait_for(service.analyze_requirement(request), timeout=120.0)
        
        logger.info(f"Design Analysis Request [SUCCESS]: Generated {len(scenarios)} scenarios.")
        return scenarios
        
    except asyncio.CancelledError:
        logger.warning("客户端已主动断开连接 (CancelledError)！LLM 调用可能仍在后台运行或已卡死。")
        print("CRITICAL WARNING: Request Cancelled by Client (Disconnected)")
        raise
        
    except asyncio.TimeoutError:
        error_detail = "Design Analysis Timed Out (120s limit reached)"
        logger.error(error_detail)
        print(f"CRITICAL ERROR: {error_detail}")
        return JSONResponse(
            status_code=504,
            content={"detail": error_detail, "type": "TimeoutError"}
        )

    except Exception as e:
        import traceback
        error_detail = f"Requirement analysis failed: {str(e)}"
        logger.error(f"Design Analysis Failed: {e}")
        logger.error(traceback.format_exc())
        
        # Force print to stdout for debugging
        print(f"CRITICAL ERROR: {error_detail}")
        print(traceback.format_exc())
        
        return JSONResponse(
            status_code=500,
            content={"detail": error_detail, "type": type(e).__name__}
        )

@router.post(
    "/generate", 
    response_model=RefinedTestCase,
    summary="生成测试用例 (Generate Test Case)",
    description="""
    **Flow 1 核心接口**: 根据测试场景生成详细的自动化测试用例。
    
    - **输入**: 场景定义 (Scenario Object)、项目 ID。
    - **处理**: 
        1. 调用 Neuro-Symbolic Agent 细化步骤。
        2. 补全 API 调用细节 (URL, Method, Headers)。
        3. 生成智能断言规则。
    - **输出**: 标准化的测试用例 (RefinedTestCase / API-IR)。
    """
)
async def generate_test_case_endpoint(
    scenario: Dict[str, Any] = Body(..., description="Scenario definition object"),
    project_id: str = Body(..., description="Project ID context"),
    service: DesignService = Depends(get_design_service)
):
    try:
        # Note: generate_test_case expects 'scenario' dict and 'project_id' str
        # We assume the body receives a JSON object that maps to scenario, plus project_id query or body?
        # The user input spec said: Input: Scenario (JSON Dict). 
        # But service needs project_id for RAG.
        # I'll modify the input to expect a wrapper or just use Body parameters.
        # Here I allow scenario as body, and project_id as query or body.
        # To make it clean, let's accept a wrapper model or just dict.
        # Using Body(...) for scenario dict is fine.
        
        test_case = await service.generate_test_case(scenario, project_id)
        return test_case
    except ValueError as e:
        # Validation or parsing error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test case generation failed: {str(e)}")
