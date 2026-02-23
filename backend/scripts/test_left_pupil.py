import httpx
import asyncio
import json

async def main():
    payload = {
        "base_url": "https://jsonplaceholder.typicode.com",
        "steps": [
            {
                "id": "step_1",
                "name": "Get User",
                "request": {
                    "method": "GET",
                    "url": "/users/1",
                    "headers": {},
                    "query_params": {},
                    "timeout_ms": 5000
                },
                "extraction": {
                    "user_email": "$.email"
                },
                "assertion": {
                    "status_code": 200,
                    "json_assertions": {
                        "$.id": 1
                    }
                }
            },
            {
                "id": "step_2",
                "name": "Verify Extracted Email",
                "request": {
                    "method": "GET",
                    "url": "/posts",
                    "headers": {},
                    "query_params": {
                        "email": "${user_email}"
                    },
                    "timeout_ms": 5000
                },
                "extraction": {},
                "assertion": {
                    "status_code": 200
                }
            }
        ],
        "context": {},
        "default_headers": {},
        "stop_on_failure": True
    }

    async with httpx.AsyncClient() as client:
        try:
            print("Sending request to /api/v1/left-pupil/execute-chain...")
            resp = await client.post("http://localhost:8000/api/v1/left-pupil/execute-chain", json=payload, timeout=20.0)
            print(f"Status Code: {resp.status_code}")
            print(json.dumps(resp.json(), indent=2))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
