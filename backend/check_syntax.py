
import sys
import os

sys.path.append(os.getcwd())

print("Checking data_factory.py...")
try:
    from app.api.v1.endpoints import data_factory
    print("data_factory.py OK")
except Exception as e:
    print(f"data_factory.py FAILED: {e}")

print("Checking executions.py...")
try:
    from app.api.v1.endpoints import executions
    print("executions.py OK")
except Exception as e:
    print(f"executions.py FAILED: {e}")

print("Checking execution_tasks.py...")
try:
    from app.tasks import execution_tasks
    print("execution_tasks.py OK")
except Exception as e:
    print(f"execution_tasks.py FAILED: {e}")
