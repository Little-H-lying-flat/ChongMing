import asyncio
from app.engines.left_pupil.api_executor import APIExecutor
from app.schemas.api_ir import APIIR

async def test_assertion_defense():
    print("Testing Assertion Defense Mechanism...")
    
    # 1. Create APIIR with NO assertions, targeting a 404 endpoint
    # This simulates LLM forgetting to add assertions
    api_ir = APIIR(
        method="GET",
        url="https://jsonplaceholder.typicode.com/invalid-path-404",
        assertions=[] 
    )
    
    executor = APIExecutor()
    async with executor:
        result = await executor.execute(api_ir)
        
    print(f"URL: {result.response.request_url}")
    print(f"Status Code: {result.response.status_code}")
    print(f"Success: {result.success}")
    print(f"Assertions Failed: {result.assertions_failed}")
    
    # Verification
    if not result.success and "状态码: 期望 [200, " in str(result.assertions_failed):
        print("\n✅ PASS: Defense mechanism correctly caught the 404 error!")
    else:
        print("\n❌ FAIL: Defense mechanism failed. The step should have failed.")

if __name__ == "__main__":
    asyncio.run(test_assertion_defense())
