# scripts/verify_status_fix.py
import requests
import time
import sys

BASE_URL = "http://localhost:8000/api/v1"

def test_adhoc_status():
    print("[INFO] Testing Ad-hoc Task Status...")
    prompt = "Status Test"
    url = "about:blank"
    
    # 1. Start Async Task
    resp = requests.post(f"{BASE_URL}/executions/ui/run/async", json={"prompt": prompt, "url": url})
    if resp.status_code != 202:
        print(f"[FAIL] Failed to start task: {resp.text}")
        return False
        
    task_id = resp.json()["task_id"]
    print(f"[INFO] Task started: {task_id}")
    
    # 2. Poll Status until Success
    for _ in range(30): # 30 seconds timeout
        status_resp = requests.get(f"{BASE_URL}/executions/{task_id}")
        if status_resp.status_code != 200:
            print(f"[WARN] polling failed: {status_resp.status_code}")
            time.sleep(1)
            continue
            
        data = status_resp.json()
        status = data["status"]
        passed = data["passed"]
        
        print(f"Status: {status}, Passed: {passed}")
        
        if status == "SUCCESS":
            # Verification: passed should be 1 for ad-hoc task
            if passed == 1:
                print("[PASS] Status is SUCCESS and Passed count is 1.")
                return True
            else:
                print(f"[FAIL] Status is SUCCESS but Passed count is {passed} (Expected 1).")
                return False
                
        time.sleep(1)
        
    print("[FAIL] Timeout waiting for task success.")
    return False

if __name__ == "__main__":
    try:
        if test_adhoc_status():
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Script crashed: {e}")
        sys.exit(1)
