import httpx
import asyncio
import json

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Create API Test Case
        print("Creating Test Case...")
        tc_payload = {
            "name": "E2E Integration Test Case",
            "description": "Integration from API to Performance",
            "mode": "API",
            "priority": "P1",
            "steps": [
                {
                    "request": {
                        "method": "GET",
                        "url": "https://jsonplaceholder.typicode.com/todos/1"
                    }
                }
            ],
            "tags": ["integration"]
        }
        resp = await client.post("/api/v1/test-cases", json=tc_payload)
        try:
            tc_data = resp.json()
            print("Test Case created:", tc_data)
        except Exception:
            print("Failed to decode JSON. Status:", resp.status_code)
            print("Body:", resp.text)
            return
        
        tc_id = tc_data.get("id")
        
        if not tc_id:
            print("Failed to create TC:", resp.text)
            return

        # 2. Start Turbo Test
        print("Starting Turbo Test...")
        turbo_payload = {
            "test_case_id": tc_id,
            "users": 10,
            "spawn_rate": 2.0,
            "run_time": "10s",
            "mode": "local",
            "worker_count": 1,
            "data_count": 0
        }
        resp = await client.post("/api/v1/turbo/run", json=turbo_payload)
        try:
            turbo_data = resp.json()
            print("Turbo started:", turbo_data)
        except Exception:
            print("Failed to decode Turbo JSON. Status:", resp.status_code)
            print("Body:", resp.text)
            return
        
        test_id = turbo_data.get("test_id")
        
        if not test_id:
             print("Failed to start Turbo:", resp.text)
             return
             
        # Wait a bit pour statistics
        for i in range(5):
             await asyncio.sleep(2)
             resp = await client.get(f"/api/v1/turbo/stats/{test_id}")
             print(f"Turbo Stats ({i}):", resp.json())
        
        # 4. Stop Turbo
        resp = await client.post(f"/api/v1/turbo/stop/{test_id}")
        print("Turbo stopped:", resp.json())

if __name__ == "__main__":
    asyncio.run(main())
