import asyncio
import json
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", trust_env=False) as client:
        print("1. Creating Test Environment...")
        env_res = await client.post("/api/v1/environments", json={
            "name": "Injection Test Env",
            "base_url": "https://httpbin.org",
            "description": "Used by integration tests to check injection",
            "variables": {
                "auth_token": {
                    "value": "super_secret_xyz_123",
                    "encrypted": True,
                    "description": "My Token"
                }
            }
        })
        if env_res.status_code == 400 and "已存在" in env_res.text:
            envs_res = await client.get("/api/v1/environments")
            env_id = next(e["id"] for e in envs_res.json() if e["name"] == "Injection Test Env")
            print(f"✅ Reusing existing Environment: {env_id}\n")
        elif env_res.status_code >= 400:
            print(f"Failed to create env: {env_res.status_code} - {env_res.text}")
            return
        else:
            env_data = env_res.json()
            env_id = env_data["id"]
            print(f"✅ Environment created: {env_id}\n")

        # 2. Add some test cases to run
        test_payload = {
            "tc_ids": ["mock-tc"],
            "mode": "API",
            "parallel": False,
            "max_workers": 1,
            "env": env_id,
            "dynamic_payload": [
                {
                    "id": "mock-tc",
                    "name": "Dynamic Env Test",
                    "mode": "API",
                    "steps": [
                        {
                            "step_type": "API",
                            "name": "Test Env Secrets",
                            "method": "GET",
                            "url": "${base_url}/get",
                            "headers": {
                                "Authorization": "Bearer ${auth_token}",
                                "X-Env-Name": "${env_name}"
                            },
                            "assertions": [
                                {
                                    "type": "status_code",
                                    "expected": 200
                                },
                                {
                                    "type": "json_path",
                                    "path": "headers.Authorization",
                                    "operator": "eq",
                                    "expected": "Bearer super_secret_xyz_123"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        print("2. Submitting Execution with Env Tracking...")
        exec_res = await client.post("/api/v1/executions", json=test_payload)
        if exec_res.status_code >= 400:
            print("Failed execution:", exec_res.text)
            return
            
        exec_id = exec_res.json()["execution_id"]
        print(f"✅ Execution started: {exec_id}\n")
        
        # 3. Poll for result
        print("3. Polling Execution Result...")
        for _ in range(20):
            await asyncio.sleep(1)
            res = await client.get(f"/api/v1/executions/{exec_id}/result")
            data = res.json()
            if data["status"] in ["passed", "failed", "completed"]:
                print(f"✅ Execution Finished: {data['status']}")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                break
        else:
            print("❌ Execution Timeout")
        
if __name__ == "__main__":
    asyncio.run(main())
