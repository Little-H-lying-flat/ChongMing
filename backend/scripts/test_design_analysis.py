import asyncio
import sys
import os
import logging
from loguru import logger as loguru_logger

# Setup logging
logging.basicConfig(level=logging.INFO)
loguru_logger.add(sys.stderr, level="INFO")

# Fix path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest
from app.core.config import settings
from app.core.ai_client import get_ai_manager

async def main():
    loguru_logger.info(f"🧪 Testing Design Analysis")
    loguru_logger.info(f"Using Model: {settings.MODEL_NEURAL_SCENARIO}")
    loguru_logger.info(f"Gemini Key Present: {bool(settings.GEMINI_API_KEY)}")
    loguru_logger.info(f"Qwen Key Present: {bool(settings.QWEN_API_KEY)}")
    
    # Check if AI Manager can initialize clients
    manager = get_ai_manager()
    loguru_logger.info("AI Manager Initialized")
    
    service = DesignService()
    loguru_logger.info("DesignService Initialized")
    
    req = DesignRequest(
        project_id="test_repro_500",
        requirement_text="Design a login page with username, password, and remember me checkbox.",
        target_type="UI"
    )
    
    try:
        loguru_logger.info("Calling analyze_requirement...")
        scenarios = await service.analyze_requirement(req)
        loguru_logger.success(f"✅ Success! Generated {len(scenarios)} scenarios.")
        # print(scenarios)
    except Exception as e:
        loguru_logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
