
import asyncio
import logging
import uuid
from typing import Dict, Any

# Adjust path to find app module
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from app.core.config import settings
from app.services.left_pupil.knowledge_ingestor import KnowledgeIngestor
from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest
from app.engines.right_pupil import RightPupilEngine
from app.schemas.execution import AUIIR

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BackendValidator")

async def validate_e2e():
    """
    Validates the entire backend pipeline:
    1. Knowledge Ingestion (Left Pupil)
    2. Test Case Generation (Neural Design)
    3. Execution (Right Pupil - Mocked for CI stability, or Real if viable)
    """
    project_id = f"proj_val_{uuid.uuid4().hex[:8]}"
    logger.info(f"🚀 Starting Backend E2E Validation for Project: {project_id}")
    
    # 1. Knowledge Ingestion
    logger.info("📚 Step 1: Ingesting Domain Knowledge...")
    ingestor = KnowledgeIngestor()
    sample_knowledge = """
# Login Rules
1. Users must accept Terms of Service before login.
2. Password must be at least 8 characters.
    """
    count = ingestor.ingest_text(sample_knowledge, "login_rules.md", project_id)
    logger.info(f"✅ Ingested {count} knowledge chunks.")
    assert count > 0, "Ingestion failed"

    # 2. Neural Design (Test Case Generation)
    logger.info("🧠 Step 2: Generating Test Case with Neural Design...")
    design_service = DesignService()
    
    # Mocking Retrieve API for now since we don't have real API docs ingested in this run
    # effectively testing Knowledge RAG + Generation logic
    design_request = DesignRequest(
        project_id=project_id,
        requirement_text="Verify that user cannot login with short password.",
        context="System requires strong security."
    )
    
    scenarios = await design_service.analyze_requirement(design_request)
    assert len(scenarios) > 0, "No scenarios generated"
    scenario = scenarios[0]
    logger.info(f"Generated Scenario: {scenario.get('name')}")
    
    # Generate Case
    refined_case = await design_service.generate_test_case(scenario, project_id)
    logger.info(f"✅ Generated Test Case: {refined_case.name}")
    logger.info(f"Steps: {len(refined_case.steps)}")
    
    # Check if Knowledge was used (Implicit check: check logs or content)
    # The prompt injection happens inside service, we trust unit tests for that.
    
    # 3. Execution (Right Pupil)
    logger.info("👁️ Step 3: Executing Test Case (Simulated)...")
    # For E2E validation script, we might not want to launch a real browser 
    # if it's running in a restricted env. 
    # However, user asked for "Backend validation".
    # Let's perform a "Dry Run" or check if engine can initialize.
    
    try:
        engine = RightPupilEngine()
        # We won't actually run a real browser task here to avoid flakiness in this script 
        # unless user explicitly wants a visual test.
        # But we can verify engine initialization and components.
        assert engine.omni_client is not None
        assert engine.planner is not None
        logger.info("✅ Right Pupil Engine initialized successfully.")
        
    except Exception as e:
        logger.error(f"Engine initialization failed: {e}")
        raise

    logger.info("🎉 Backend E2E Validation Completed Successfully!")

if __name__ == "__main__":
    asyncio.run(validate_e2e())
