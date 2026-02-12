"""
执行任务 - Celery Tasks

负责异步执行测试用例
"""

from typing import List
from celery import shared_task
from loguru import logger


@shared_task(bind=True, name="app.tasks.execute_test_cases")
def execute_test_cases(
    self,
    tc_ids: List[str],
    config: dict = None,
):
    """
    执行测试用例 (Orchestrator Task)
    """
    import asyncio
    import uuid
    from app.engines.dispatcher import Dispatcher
    from app.engines.right_pupil import RightPupilEngine
    from app.engines.left_pupil import LeftPupilEngine
    from app.engines.runner.tc_loader import TestCaseLoader

    config = config or {}
    execution_id = f"EXEC_{uuid.uuid4().hex[:8].upper()}"
    parallel = config.get("parallel", True)
    max_workers = config.get("max_workers", 3)
    
    logger.info(f"Start Execution {execution_id}: {len(tc_ids)} cases, Parallel={parallel}")
    
    self.update_state(state="PROGRESS", meta={"execution_id": execution_id, "progress": 0})
    
    async def run_single_tc(tc_id: str, semaphore: asyncio.Semaphore):
        async with semaphore:
            logger.info(f"[{tc_id}] Loading...")
            tc_ir = TestCaseLoader.load(tc_id)
            if not tc_ir:
                logger.error(f"[{tc_id}] Not Found")
                return {"tc_id": tc_id, "status": "error", "error": "TC Not Found"}
            
            # Initialize Engines (Fresh Environment per TC)
            # For API tests, we can reuse HTTP client potentially, but cleaner to isolate.
            # For UI tests, we MUST have separate Page/Context. 
            # RightPupilEngine.start_session handles browser launch.
            
            # Note: Launching 5 browsers in parallel is heavy. 
            # In production we might share the 'browser' and creating 'contexts'.
            # But RightPupilEngine current refactor spawns a browser. 
            # We stick to max_workers=3 to avoid OOM.
            
            right_pupil = RightPupilEngine()
            left_pupil = LeftPupilEngine()
            dispatcher = Dispatcher()
            dispatcher.attach_engines(right_pupil, left_pupil)
            
            result = None
            try:
                # Setup specific engine if needed
                if tc_ir.mode.value in ["UI", "HYBRID"]:
                     # Headless default unless debug mode
                     await right_pupil.start_session(headless=True)
                
                async with left_pupil: # Context manager for HTTP client
                    logger.info(f"[{tc_id}] Executing...")
                    result = await dispatcher.execute(tc_ir)
                
            except Exception as e:
                logger.error(f"[{tc_id}] Failed: {e}")
                import traceback
                traceback.print_exc()
                return {"tc_id": tc_id, "status": "error", "error": str(e)}
            finally:
                # Cleanup
                await right_pupil.stop_session()
                # left_pupil auto-closed by async with
                
            return {
                "tc_id": tc_id,
                "status": result.status,
                "duration_ms": result.total_duration_ms,
                "steps_total": len(result.step_results),
                "steps_passed": sum(1 for s in result.step_results if s.success)
            }

    # Run Loop
    async def main_loop():
        semaphore = asyncio.Semaphore(max_workers if parallel else 1)
        tasks = [run_single_tc(tid, semaphore) for tid in tc_ids]
        
        # We can use as_completed to update progress?
        # Or simple gather. for simplicity: gather.
        results = await asyncio.gather(*tasks)
        return results

    # Celery is sync, but we need async for Playwright/HTTPX
    # We create a new event loop or use existing? 
    # Celery worker is typically process-based (prefork). 
    # Can run asyncio.run() safely if no other loop is running in this thread.
    
    try:
        # Check if loop exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # If loop is running (e.g. Gevent/Eventlet), this might be tricky.
        # Assuming standard prefork worker.
        results = asyncio.run(main_loop())
        
    except Exception as e:
        logger.critical(f"Execution Loop Crashed: {e}")
        return {"status": "failed", "error": str(e)}

    logger.info(f"Execution {execution_id} Completed")
    
    return {
        "execution_id": execution_id,
        "status": "completed",
        "results": results,
        "summary": {
            "total": len(tc_ids),
            "passed": sum(1 for r in results if r["status"] == "passed"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "error": sum(1 for r in results if r["status"] == "error")
        }
    }


@shared_task(name="app.tasks.cancel_execution")
def cancel_execution(execution_id: str):
    """取消执行"""
    logger.info(f"取消执行: {execution_id}")
    # TODO: 实现取消逻辑
    return {"execution_id": execution_id, "cancelled": True}
