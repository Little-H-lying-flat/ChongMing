import requests
import json
import sys

def test_api():
    url = "http://localhost:8000/api/v1/design/analyze"
    payload = {
        "project_id": "api_test_verif",
        "requirement_text": "Design a simple login page with username and password inputs.",
        "target_type": "UI"
    }
    try:
        print(f"📡 Sending request to {url}...")
        resp = requests.post(url, json=payload, timeout=60)
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ Success! API is working.")
            data = resp.json()
            print(f"Received {len(data)} scenarios.")
            # print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("❌ Failed!")
            print(f"Response: {resp.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_api()
