import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import asyncio
import time
import logging
from app.engines.right_pupil import RightPupilEngine
from app.core.config import settings

# Override settings or ensure keys are available
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("E2ETest")

async def test_e2e_pipeline():
    total_start_time = time.time()
    
    logger.info("=== Starting Right Pupil 3.0 E2E Test ===")
    
    engine = RightPupilEngine()
    await engine.start_session(headless=True) # use headless=True to avoid popping up window if testing in background
    
    try:
        task_prompt = "在搜索框中输入 Playwright 然后提交搜索"
        url = "https://www.baidu.com"
        
        logger.info(f"Task: {task_prompt}")
        logger.info(f"URL: {url}")
        
        # 1. Provide an initial navigation kickstart
        logger.info("Navigate to target page...")
        nav_start = time.time()
        await engine.page.goto(url, wait_until="domcontentloaded")
        logger.info(f"Navigation completed in {time.time() - nav_start:.2f}s")
        
        # 2. Execute Step
        logger.info("Running Execute Step...")
        step_start = time.time()
        result = await engine.execute_step(task_prompt, url=url)
        step_end = time.time()
        
        print("\n==============================================")
        print("                E2E TEST REPORT                 ")
        print("==============================================")
        print(f"Success:            {result.get('success')}")
        print(f"Action Taken:       {result.get('action_taken')}")
        print(f"Target Description: {result.get('target_description')}")
        print(f"Error Message:      {result.get('error')}")
        
        print("\n--- Timing Metrics ---")
        print(f">> Agent Workflow Execution (execute_step): {step_end - step_start:.2f}s")
        print(f">> Total Script Execution Time            : {time.time() - total_start_time:.2f}s")
        
        print("\n--- Agent Task Responsibilities ---")
        print("1. [OmniParser]         (Service): Extracted BBox & OCR from screenshot.")
        print("2. [Hybrid Perception]  (Service): Snipped DOM hints (Tag, aria-labels) via Playwright eval.")
        print("3. [ElementDescriber]   (Agent)  : Translated raw JSON into natural semantic UI descriptions.")
        print("4. [VisualExpert]       (Agent)  : Proposed AUI-IR `type` action mapping Intent -> Semantic ID.")
        print("5. [Critic]             (Agent)  : Enforced 'Logical Sanity Check' & output final clean AUI-IR.")
        print("6. [UiRunner / Executor](Service): Applied `mouse.move(0,0)`, `Wait`, and SSIM state diff verify.")
        print("==============================================")
        
    finally:
        await engine.stop_session()

if __name__ == "__main__":
    asyncio.run(test_e2e_pipeline())
