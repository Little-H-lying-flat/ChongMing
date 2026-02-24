import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def run_flow_2():
    print("=== Starting E2E Flow 2 Verification Script via HTTP ===")
    
    # 1. AI Healing (Smart Ops)
    print("\n--- Step 1: Smart Ops AI Healing ---")
    mock_error = "TimeoutError: Locator '#submit-btn' is not visible after 3000ms"
    mock_context = "{'action': 'click', 'target': '#submit-btn', 'page_url': 'https://example.com/login'}"
    
    print(f"Injecting Error: {mock_error}")
    res1 = requests.post(f"{BASE_URL}/smart-ops/analyze-defect", json={
        "error_msg": mock_error,
        "context": mock_context
    })
    
    if res1.status_code != 200:
        print(f"Failed! {res1.status_code} {res1.text}")
        return
        
    analysis = res1.json()
    print("AI Root Cause Analysis Result:")
    print(json.dumps(analysis, ensure_ascii=False, indent=2))
    
    # 2. Phoenix Nirvana (Compile Trace)
    print("\n--- Step 2: Phoenix Nirvana Trace Compilation ---")
    
    # Simulating the trace JSON structure that Phoenix expects
    mock_trace_data = {
        "source_tc_id": "test_login_flow",
        "source_tc_name": "User Login Flow Trace",
        "trace_events": [
            {"action": "goto", "url": "https://example.com/login"},
            {"action": "fill", "target": "#username", "value": "testuser"},
            {"action": "fill", "target": "#password", "value": "testpass"},
            {"action": "click", "target": "#submit-btn"},
            {"action": "verify", "target": ".welcome-msg", "expected": "Welcome"}
        ],
        "error_context": str(analysis)
    }
    
    print("Sending to Phoenix Service to compile script...")
    res2 = requests.post(f"{BASE_URL}/phoenix/compile", json=mock_trace_data)
    
    if res2.status_code != 200:
        print(f"Failed to compile! {res2.status_code} {res2.text}")
        return
        
    compiled_result = res2.json()
    print("Compilation Success!")
    print(f"Script ID: {compiled_result.get('id')}")
    print(f"Script Content Snippet: {compiled_result.get('code', '')[:200]}...")
    
    print("=== E2E Flow 2 Verification Complete ===")

if __name__ == "__main__":
    run_flow_2()
