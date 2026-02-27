import asyncio
import sys
import os
from loguru import logger

# Ensure backend is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from app.engines.right_pupil import RightPupilEngine
from app.core.config import settings

async def run_real_ui_e2e():
    print("=========================================================")
    print("🚀 ChongMing Right Pupil Real-World UI E2E Test 🚀")
    print("=========================================================")
    
    # Pre-flight Check
    if not settings.QWEN_API_KEY:
        logger.error("❌ QWEN_API_KEY is not set. Real UI testing requires a VL model.")
        return
        
    print(f"ℹ️ OmniParser URL: {settings.OMNIPARSER_URL}")
    print(f"ℹ️ Visual LLM: {settings.MODEL_RIGHT_PUPIL_VL}")
    
    # Initialize the engine
    engine = RightPupilEngine()
    
    target_url = "https://dummyjson.com/"
    task_prompt = "Click the 'Docs' link in the top navigation bar to go to the documentation page."
    
    print(f"\n🎯 [Task] {task_prompt}")
    print(f"🌐 [URL]  {target_url}")
    print("---------------------------------------------------------")
    
    try:
        # Run the task. We expect this to pull up the browser, parse the tree, 
        # let Qwen reason that it needs to click the Docs link, and execute the click.
        report = await engine.run_task(
            prompt=task_prompt, 
            url=target_url,
            # We enforce a small max_steps to prevent infinite loop if confused
            # 1 step to perceive docs, 1 step to click, 1 step to realize done
        )
        
        print("\n✅ Execution Finished.")
        print(f"Result Report: {report}")
        
    except Exception as e:
        logger.error(f"❌ Execution failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_real_ui_e2e())
