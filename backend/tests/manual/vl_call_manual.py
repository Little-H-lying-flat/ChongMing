import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.core.config import settings

from app.core.ai_client import init_ai_manager, AIModule
from app.core.ai_config_provider import DefaultAIConfigProvider

async def test_vision():
    provider = DefaultAIConfigProvider()
    ai_manager = init_ai_manager(provider)
    
    # Use Visual UI draft model for vision tests
    print("Sending vision request to Visual UI draft model...")
    res = await ai_manager.invoke_vision(
        module=AIModule.AGENT_NEURAL_UI_EXPERT,
        prompt="Describe this image: https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
        image_url="https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
    )
    print(f"Response: {res.content}")

if __name__ == "__main__":
    asyncio.run(test_vision())
