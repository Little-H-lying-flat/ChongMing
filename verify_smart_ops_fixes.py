import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Mock Celery
mock_celery = MagicMock()
sys.modules["celery"] = mock_celery
sys.modules["celery.schedules"] = MagicMock()
sys.modules["celery.result"] = MagicMock()
sys.modules["kombu"] = MagicMock()

def shared_task_mock(*args, **kwargs):
    def decorator(func):
        func.delay = MagicMock(return_value=MagicMock(id="TASK_123"))
        return func
    return decorator
mock_celery.shared_task = shared_task_mock

from app.tasks.scheduled_tasks import cleanup_expired_data, daily_regression
from app.api.v1.endpoints.health import health_check
from app.core.config import settings
import app.worker # Load module so patch works

async def test_cleanup():
    print("\n[1] Testing Clean Task (Dry Run)...")
    # It should effectively do nothing but print logs since we don't have expired files in verified env
    # But we want to ensure it runs without error and respects safety guards
    try:
        result = cleanup_expired_data()
        print(f"Cleanup Result: {result}")
        if result['status'] == 'completed' or result['status'] == 'skipped':
            print("PASS: Cleanup ran successfully (Safely)")
        else:
            print("FAIL: Cleanup failed")
    except Exception as e:
        print(f"FAIL: Cleanup Exception: {e}")

async def test_regression():
    print("\n[2] Testing Regression Trigger...")
    from app.tasks.execution_tasks import execute_test_cases
    
    result = daily_regression()
    print(f"Regression Result: {result}")
    
    if execute_test_cases.delay.called:
         print("PASS: execute_test_cases.delay() was called")
    else:
         print("FAIL: execute_test_cases.delay() was NOT called")

async def test_health_check():
    print("\n[3] Testing Health Check Probes...")
    
    # We need to mock DB dependency
    mock_db = AsyncMock()
    # Mock execute "SELECT 1"
    mock_db.execute = AsyncMock(return_value=True)
    
    # Mock celery.connection_or_acquire by patching where it is imported or the module itself
    # Since health.py does `from app.worker import celery`, we need to patch `app.worker.celery`
    # But `app` might not have `worker` attribute if it wasn't imported.
    # Let's verify if we can import it first. 
    # Or just patch sys.modules? 
    # Or patch `app.api.v1.endpoints.health.celery` if it was imported at module level? 
    # No, it's imported inside the function.
    
    # We'll use a safer patch string because `app` is in sys.path
    with patch("app.worker.celery") as mock_worker_celery:
        mock_conn = MagicMock()
        mock_worker_celery.connection_or_acquire.return_value.__enter__.return_value = mock_conn
        
        # Run Health Check
        response = await health_check(db=mock_db)
        print(f"Health Response: status={response.status} services={response.services}")
        
        if response.services['database'] == 'ok' and response.services['celery'] == 'ok':
            print("PASS: Health Check verified DB and Celery connections")
        else:
             print("FAIL: Health Check failed to verify connections")

if __name__ == "__main__":
    asyncio.run(test_cleanup())
    asyncio.run(test_regression())
    asyncio.run(test_health_check())
