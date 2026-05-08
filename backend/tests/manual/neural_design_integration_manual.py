import asyncio
import httpx
import json

base_url = "http://localhost:8000/api/v1/design"

async def test_upload(filename):
    print(f"--- Uploading {filename} ---")
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        with open(filename, "rb") as f:
            files = {"file": (filename, f, "application/octet-stream")}
            response = await client.post(f"{base_url}/upload", files=files)
            print("Status:", response.status_code)
            if response.status_code != 200:
                print("Error Body:", response.text)
                return None, None
            data = response.json()
            # print(json.dumps(data, ensure_ascii=False, indent=2))
            return data["extracted_text"], data["file_type"]

async def test_analyze(extracted_text, target_type):
    print(f"--- Analyzing ({target_type}) ---")
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        payload = {
            "project_id": "test_project",
            "requirement_text": extracted_text,
            "target_type": target_type,
            "context": "This is a local integration test."
        }
        response = await client.post(f"{base_url}/analyze", json=payload)
        print("Status:", response.status_code)
        
        if response.status_code != 200:
            print(response.text)
            return
            
        data = response.json()
        print(f"Generated {len(data)} scenarios!")
        print(json.dumps(data, ensure_ascii=False, indent=2))

async def main():
    # Test MD PRD 
    print("Testing Markdown PRD:")
    text_md, _ = await test_upload("tests/mock_prd.md")
    await test_analyze(text_md, "MIXED")
    
    # Test Swagger JSON
    print("\nTesting Swagger JSON:")
    text_json, _ = await test_upload("tests/mock_swagger.json")
    await test_analyze(text_json, "API")

if __name__ == "__main__":
    asyncio.run(main())
