import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Mock Celery for scheduled tasks
mock_celery = MagicMock()
sys.modules["celery"] = mock_celery
def shared_task_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator
mock_celery.shared_task = shared_task_mock

from app.tasks.scheduled_tasks import cleanup_expired_data, health_check as task_health_check
from app.api.v1.endpoints.health import health_check as api_health_check
from app.core.config import settings

async def verify_zombie_cleanup():
    print("\n[1] Verifying Zombie Cleanup Task...")
    # Setup: Create a dummy "old" file
    test_file = "test_old_file.tmp"
    with open(test_file, "w") as f:
        f.write("data")
    
    try:
        # Run cleanup
        result = cleanup_expired_data()
        print(f"Task Result: {result}")
        
        # Check if file still exists
        if os.path.exists(test_file):
            print("FAIL: File still exists! Task claimed success but did nothing.")
        else:
            print("PASS: File was deleted (Unexpected for a stub).")
            
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

async def verify_fake_health():
    print("\n[2] Verifying Fake Health Check...")
    # The API health check uses settings.VERSION
    # It hardcodes services={"database": "pending", ...}
    
    result = await api_health_check()
    print(f"API Result: {result}")
    
    if result.services["database"] == "pending" or result.services["database"] == "ok":
        print("FAIL: Database status is hardcoded (pending/ok) without checking connection.")
    else:
        print("PASS: Database status reflects reality.")

if __name__ == "__main__":
    asyncio.run(verify_zombie_cleanup())
    asyncio.run(verify_fake_health())
