import asyncio
import sys
import os

# Add backend directory to path so we can import app modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.engines.right_pupil import RightPupilEngine
from app.services.vision.omni_client import OmniClient

async def main():
    print("[*] Initializing RightPupilEngine...")
    try:
        engine = RightPupilEngine()
        
        # Override OmniClient to use our local server
        print("[*] Overriding OmniClient to http://localhost:8002...")
        engine.omni_client = OmniClient(base_url="http://localhost:8002")
        engine.omni_client.timeout = 120.0 # Increase timeout
        
        prompt = "Go to bing.com and type 'OmniParser rocks'"
        url = "https://www.bing.com"
        
        print(f"[*] Starting task: {prompt}")
        
        # Run the task
        logs = await engine.run_task(prompt, url)
        
        print("\n[OK] Task Execution Finished!")
        print(f"[+] Total steps: {len(logs)}")
        for step in logs:
            print(f"  - Step {step.get('step')}: {step.get('status')}")
            action = step.get('action', {})
            print(f"    Action: {action.get('action_type')} -> {action.get('target')}")
            
    except Exception as e:
        print(f"\n[ERR] Task Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
