import httpx
import time
import json
import asyncio

BASE_URL = "http://localhost:8000/api/v1"

async def wait_for_backend():
    print("Waiting for backend to start...")
    async with httpx.AsyncClient() as client:
        for i in range(30):
            try:
                # Try hitting docs or health
                response = await client.get("http://localhost:8000/docs", timeout=2)
                if response.status_code == 200:
                    print("\nBackend is ready!")
                    return True
            except httpx.RequestError:
                pass
            time.sleep(1)
            print(".", end="", flush=True)
    print("\nBackend failed to start in time.")
    return False

async def test_right_pupil():
    print("Testing Right Pupil Engine...")
    url = f"{BASE_URL}/executions/ui/run"
    payload = {
        "prompt": "Go to Google and search for 'OpenAI'",
        "url": "https://www.google.com"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Long timeout for UI task
            response = await client.post(url, json=payload, timeout=60) 
            if response.status_code == 200:
                print("Success!")
                print(json.dumps(response.json(), indent=2))
            else:
                print(f"Failed with status: {response.status_code}")
                try:
                    print(response.text)
                except:
                    pass
        except Exception as e:
            print(f"Error executing request: {e}")

if __name__ == "__main__":
    import asyncio
    if asyncio.run(wait_for_backend()):
        asyncio.run(test_right_pupil())
