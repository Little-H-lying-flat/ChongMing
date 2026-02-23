import httpx
import asyncio

async def main():
    payload = {
        "project_id": "1",
        "requirement_text": "Verify the health endpoint API returns 200 OK",
        "target_type": "API"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://127.0.0.1:8000/api/v1/design/analyze", json=payload, timeout=60)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")

if __name__ == "__main__":
    asyncio.run(main())
