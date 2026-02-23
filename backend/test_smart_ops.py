import httpx
import asyncio

async def test_smart_ops():
    payload = {
        "error_msg": "TimeoutError: element .submit-btn not visible after 30000ms",
        "context": "Executing Step 3: Click Submit Button inside User Registration Flow."
    }
    
    print("Sending Defect Analysis Request to AI...")
    async with httpx.AsyncClient(trust_env=False) as client:
        try:
            resp = await client.post(
                "http://127.0.0.1:8000/api/v1/smart-ops/analyze-defect", 
                json=payload, 
                timeout=120
            )
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.json()}")
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_smart_ops())
