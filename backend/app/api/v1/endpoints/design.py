"""
Neural Design Layer Endpoints

Exposes Neural Design Service capabilities via REST API.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest, RefinedTestCase
from app.core.ai_client import get_ai_manager
from app.services.left_pupil.rag_retriever import RagRetriever

router = APIRouter()

# Dependency Injection
def get_design_service() -> DesignService:
    """Get DesignService instance"""
    # In a real app, we might want to cache this or use a proper DI container
    # Since DesignService holds references to stateless/singleton clients, instantiation is cheap
    return DesignService(ai_manager=get_ai_manager(), retriever=RagRetriever())

@router.post("/analyze", response_model=List[Dict[str, Any]])
async def analyze_prd(
    request: DesignRequest,
    service: DesignService = Depends(get_design_service)
):
    """
    Analyze Requirement / PRD
    
    Extracts test scenarios from natural language requirements.
    """
    try:
        scenarios = await service.analyze_requirement(request)
        return scenarios
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Requirement analysis failed: {str(e)}")

@router.post("/generate", response_model=RefinedTestCase)
async def generate_test_case_endpoint(
    scenario: Dict[str, Any] = Body(..., description="Scenario definition object"),
    project_id: str = Body(..., description="Project ID context"),
    service: DesignService = Depends(get_design_service)
):
    """
    Generate Test Case (refined)
    
    Generates a structured API-IR test case from a scenario description.
    """
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
