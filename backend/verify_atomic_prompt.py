import urllib.request
import json
import sys

# Configuration
API_URL = "http://localhost:8000/api/v1/design/analyze"
PAYLOAD = {
    "project_id": "atomic_verification_v2",
    "type": "UI",
    "requirement_text": """
目标网址: https://www.saucedemo.com/
测试账号: standard_user / secret_sauce
操作: 登录系统。
视觉预期: 成功进入商品页，看到 'Products' 标题。
""",
    "context": "Verification Test"
}

def verify():
    print(f"🚀 Sending request to {API_URL}...")
    
    try:
        req = urllib.request.Request(
            API_URL, 
            data=json.dumps(PAYLOAD).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req) as f:
            response_data = f.read().decode('utf-8')
            data = json.loads(response_data)
        
        print("\n✅ API Response Received:")
        
        # In design.py, analyze_prd returns List[Dict] directly (Scenarios list)
        # OR it returns a Dict with "scenarios".
        # Let's inspect data.
        
        scenarios = []
        if isinstance(data, list):
            scenarios = data
        elif isinstance(data, dict):
            scenarios = data.get("scenarios", [])
            if not scenarios: # Maybe it returned a single scenario?
                # Check known keys
                if "name" in data and "steps" in data:
                    scenarios = [data]

        if not scenarios:
            print("⚠️ No scenarios found!")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return

        for i, scenario in enumerate(scenarios):
            print(f"\n🏷️ Scenario {i+1}: {scenario.get('name')}")
            print(f"📝 Description: {scenario.get('description')}")
            print("Steps:")
            for j, step in enumerate(scenario.get("steps", [])):
                print(f"  [{j+1}] Type: {step.get('step_type')} | Action: {step.get('description', '')}")
                if step.get('step_type') == 'UI':
                    print(f"      -> Action: {step.get('action')}")
                    print(f"      -> Target: {step.get('target')}")
                    print(f"      -> Value: {step.get('value')}")
        
    except Exception as e:
        print(f"\n❌ Request Failed: {e}")
        # Check if 422 Validation Error
        if hasattr(e, 'read'):
             print(e.read().decode())

if __name__ == "__main__":
    verify()
