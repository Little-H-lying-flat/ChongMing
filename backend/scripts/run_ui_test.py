import asyncio
import sys
import os
import argparse
from pathlib import Path

# Fix path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.engines.right_pupil import RightPupilEngine
from app.engines.runner.tc_loader import TestCaseLoader
from app.schemas.aui_ir import VisualActionIR, VisualLocator
from loguru import logger

async def main(tc_id, headless):
    logger.info(f"🚀 Starting Test: {tc_id}")
    
    # 1. Load Test Case
    tc = TestCaseLoader.load(tc_id)
    if not tc:
        logger.error(f"❌ Test Case {tc_id} not found!")
        return

    logger.info(f"📋 Scenario: {tc.name}")
    
    # 2. Init Engine
    engine = RightPupilEngine()
    
    try:
        await engine.start_session(headless=headless)
        
        # 3. Execute Steps
        for i, step_data in enumerate(tc.steps):
            logger.info(f"▶️ Step {i+1}: {step_data.get('action')} {step_data.get('params', '')}")
            
            # Convert TC step (dict) to VisualActionIR
            action_type = step_data.get("action")
            params = step_data.get("params", {})
            target_data = step_data.get("target")
            
            target = None
            if target_data:
                target = VisualLocator(
                    strategy=target_data.get("strategy", "dom"),
                    value=target_data.get("value"),
                    bbox=target_data.get("bbox")
                )
                
            action = VisualActionIR(
                id=f"step_{i}",
                action_type=action_type,
                params=params,
                target=target,
                description=f"Step {i}"
            )
            
            # Execute
            success = await engine.runner.execute(action)
            
            if not success:
                logger.error(f"❌ Step {i+1} Failed!")
                break
                
        logger.success(f"✅ Test {tc_id} Completed Successfully")
        
    except Exception as e:
        logger.error(f"💥 Execution Error: {e}")
    finally:
        await engine.stop_session()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run UI Test Scenario")
    parser.add_argument("tc_id", type=str, help="Test Case ID (e.g. TC_UI_BING_SEARCH)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--headed", action="store_false", dest="headless", help="Run in headed mode")
    parser.set_defaults(headless=True)
    
    args = parser.parse_args()
    asyncio.run(main(args.tc_id, args.headless))
