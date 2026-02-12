import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Mock Celery update_state to avoid 'AttributeError' when calling task function directly
# (When calling task function directly, 'self' is passed if bind=True, but we need to mock it)

# Mock Celery to avoid import errors
mock_celery = MagicMock()
sys.modules["celery"] = mock_celery

# Define shared_task decorator mock
def shared_task_mock(*args, **kwargs):
    def decorator(func):
        # Attach a .run method to the decorated function to simulate Celery task
        func.run = func 
        return func
    return decorator

mock_celery.shared_task = shared_task_mock

from app.engines.dispatcher import Dispatcher, TCIR, ExecutionMode
from app.tasks.execution_tasks import execute_test_cases

def test_zombie_stub():
    print("\n[1] Testing Zombie Stub Task...")
    
    # execute_test_cases is a @shared_task. 
    # To call the underlying function, we usually just call it if we can access the original func,
    # or rely on the __call__ method if Celery is set up? 
    # Actually, @shared_task decorates the function. 
    # We can try calling `execute_test_cases(tc_ids, config)`. 
    # Since `bind=True`, the first arg is `self`.
    
    # Mock 'self' object for Celery task
    mock_self = MagicMock()
    mock_self.update_state = MagicMock()
    
    tc_ids = ["TC_001", "TC_002"]
    config = {"parallel": True, "max_workers": 5}
    
    try:
        # Call the function directly (bypassing Celery broker)
        # Type hint says execute_test_cases(self, tc_ids, config)
        # Note: The decorated object `execute_test_cases` is a Task instance. 
        # Calling it directly `execute_test_cases(...)` usually works locally if configured, 
        # assuming no async internals that fail.
        # But wait, the function code has `results = []` and `results.append({ "status": "passed" })`.
        # It does NOT use `Dispatcher`.
        
        # We need to invoke the underlying python function. 
        # Celery tasks usually store it in `execute_test_cases.run` or similar? 
        # Or we can just call it and pass the mock self?
        # Let's try calling it as a bound method or static?
        # Actually simplest way is to check the source code behavior. 
        
        # We will try to run it. If it fails due to Celery magic, we mock around it.
        # But this is a basic function test.
        
        # Actually, `execute_test_cases` IS the proxy. 
        # `execute_test_cases.run` isn't standard public API.
        
        # Let's verify by just inspecting what it does.
        # It's better to verify the *behavior* of the code we see.
        pass
    except Exception as e:
        print(f"Setup error: {e}")

    # Let's run it by importing the module and accessing the function "unwrapped" if possible?
    # No, let's just use the `execute_test_cases` object and hope it runs synchronously for testing.
    # If not, we mock the `app.tasks.execution_tasks` module structure.
    
    # Re-reading `backend/app/tasks/execution_tasks.py`:
    # It has `@shared_task(bind=True...) def execute_test_cases(self, ...)`
    
    # We can invoke `.run(mock_self, ...)` if available?
    # Or just `execute_test_cases(tc_ids=[...])`?
    
    # Let's try to simulate the run.
    try:
        # We can't easily mock the internal behavior if we just call it.
        # But we know it's a stub. 
        pass
    except:
        pass

    # Let's write a "test" that asserts the Stub nature by reading the file content logic 
    # or by running a simplified version of the logic we observed.
    
    # Actually, I'll just write a script that imports it and tries to run it with a Mock 'self'.
    # If it returns "completed" instantly without doing anything real, it confirms the bug.
    
    try:
        result = execute_test_cases.run(mock_self, tc_ids, config)
        
        print(f"Result Status: {result['status']}")
        print(f"Results Count: {len(result['results'])}")
        
        # Check if it actually did anything "real"
        # The result['results'] contains `{'status': 'passed'}`.
        # If it was real, it should have failed because we didn't provide real TC IDs or DB.
        # The fact that it 'passed' proves it's a stub!
        
        passed_count = sum(1 for r in result['results'] if r['status'] == 'passed')
        if passed_count == len(tc_ids):
             print("FAILURE: Task returned 'passed' for nonexistent TCs. It is a zombie stub.")
        else:
             print("PASS: Task failed as expected (Logic is real).")
             
    except Exception as e:
         print(f"Error running task: {e}")

async def test_dispatcher_isolation():
    print("\n[2] Testing Dispatcher Isolation...")
    # Verify Dispatcher raises error if engines not attached
    from app.engines.dispatcher import Dispatcher, TCIR, ExecutionMode
    
    dispatcher = Dispatcher()
    # Don't attach engines
    
    tc_ir = TCIR(
        id="TC_TEST", name="Test", mode=ExecutionMode.UI, steps=[{"type": "UI", "action": "click"}]
    )
    
    try:
        await dispatcher.execute(tc_ir)
        print("FAIL: Dispatcher executed without engines attached!")
    except RuntimeError as e:
        if "右瞳引擎未初始化" in str(e):
            print("PASS: Dispatcher correctly raised error when uninitialized.")
        else:
            print(f"FAIL: Unexpected error: {e}")
    except Exception as e:
        print(f"FAIL: Unexpected error type: {e}")

if __name__ == "__main__":
    test_zombie_stub()
    asyncio.run(test_dispatcher_isolation())
