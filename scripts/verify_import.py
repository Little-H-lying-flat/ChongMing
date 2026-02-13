# scripts/verify_import.py
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    print("Importing app.tasks.execution_tasks...")
    from app.tasks.execution_tasks import execute_adhoc_task
    print("[PASS] Import successful.")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
