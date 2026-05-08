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
    execution_id: str,
    tc_ids: List[str],
    config: dict | None = None,
    dynamic_payload: List[dict] | None = None, # Renamed from adhoc_cases
):
    """
    执行测试用例 (Orchestrator Task)
    """
    try:
        import asyncio
        import traceback
        from app.engines.dispatcher import Dispatcher
        from app.engines.right_pupil import RightPupilEngine
        from app.engines.left_pupil import LeftPupilEngine
        from app.engines.runner.tc_loader import TestCaseLoader
        
        # Imports for Persistence
        from app.services.execution_service import ExecutionService
        from app.models.execution import ExecutionStatus
        from app.schemas.execution import ExecutionMode, TCIR

        config = config or {}
        parallel = config.get("parallel", True)
        max_workers = config.get("max_workers", 3)
        
        # Use dynamic payload if available
        cases_source = "Dynamic" if dynamic_payload else "DB"
        
        logger.info(f"Start Execution {execution_id}: {len(tc_ids)} cases, Parallel={parallel}, Source={cases_source}")
        
        self.update_state(state="PROGRESS", meta={"execution_id": execution_id, "progress": 0})
        
        # --- Helper: Async wrapper for Service calls ---
        
        async def _safe_update_execution(status, summary, duration=0.0):
            try:
                await ExecutionService.update_execution_status(execution_id, status, summary, duration)
            except Exception as e:
                logger.error(f"Failed to update execution record: {e}")

        async def _safe_create_step(tc_id, status, result, duration=0.0, error: str | None = None):
            try:
                await ExecutionService.create_step_result(execution_id, tc_id, status, result, duration, error)
            except Exception as e:
                logger.error(f"Failed to create step record: {e}")

        # --- End Helper ---

        async def run_single_tc(tc_id: str, semaphore: asyncio.Semaphore, initial_context: dict):
            async with semaphore:
                logger.info(f"[{tc_id}] Loading...")
                
                tc_ir = None
                # 1. Try Dynamic Payload first
                if dynamic_payload:
                    case_data = next((c for c in dynamic_payload if c.get("id") == tc_id), None)
                    if case_data:
                        try:
                            # Construct TCIR from dict
                            mode_str = case_data.get("mode", "UI")
                            # Handle Enum conversion
                            try:
                                mode_enum = ExecutionMode(mode_str)
                            except ValueError:
                                mode_enum = ExecutionMode.UI # Default
                            
                            tc_ir = TCIR(
                                id=case_data["id"],
                                name=case_data.get("name", "Ad-hoc Test"),
                                mode=mode_enum,
                                steps=case_data.get("steps", []),
                                priority=case_data.get("priority", "P1"),
                                tags=case_data.get("tags", [])
                            )
                        except Exception as e:
                            logger.error(f"Failed to parse dynamic case {tc_id}: {e}")

                # 2. Try loading from Database
                if not tc_ir:
                    from app.core.database import get_db_session
                    from sqlalchemy import select
                    from app.models.test_case import TestCase
                    try:
                        async with get_db_session() as session:
                            stmt = select(TestCase).where(TestCase.id == tc_id)
                            tc_record = (await session.execute(stmt)).scalar_one_or_none()
                            if tc_record:
                                tc_dict = tc_record.to_tcir()
                                # Convert mode string to enum if necessary for Pydantic
                                try:
                                    if isinstance(tc_dict.get("mode"), str):
                                        tc_dict["mode"] = ExecutionMode(tc_dict["mode"])
                                except Exception:
                                    tc_dict["mode"] = ExecutionMode.UI
                                tc_ir = TCIR(**tc_dict)
                    except Exception as e:
                        logger.error(f"[{tc_id}] DB Load Failed: {e}")

                # 3. Fallback to Legacy Loader (DB/File Mocks)
                if not tc_ir:
                    tc_ir = TestCaseLoader.load(tc_id)
                
                if not tc_ir:
                    logger.error(f"[{tc_id}] Not Found in {cases_source}")
                    await _safe_create_step(tc_id, ExecutionStatus.ERROR, {}, 0.0, f"TC Not Found in {cases_source}")
                    return {"tc_id": tc_id, "status": "error", "error": "TC Not Found"}
                
                # Initialize Engines (Fresh Environment per TC)
                right_pupil = RightPupilEngine()
                left_pupil = LeftPupilEngine()
                dispatcher = Dispatcher()
                dispatcher.attach_engines(right_pupil, left_pupil)
                
                result = None
                ui_session_started = False
                
                try:
                    # Lazy Initialization: CHECK IF UI ENGINE IS NEEDED (STRICT)
                    dataset_steps = tc_ir.steps if isinstance(tc_ir.steps, list) else []
                    
                    mode_str = getattr(tc_ir.mode, "value", str(tc_ir.mode))
                    ui_needed = mode_str in ("UI", "HYBRID", "ExecutionMode.UI", "ExecutionMode.HYBRID")
                    
                    if not ui_needed:
                        for s in dataset_steps:
                            # Handle both dict and object (attribute) access
                            s_type = s.get("step_type") if isinstance(s, dict) else getattr(s, "step_type", None)
                            
                            # Strict matching: ONLY if step_type is explicitly "UI"
                            if s_type == "UI":
                                ui_needed = True
                                break
                    
                    if ui_needed:
                         logger.info(f"[{tc_id}] Initializing RightPupilEngine (UI Steps Detected)...")
                         await right_pupil.start_session(headless=True)
                         ui_session_started = True
                    else:
                         logger.info(f"[{tc_id}] Skipping UI Engine (Pure API / No UI Steps)")

                    async with left_pupil: # Context manager for HTTP client
                        logger.info(f"[{tc_id}] Executing...")
                        result = await dispatcher.execute(tc_ir, execution_id, initial_context=initial_context)
                    
                except Exception as e:
                    logger.error(f"[{tc_id}] Failed: {e}")
                    traceback.print_exc()
                    await _safe_create_step(tc_id, ExecutionStatus.ERROR, {}, 0.0, str(e))
                    return {"tc_id": tc_id, "status": "error", "error": str(e)}
                finally:
                    # Cleanup only if started
                    if ui_session_started:
                        await right_pupil.stop_session()
                    
                # Map result status to Enum
                status_map = {
                    "passed": ExecutionStatus.PASSED,
                    "failed": ExecutionStatus.FAILED,
                    "error": ExecutionStatus.ERROR
                }
                db_status = status_map.get(result.status, ExecutionStatus.ERROR)
                
                # Persist Step Result
                import dataclasses
                await _safe_create_step(
                    tc_id, 
                    db_status, 
                    {
                        "steps": [dataclasses.asdict(s) for s in result.step_results],
                        "variable_trace": result.variable_trace or []
                    }, 
                    result.total_duration_ms, 
                    None
                )

                return {
                    "tc_id": tc_id,
                    "status": result.status,
                    "duration_ms": result.total_duration_ms,
                    "steps_total": len(result.step_results),
                    "steps_passed": sum(1 for s in result.step_results if s.success)
                }

        # Run Loop
        async def main_loop():
            start_time = asyncio.get_event_loop().time()
            await _safe_update_execution(
                ExecutionStatus.RUNNING,
                {"passed": 0, "failed": 0, "skipped": 0},
                0.0,
            )
            
            # 1. Fetch Environment Context
            global_context = {}
            env_id = config.get("env")
            from app.core.database import get_db_session
            from app.services.environment_manager import EnvironmentManager
            try:
                async with get_db_session() as session:
                    env_manager = EnvironmentManager(session)
                    env_record = await env_manager.get(env_id) if env_id else await env_manager.get_default()
                    if env_record:
                        for key, var in env_record.variables.items():
                            val = var.get("value", "")
                            if var.get("encrypted"):
                                val = env_manager._decrypt(val)
                            global_context[key] = val
                        global_context["base_url"] = env_record.base_url
                        global_context["env_name"] = env_record.name
                        logger.info(
                            f"Loaded Environment Context from {'explicit env' if env_id else 'default env'} "
                            f"{env_record.id}/{env_record.name}: {list(global_context.keys())}"
                        )
                    elif env_id:
                        logger.warning(f"Configured execution env not found: {env_id}")
                    else:
                        logger.warning("No execution env specified and no default env configured.")
            except Exception as e:
                logger.error(f"Failed to load execution environment context: {e}")

            semaphore = asyncio.Semaphore(max_workers if parallel else 1)
            tasks = [run_single_tc(tid, semaphore, global_context) for tid in tc_ids]
            
            results = await asyncio.gather(*tasks)
            
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            
            summary = {
                "total": len(tc_ids),
                "passed": sum(1 for r in results if r["status"] == "passed"),
                "failed": sum(1 for r in results if r["status"] == "failed"),
                "error": sum(1 for r in results if r["status"] == "error"),
                "skipped": 0
            }
            
            # 2. Update Execution Record
            final_status = ExecutionStatus.PASSED
            if summary["failed"] > 0 or summary["error"] > 0:
                final_status = ExecutionStatus.FAILED
                
            await _safe_update_execution(final_status, summary, duration)
            
            return results, summary

        # Wrapper to ensuring DB update on background crash
        async def safe_main_loop():
            try:
                return await main_loop()
            except Exception as e:
                logger.critical(f"Async Background Execution Crashed: {e}")
                traceback.print_exc()
                # Attempt to report failure to DB
                try:
                    await ExecutionService.update_execution_status(
                        execution_id, 
                        ExecutionStatus.FAILED, 
                        {"error": f"Background Crash: {str(e)}", "traceback": traceback.format_exc()},
                        0.0
                    )
                except Exception as db_e:
                    logger.error(f"Failed to report background crash to DB: {db_e}")

        try:
            # Check if loop exists (Python 3.12+ compatible)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            
            if loop is None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # API Mode: Loop is running. Schedule as task.
                logger.info(f"Existing loop detected. Scheduling execution {execution_id} as background task.")
                loop.create_task(safe_main_loop()) 
                return {
                    "execution_id": execution_id,
                    "status": "scheduled_async",
                    "info": "Execution running in background loop"
                }
            else:
                # Worker Mode: No running loop, run blocking.
                outcome = loop.run_until_complete(safe_main_loop())
                if outcome is None:
                    # safe_main_loop caught an exception internally
                    return {
                        "execution_id": execution_id,
                        "status": "error",
                        "info": "Execution crashed, see logs"
                    }
                results, summary = outcome
                return {
                    "execution_id": execution_id,
                    "status": "completed",
                    "results": results,
                    "summary": summary
                }

        except Exception as e:
            # This catches launch errors
            logger.critical(f"Execution Launch Failed: {e}")
            raise e

    except Exception as e:
        import traceback
        import asyncio
        from app.services.execution_service import ExecutionService
        from app.models.execution import ExecutionStatus

        error_msg = f"CRITICAL TASK FAILURE: {str(e)}"
        stack_trace = traceback.format_exc()
        logger.critical(error_msg)
        logger.error(stack_trace)
        
        # Attempt to report failure to DB
        try:
            async def report_failure():
                await ExecutionService.update_execution_status(
                    execution_id, 
                    ExecutionStatus.FAILED, 
                    {"error": str(e), "traceback": stack_trace},
                    0.0
                )
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # Use create_task if loop running
                loop.create_task(report_failure())
            else:
                loop.run_until_complete(report_failure())
            
        except Exception as db_e:
            logger.error(f"FATAL: Failed to report failure to DB: {db_e}")

        return {"status": "failed", "error": str(e), "traceback": stack_trace}


@shared_task(name="app.tasks.execute_adhoc_task")
def execute_adhoc_task(prompt: str, url: str):
    """
    执行 Ad-hoc UI 任务
    """
    import asyncio
    from app.engines.right_pupil import RightPupilEngine

    logger.info(f"Start Ad-hoc Task: {prompt} on {url}")
    
    async def run():
        engine = RightPupilEngine()
        logs = await engine.run_task(prompt, url)
        return logs

    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            
        import nest_asyncio
        nest_asyncio.apply()
        logs = loop.run_until_complete(run())
        return {"status": "completed", "logs": logs}
    except Exception as e:
        logger.error(f"Ad-hoc Task Failed: {e}")
        return {"status": "failed", "error": str(e)}

@shared_task(name="app.tasks.cancel_execution")
def cancel_execution(execution_id: str):
    """取消执行"""
    logger.info(f"取消执行: {execution_id}")
    # TODO: 实现取消逻辑
    return {"execution_id": execution_id, "cancelled": True}
