# scripts/stress_test_ui.py
import asyncio
import httpx
import time
import sys

BASE_URL = "http://localhost:8000/api/v1"
CONCURRENT_REQUESTS = 5

async def trigger_task(client, i):
    payload = {
        "prompt": f"Stress Test Task {i}: Open Google",
        "url": "https://www.google.com"
    }
    print(f"[INFO] Task {i} starting...")
    start = time.time()
    try:
        # Use Async Endpoint
        resp = await client.post(f"{BASE_URL}/executions/ui/run/async", json=payload)
        
        if resp.status_code != 202:
            print(f"[FAIL] Task {i} submission failed: {resp.status_code} - {resp.text}")
            return False
            
        task_id = resp.json()["task_id"]
        # print(f"[INFO] Task {i} submitted. ID: {task_id}")
        
        # Poll for completion
        while True:
            # Check Timeout (60s)
            if time.time() - start > 60:
                print(f"[FAIL] Task {i} timed out polling.")
                return False
                
            status_resp = await client.get(f"{BASE_URL}/tasks/{task_id}/status")
            if status_resp.status_code != 200:
                print(f"[WARN] Task {i} status check failed: {status_resp.status_code}")
                await asyncio.sleep(1)
                continue
                
            state = status_resp.json()["state"]
            
            if state == "SUCCESS":
                duration = time.time() - start
                print(f"[PASS] Task {i} finished in {duration:.2f}s")
                return True
            elif state in ["FAILURE", "REVOKED"]:
                print(f"[FAIL] Task {i} failed in Celery: {state}")
                return False
            
            # Still Pending/Started
            await asyncio.sleep(2)

    except Exception as e:
        print(f"[FAIL] Task {i} error: {e}")
        return False

async def main():
    print(f"[INFO] Starting Stress Test with {CONCURRENT_REQUESTS} concurrent requests...")
    
    async with httpx.AsyncClient() as client:
        # Health Check
        try:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code != 200:
                print("[FAIL] Backend not reachable. Is it running?")
                return
        except Exception:
             print("[FAIL] Backend connection failed.")
             return

        # Launch tasks
        tasks = [trigger_task(client, i) for i in range(CONCURRENT_REQUESTS)]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r)
        print(f"\n[SUMMARY] Success: {success_count}/{CONCURRENT_REQUESTS}")
        
        if success_count < CONCURRENT_REQUESTS:
            print("[WARN] Some tasks failed. Celery queue might be needed.")
        else:
            print("[PASS] All tasks handled concurrently.")

if __name__ == "__main__":
    asyncio.run(main())
