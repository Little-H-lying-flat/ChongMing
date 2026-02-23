import asyncio
from sqlalchemy import text
from app.core.database import get_db_session

async def main():
    async with get_db_session() as session:
        # Get the execution result steps directly from execution_results table? 
        # Or test_cases steps?
        # Let's check test_cases first
        res = await session.execute(text("SELECT steps FROM test_cases WHERE id='TC-F02D10FE'"))
        row = res.scalar()
        print("Test Case Steps:")
        print(row)
        
        # Now check execution steps
        print("Execution Steps associated with TC-F02D10FE:")
        res = await session.execute(text("SELECT execution_id, step_index, status, action_taken, target_description, screenshot_before, screenshot_after FROM execution_steps WHERE tc_id='TC-F02D10FE' ORDER BY created_at DESC LIMIT 10"))
        rows = res.fetchall()
        for r in rows:
            print(f"Index {r.step_index}: status={r.status}, action={r.action_taken}, target={r.target_description}, b={(r.screenshot_before is not None)}, a={(r.screenshot_after is not None)}")
            if r.screenshot_before and r.screenshot_after and r.screenshot_before == r.screenshot_after:
                print(f"  -> Screenshots MATCH EXACTLY for step {r.step_index}")

asyncio.run(main())
