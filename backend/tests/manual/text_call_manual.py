import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.core.config import settings
from app.core.ai_client import init_ai_manager, AIModule
from app.core.ai_config_provider import DefaultAIConfigProvider

async def test_text():
    provider = DefaultAIConfigProvider()
    ai_manager = init_ai_manager(provider)
    
    print("Sending text request to qwen3.5-plus (General Chat model)...")
    res = await ai_manager.simple_chat(
        "Who are you?", 
        module=AIModule.GENERAL_CHAT
    )
    print(f"Response: {res}")

if __name__ == "__main__":
    asyncio.run(test_text())
