import asyncio
import sys
import os

# Ensure backend is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from app.engines.left_pupil.api_executor import APIExecutor
from app.schemas.api_ir import APIIR, ExecutionResult

async def test_real_execution():
    print("🚀 Starting Left Pupil Real Execution Test...")
    
    # 1. Initialize Executor
    executor = APIExecutor(timeout=10.0)
    
    # 2. Define API-IR (Real Request to JSONPlaceholder)
    api_ir = APIIR(
        method="GET",
        url="https://jsonplaceholder.typicode.com/posts/1",
        headers={"User-Agent": "ChongMing-Test-Agent/1.0"},
        assertions=[
            {
                "type": "status_code",
                "expected": 200
            },
            {
                "type": "jsonpath",
                "path": "$.id",
                "expected": 1,
                "operator": "equals"
            },
            {
                "type": "jsonpath",
                "path": "$.title",
                "expected": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
                "operator": "equals" # This title is stable in JSONPlaceholder
            }
        ],
        extract={
            "post_id": "$.id",
            "post_title": "$.title"
        }
    )
    
    # 3. Execute
    async with executor:
        print(f"📡 Sending GET request to {api_ir.url}...")
        result: ExecutionResult = await executor.execute(api_ir)
    
    # 4. Verify Result
    print(f"\n✅ Execution Completed in {result.response.duration_ms:.2f}ms")
    print(f"Status Code: {result.response.status_code}")
    print(f"Success: {result.success}")
    
    if result.success:
        print("✅ All assertions passed!")
    else:
        print("❌ Assertions failed:")
        for fail in result.assertions_failed:
            print(f"  - {fail}")
            
    print("\n📦 Extracted Variables:")
    for key, val in result.extracted_values.items():
        print(f"  {key} = {val}")

    # 5. Test Variable Replacement for POST
    print("\n🚀 Testing POST with Variable Replacement...")
    
    post_ir = APIIR(
        method="POST",
        url="https://jsonplaceholder.typicode.com/posts",
        body={
            "title": "foo",
            "body": "bar",
            "userId": "${post_id}" # Should be replaced by 1
        },
        assertions=[
             {
                "type": "status_code",
                "expected": 201
            }
        ]
    )
    
    # Manually inject context since we are not using Dispatcher which persists context
    executor.set_context("post_id", 1) 
    
    async with executor:
         print(f"📡 Sending POST request to {post_ir.url}...")
         result_post: ExecutionResult = await executor.execute(post_ir)
         
    print(f"✅ POST Success: {result_post.success}")
    print(f"Response Body: {result_post.response.body}")

if __name__ == "__main__":
    asyncio.run(test_real_execution())
