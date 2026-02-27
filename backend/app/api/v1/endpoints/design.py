"""
Neural Design Layer Endpoints

Exposes Neural Design Service capabilities via REST API.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import fitz # PyMuPDF
import json

from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest, RefinedTestCase
from app.core.ai_client import get_ai_manager
from app.services.left_pupil.rag_retriever import RagRetriever
from app.core.logging import logger
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.environment import Environment
import traceback

router = APIRouter(tags=["Flow 1: Neural Design (需求解析)"])

# Dependency Injection
def get_design_service() -> DesignService:
    """Get DesignService instance"""
    # In a real app, we might want to cache this or use a proper DI container
    # Since DesignService holds references to stateless/singleton clients, instantiation is cheap
    return DesignService(ai_manager=get_ai_manager(), retriever=RagRetriever())


@router.post(
    "/upload",
    summary="解析上传文档 (Parse Uploaded Document)",
    description="支持解析 .md, .pdf 和 Swagger .json 文件内容为纯文本提取。"
)
async def upload_document(file: UploadFile = File(...)):
    try:
        content = await file.read()
        filename = file.filename.lower()
        
        extracted_text = ""
        file_type = "unknown"
        
        if filename.endswith(".md") or filename.endswith(".txt"):
            extracted_text = content.decode("utf-8")
            file_type = "markdown"
        elif filename.endswith(".pdf"):
            # Use PyMuPDF to extract text
            doc = fitz.open(stream=content, filetype="pdf")
            for page in doc:
                extracted_text += page.get_text() + "\n"
            doc.close()
            file_type = "pdf"
        elif filename.endswith(".json"):
            # Could be Swagger/OpenAPI or just regular JSON
            json_data = json.loads(content.decode("utf-8"))
            extracted_text = json.dumps(json_data, ensure_ascii=False, indent=2)
            file_type = "json"
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload .md, .pdf, or .json")
            
        return {
            "filename": file.filename,
            "file_type": file_type,
            "extracted_text": extracted_text.strip()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse uploaded file: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"File parsing failed: {str(e)}")


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
    service: DesignService = Depends(get_design_service),
    db: AsyncSession = Depends(get_db)
):
    try:
        import asyncio
        from app.core.config import settings
        
        # Inject default environment Base URL into the context
        env_stmt = select(Environment).where(Environment.is_default == True, Environment.is_active == True)
        env_result = await db.execute(env_stmt)
        default_env = env_result.scalar_one_or_none()
        
        if not default_env:
            # Fallback to the first active environment if no default is marked
            fallback_stmt = select(Environment).where(Environment.is_active == True).limit(1)
            fallback_result = await db.execute(fallback_stmt)
            default_env = fallback_result.scalar_one_or_none()
        
        env_context = ""
        if default_env and getattr(default_env, "base_url", None):
            base_url = default_env.base_url
            if not getattr(request, "target_url", None):
                request.target_url = base_url
            env_context = f"\n\n[系统可选测试环境]\n如果你在需求文档中找不到任何明确的测试目标地址或域名，你可以考虑使用以下备选 Base URL: {base_url}\n(但如果需求文档或 Context INFO 中明确指定了目标网址，请【必须】优先使用文档中提供的网址，忽略此备选地址。)\nAPI 路径拼接原则：你生成的所有 API 请求路径必须是完整的绝对路径，绝不能只输出相对路径（如 /health）。"
        
        request.context = (request.context or "") + env_context
        
        logger.info(f"Design Analysis Request [START]: Project={request.project_id}, Type={request.target_type}, Model={settings.MODEL_NEURAL_SCENARIO}")
        
        logger.info("准备调用大模型 API (via Service)...")
        # Enforce 300s timeout to allow for long generation times (and retries)
        scenarios = await asyncio.wait_for(service.analyze_requirement(request), timeout=300.0)
        
        logger.info(f"Design Analysis Request [SUCCESS]: Generated {len(scenarios)} scenarios.")
        return scenarios
        
    except asyncio.CancelledError:
        logger.warning("客户端已主动断开连接 (CancelledError)！LLM 调用可能仍在后台运行或已卡死。")
        print("CRITICAL WARNING: Request Cancelled by Client (Disconnected)")
        raise
        
    except asyncio.TimeoutError:
        error_detail = "Design Analysis Timed Out (300s limit reached)"
        logger.error(error_detail)
        print(f"CRITICAL ERROR: {error_detail}")
        raise HTTPException(status_code=504, detail=error_detail)

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
