
import asyncio
import os
import sys

# Add backend to path
sys.path.append("d:/project/ChongMing/backend")

from app.core.ai_client import DashScopeClient, Message
from app.core.ai_models import ModelConfig, ModelProvider, ModelCapability

async def test_reasoning():
    client = DashScopeClient()
    
    # Mock config for qwen3.5-plus
    config = ModelConfig(
        model_id="qwen3.5-plus", 
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.REASONING,
        max_tokens=1024
    )
    
    messages = [Message(role="user", content="9.11 and 9.8, which is bigger?")]
    
    print("--- Testing Non-Stream ---")
    try:
        # Direct call
        response = await client.chat(
            messages=messages, 
            model_config=config,
            extra_body={"enable_thinking": True}
        )
        print(f"Model: {response.model}")
        print(f"Content: {response.content[:50]}...")
        print(f"Reasoning: {response.reasoning_content}")
        
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- Testing Stream (Note: Stream extraction logic not fully implemented in client yet, just checking no crash) ---")
    # Current client doesn't yield reasoning in stream yet, but shouldn't crash
    try:
        async for chunk in client.chat_stream(
            messages=messages,
            model_config=config,
            extra_body={"enable_thinking": True}
        ):
            print(chunk, end="", flush=True)
    except Exception as e:
        print(f"Stream Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_reasoning())
