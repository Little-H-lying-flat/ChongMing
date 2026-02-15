
import asyncio
import logging
import uuid
import sys
import os
import json

# Adjust path
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from app.services.left_pupil.knowledge_ingestor import KnowledgeIngestor
from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest
from app.engines.right_pupil import RightPupilEngine
from app.core.config import settings

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DemoFlow")

async def run_demo():
    project_id = f"demo_proj_{uuid.uuid4().hex[:6]}"
    logger.info(f"🚀 Starting Full Flow Demo [Project: {project_id}]")
    
    # 1. Ingest Requirement (Knowledge)
    logger.info("📚 Step 1: Ingesting Requirement Document...")
    ingestor = KnowledgeIngestor()
    with open("requirements/demo_search.md", "r", encoding="utf-8") as f:
        content = f.read()
    
    ingestor.ingest_text(content, "demo_search.md", project_id)
    logger.info("✅ Requirement Ingested into ChromaDB.")

    # 2. Neural Design (Requirement -> Test Case)
    logger.info("🧠 Step 2: Generating Visual Test Case [Model: qwen3-max]...")
    design_service = DesignService()
    
    req_text = "Verify that a user can search for 'ChongMing AI' on Baidu."
    
    # Analyze
    scenarios = await design_service.analyze_requirement(DesignRequest(
        project_id=project_id,
        requirement_text=req_text
    ))
    
    if not scenarios:
        logger.error("❌ No scenarios generated!")
        return

    selected_scenario = scenarios[0]
    logger.info(f"📋 Generated Scenario: {selected_scenario.get('name')}")
    
    # Generate Steps
    test_case = await design_service.generate_test_case(selected_scenario, project_id)
    logger.info(f"✅ Test Case Created: {test_case.name}")
    
    # Fix UP the URL for the demo if LLM guessed wrong or generic
    # The LLM usually outputs generalized steps. For this demo, we ensure it points to a real URL.
    # We will inspect the steps.
    logger.info("Steps generated:")
    for step in test_case.steps:
        logger.info(f" - {step.name} (URL: {step.request.url})")
        # Force Baidu URL for safety in this demo script if missing
        if "baidu" not in str(step.request.url):
             step.request.url = "https://www.baidu.com"
    
    # 3. Right Pupil Execution (Visual-First)
    logger.info("👁️ Step 3: Executing with Right Pupil [Visual-First]...")
    logger.info(f"   - Planner: {settings.MODEL_RIGHT_PUPIL_PLANNER}")
    logger.info(f"   - Vision: {settings.MODEL_RIGHT_PUPIL_VL}")
    engine = RightPupilEngine(omni_url="http://localhost:8003")
    try:
        # Start Session
        await engine.start_session(headless=False)
        
        for i, step in enumerate(test_case.steps):
            logger.info(f"▶️ Executing Step {i+1}: {step.name}")
            
            # 1. Navigate if URL is present (usually first step)
            if step.request.url and i == 0:
                logger.info(f"   Navigating to {step.request.url}")
                await engine.page.goto(step.request.url)
            
            # 2. Sensing (Visual-First)
            logger.info("   👀 Sensing...")
            await engine.waiter.wait_until_stable()
            screenshot_bytes = await engine.page.screenshot(type="png")
            import base64
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            
            elements = await engine.omni_client.parse_screenshot(screenshot_base64)
            loop = asyncio.get_running_loop()
            annotated_base64, id_map = await loop.run_in_executor(
                None, engine.som_renderer.draw_som, screenshot_base64, elements
            )
            
            # 3. Planning (Instruction -> Action with ID)
            logger.info("   🧠 Planning...")
            som_text_lines = [f"ID {k}: {v.get('label')} {v.get('content', '')}" for k, v in id_map.items()]
            som_text = "\n".join(som_text_lines)
            
            action = await engine.planner.plan_next_step(
                task=step.name, # "Click search box"
                screenshot_base64=annotated_base64,
                som_text=som_text,
                history=[] # Stateless for single step, or accumulate if needed
            )
            
            if not action:
                logger.error("   ❌ Planner failed to generate action.")
                break
                
            logger.info(f"   🎯 Action: {action.action_type} on {action.target.value}")

            # 4. Execution
            success = await engine.runner.execute(action, id_map)
            
            if not success:
               logger.error("   ❌ Execution Failed.")
               break
            
            logger.info("   ✅ Step Completed.")

        logger.info("🎉 Full Flow Demonstration Completed Successfully!")
        await engine.stop_session()
        
    except Exception as e:
        logger.error(f"❌ Execution Failed: {e}", exc_info=True)
        if 'engine' in locals():
            await engine.stop_session()

if __name__ == "__main__":
    asyncio.run(run_demo())
