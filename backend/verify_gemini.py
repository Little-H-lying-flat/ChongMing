import asyncio
import sys
import os

# Ensure backend path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.ai_client import get_ai_manager, Message
from app.core.ai_models import AIModule
from loguru import logger

async def main():
    logger.info("Verifying Gemini Integration...")
    
    manager = get_ai_manager()
    
    # Test message
    messages = [
        Message(role="user", content="Hello, who are you? Please reply with 'I am Gemini'.")
    ]
    
    try:
        response = await manager.invoke(
            module=AIModule.GENERAL_CHAT,
            messages=messages,
            model_override="gemini-3-pro-high"
        )
        
        logger.info(f"Response Received: {response.content}")
        logger.info(f"Model Used: {response.model}")
        
        logger.success("Verification Completed Successfully!")
            
    except Exception as e:
        logger.error(f"Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
