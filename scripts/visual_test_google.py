import asyncio
import os
import sys
import logging
import httpx
from typing import List, Dict, Any, Optional

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.engines.right_pupil import RightPupilEngine
from app.core.config import settings
from app.schemas.aui_ir import VisualActionIR, VisualLocator

# Configure Logging
# Configure Logging
import time
log_dir = os.path.join("traces", "logs")
os.makedirs(log_dir, exist_ok=True)
timestamp = int(time.time())
log_file = os.path.join(log_dir, f"visual_test_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger("VisualTest")
logger.info(f"Logging to file: {log_file}")

class MockPlanner:
    """Mock Planner for testing without LLM"""
    def __init__(self):
        self.step = 0

    async def plan_next_step(self, task: str, screenshot: str, som: str, history: List) -> Optional[VisualActionIR]:
        self.step += 1
        logger.info(f"MockPlanner: Planning step {self.step}")
        
        if self.step == 1:
            # Step 1: Type query
            return VisualActionIR(
                action_type="type",
                target=VisualLocator(strategy="dom", value="textarea[name='q']", description="Search Box"),
                params={"text": "OmniParser"},
                expected_visual_change="Text appears in search box"
            )
        elif self.step == 2:
            # Step 2: Click Search (or just type Enter via a hack if needed, but let's try finding the button)
            # Google's search button often has name='btnK'
            # We'll use a DOM selector for reliability in this mock
            return VisualActionIR(
                action_type="click",
                target=VisualLocator(strategy="dom", value="input[name='btnK']", description="Google Search Button"),
                expected_visual_change="Results page loads"
            )
        else:
            return None

async def main():
    logger.info("Starting Visual Test: Google Search for 'OmniParser'")
    
    settings.OMNIPARSER_URL = "http://localhost:8003"
    logger.info("Using OMNIPARSER_URL=http://localhost:8003")
    
    # Initialize Engine with correct URL
    engine = RightPupilEngine(omni_url=settings.OMNIPARSER_URL)
    
    # Inject Mock Planner if no API Key (This block should not run if key is present)
    if not settings.QWEN_API_KEY:
        logger.warning("No QWEN_API_KEY found. Using MockPlanner.")
        engine.planner = MockPlanner()
    else:
        logger.info("QWEN_API_KEY found. Using Real VisualPlanner.")
    
    # Wait for OmniParser to be ready
    logger.info("Waiting for OmniParser to be ready...")
    async with httpx.AsyncClient() as client:
        for i in range(120): # Wait up to 2 minutes
            try:
                # Just check if we can connect
                await client.get(settings.OMNIPARSER_URL, timeout=1.0)
                # If we get here, it might be 404 or 405 but server is up
                logger.info("OmniParser is ready!")
                break
            except Exception:
                if i % 5 == 0:
                    logger.info(f"Waiting for OmniParser... ({i}s)")
                await asyncio.sleep(1)
        else:
             logger.error("OmniParser failed to start in time.")
             # Proceed anyway, maybe it will work or fail with clean error
    
    # Run Task
    url = "https://www.google.com"
    prompt = "Search for 'OmniParser', press Enter, and then find and click the official GitHub repository or project website in the results."
    
    # We need to run the loop manually or use run_task
    # engine.run_task calls planner.plan_next_step
    
    try:
        await engine.run_task(prompt, url)
    except Exception as e:
        logger.error(f"Test Failed: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
