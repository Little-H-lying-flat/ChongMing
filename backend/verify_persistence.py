
import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app.engines.dispatcher import Dispatcher
from app.schemas.execution import TCIR, ExecutionMode
from app.services.execution_service import ExecutionService
from app.models.execution import ExecutionStatus
import dataclasses

async def verify_persistence():
    print("🚀 Starting Persistence Verification...")
    
    # 1. Setup Dummy TCIR
    tcir = TCIR(
        id="TC-VERIFY-001",
        name="Verification Case",
        mode=ExecutionMode.API,
        steps=[
            {
                "name": "Verify Google",
                "description": "Ping Google to check connection",
                "step_type": "API",
                "url": "https://www.google.com",
                "method": "GET",
                "headers": {},
                "body": None
            }
        ]
    )
    
    # 2. Execute via Dispatcher
    print("running dispatcher...")
    dispatcher = Dispatcher()
    # Mock engines if needed, or rely on real ones if they don't block
    from app.engines.left_pupil import LeftPupilEngine
    dispatcher.attach_engines(left_pupil=LeftPupilEngine())
    
    result = await dispatcher.execute(tcir)
    print(f"Dispatcher Result Success: {result.success}")
    
    # Check if details are in the result object
    step_result = result.step_results[0]
    print(f"Step Result Details Present: {step_result.details is not None}")
    if step_result.details:
        print(f"Step Name in Details: {step_result.details.get('step_name')}")
    
    # 3. Simulate Persistence (like execution_tasks.py)
    execution_id = "EXEC_VERIFY_001"
    tc_id = "TC-VERIFY-001"
    
    # Create execution record first
    await ExecutionService.create_execution(execution_id, [tc_id], {})
    
    step_data = {
        "steps": [dataclasses.asdict(s) for s in result.step_results]
    }
    
    print("\n💾 Saving to DB...")
    await ExecutionService.create_step_result(
        execution_id,
        tc_id,
        ExecutionStatus.PASSED,
        step_data,
        result.total_duration_ms
    )
    
    # 4. Read back from DB
    print("\n📖 Reading back from DB...")
    read_result = await ExecutionService.get_execution_result_dict(execution_id)
    
    cases = read_result.get("cases", [])
    if not cases:
        print("❌ No cases found in read back result!")
        return
        
    first_case = cases[0]
    steps = first_case.get("steps", [])
    if not steps:
        print("❌ No steps found in case!")
        return
        
    first_step = steps[0]
    details = first_step.get("details")
    
    if details:
        print("✅ SUCCESS! Details found in DB record.")
        print(f"   Step Name: {details.get('step_name')}")
        print(f"   Request URL: {details.get('request', {}).get('url')}")
    else:
        print("❌ FAILURE! Details MISSING in DB record.")
        print(f"   Step Keys: {first_step.keys()}")

if __name__ == "__main__":
    asyncio.run(verify_persistence())
