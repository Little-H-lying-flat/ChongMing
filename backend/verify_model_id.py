
import os
import asyncio
from openai import AsyncOpenAI

API_KEY = "sk-fecda1b83bfe4208892248adffc7cc38"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

async def test_model(model_name):
    print(f"Testing model: {model_name}...")
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print(f"SUCCESS: {model_name}")
        print(response)
    except Exception as e:
        print(f"FAILED: {model_name}")
        print(f"Error: {e}")

async def main():
    await test_model("qwen-max")
    await test_model("qwen3-max")

if __name__ == "__main__":
    asyncio.run(main())
