import requests

url = "http://127.0.0.1:8000/api/v1/design/analyze/async"
payload = {
    "project_id": "proj_001",
    "requirement_text": "Need a login page",
    "target_type": "MIXED"
}

try:
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
