import asyncio
import os
import traceback

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.core.config import settings
from app.core.ai_client import init_ai_manager, AIModule
from app.core.ai_config_provider import DefaultAIConfigProvider

async def main():
    provider = DefaultAIConfigProvider()
    ai_manager = init_ai_manager(provider)
    
    print("Testing invoke_vision...")
    try:
        res = await ai_manager.invoke_vision(
            module=AIModule.RIGHT_PUPIL_GROUNDING,
            prompt="Describe this image",
            image_url="https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"
        )
        print("SUCCESS")
    except Exception as e:
        print(f"Exception Type: {type(e)}")
        if hasattr(e, 'response'):
            print(f"Response text: {e.response.text}")
        else:
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
