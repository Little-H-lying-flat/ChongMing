import requests
import time
import json
import sys

import sys
import io

# Force UTF-8 for stdout/stderr to avoid UnicodeEncodeError in Windows Console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000/api/v1"

def run_verification():
    print("🚀 Starting Final System Verification (Real-World Test)...")
    
    # 1. Generate Scenario (Neural Design)
    print("\n📝 Step 1: Generating Test Scenario from Requirement...")
    requirement = "Test JSONPlaceholder API: 1. Get Post 1 (GET https://jsonplaceholder.typicode.com/posts/1) - Expect 200. 2. Get Invalid Path (GET https://jsonplaceholder.typicode.com/posts/invalid-id-999) - Expect 404."
    
    try:
        res = requests.post(f"{BASE_URL}/design/analyze", json={
            "project_id": "verify_proj",
            "requirement_text": requirement,
            "target_type": "API"
        }, timeout=60)
        
        if res.status_code != 200:
            print(f"❌ Design Generation Failed: {res.status_code} - {res.text}")
            return
            
        scenarios = res.json()
        if not scenarios:
            print("❌ No scenarios generated!")
            return
            
        scenario = scenarios[0]
        # Map scenario_id to id for TCIR compatibility
        tc_id = scenario.get("scenario_id")
        scenario["id"] = tc_id
        
        print(f"✅ Generated Scenario: {scenario.get('name')} (ID: {tc_id})")
        print("Generated Steps:")
        for step in scenario.get("steps", []):
            print(f"  - {step.get('name')} | Type: {step.get('step_type')} | Assertion: {step.get('assertion')}")
            
    except Exception as e:
        print(f"❌ Exception during generation: {e}")
        return

    # 2. Execute Scenario
    print(f"\n▶️ Step 2: Executing Scenario {tc_id}...")
    try:
        res = requests.post(f"{BASE_URL}/executions", json={
            "tc_ids": [tc_id],
            "mode": "API",
            "parallel": False,
            "dynamic_payload": [scenario]
        })
        
        if res.status_code != 200:
            print(f"❌ Execution Start Failed: {res.status_code} - {res.text}")
            return
            
        execution_data = res.json()
        execution_id = execution_data.get("execution_id")
        print(f"✅ Execution Started: {execution_id}")
        
    except Exception as e:
        print(f"❌ Exception during execution start: {e}")
        return

    # 3. Poll for Completion
    print(f"\n⏳ Step 3: Waiting for Execution {execution_id} to complete...")
    for _ in range(20): # Wait up to 20s
        time.sleep(1)
        res = requests.get(f"{BASE_URL}/executions/{execution_id}")
        status_data = res.json()
        status = status_data.get("status")
        print(f"   Status: {status}")
        if status in ["completed", "failed", "passed", "interrupted"]:
            break
    else:
        print("❌ Timeout waiting for execution.")
        return

    # 4. Inspect Detailed Steps (The Drawer Data)
    print(f"\n🔍 Step 4: Inspecting Execution Details (Drawer Data)...")
    res = requests.get(f"{BASE_URL}/executions/{execution_id}/steps")
    steps_data = res.json()
    
    # We expect 1 TC result, containing multiple step results
    # The API returns Dict[tc_id, List[StepResult]]
    tc_steps = steps_data.get(tc_id, [])
    
    print(f"Found {len(tc_steps)} steps execution results.")
    
    all_passed = True
    for step in tc_steps:
        success = step.get("success")
        details = step.get("details", {})
        status_code = details.get("status_code")
        assertions_failed = details.get("assertions_failed", [])
        
        print(f"  - Step {step.get('step_index')}: Success={success} | Status Code={status_code}")
        if assertions_failed:
            print(f"    ❌ Assertions Failed: {assertions_failed}")
            
        # LOGIC CHECK
        # Step 1 (200) should be Success=True
        # Step 2 (404) should be Success=True IF the prompt correctly set expected=404
        # OR Success=False if the prompt failed (which tests our defense, but strictly speaking we WANT it to pass here because we asked for 404)
        
        # Wait, the user requirement was "Expect 404". So if the prompt works, it sets expected=404, and the engine sees 404, so it matches -> Success=True.
        # This confirms the ENTIRE flow (Prompt -> Schema -> Execution) works.
        
        if not success:
            all_passed = False

    if all_passed:
        print("\n✅ FINAL RESULT: SUCCESS! The system correctly handled both 200 and 404 expectations.")
    else:
        print("\n⚠️ FINAL RESULT: SOME STEPS FAILED. This might be correct if we were testing the defense mechanism, but here we expected success.")

if __name__ == "__main__":
    run_verification()
