import asyncio
import os
import traceback
from openai import AsyncOpenAI, BadRequestError

async def test_raw_vision():
    client = AsyncOpenAI(
        api_key=os.getenv("QWEN_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"}
                },
                {"type": "text", "text": "Describe this image"}
            ]
        }
    ]
    
    print("Sending raw ALiyun DashScope request to qwen-vl-max with vision payload...")
    try:
        response = await client.chat.completions.create(
            model="qwen-vl-max",
            messages=messages
        )
        print("Success!")
        print(response.choices[0].message.content)
    except BadRequestError as e:
        print(f"FAILED WITH BadRequestError")
        print(f"Status: {e.status_code}")
        print(f"Body: {e.response.text}")
    except Exception as e:
        print(f"FAILED WITH EXCEPTION: {type(e)}")
        print(str(e))
        traceback.print_exc()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env')))
    asyncio.run(test_raw_vision())
