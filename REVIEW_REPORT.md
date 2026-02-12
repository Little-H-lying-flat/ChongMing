# Turbo Engine Audit Report

**Date**: 2026-02-12
**Scope**: `backend/app/engines/dispatcher.py`, `backend/app/tasks/execution_tasks.py`, `backend/app/services/runner/ui_runner.py`
**Auditor**: Tech Lead (AI Assistant)

## 📊 Summary
The "Turbo Engine" (Execution Layer) determines how test cases are scheduled and executed. The audit reveals that while the **Dispatcher logic exists**, the **Execution Logic is a Stub**. The system currently **cannot execute real tests** via the API/Celery.

| Category | Status | Critical Issues |
| :--- | :--- | :--- |
| **functionality** | 🔴 Critical | `execute_test_cases` task is a completely invalid Stub |
| **Performance** | 🔴 Critical | Parallel execution logic is missing (ignored config) |
| **Integration** | 🟠 High | `Dispatcher` is not connected to `LeftPupil` or `RightPupil` |

## 🚨 Critical Issues (High Severity)

### 1. Execution Task is a Zombie Stub
- **File**: `backend/app/tasks/execution_tasks.py`
- **Method**: `execute_test_cases` (Line 13)
- **Problem**: The task that supposed to run tests contains only **TODOs** and fake loops. It does **not** instantiate the `Dispatcher`, does **not** load test cases, and does **not** execute anything.
    ```python
    # TODO: 实际执行逻辑
    # ...
    # TODO: 调用 Dispatcher 执行
    results.append({ "tc_id": tc_id, "status": "passed" }) # FAKE SUCCESS
    ```
- **Impact**: Any "Execution" triggered via API will instantly succeed with fake results, deceiving users. **The system is non-functional.**
- **Fix**: Implement the task to:
    1.  Load TC-IR data (mock or DB).
    2.  Instantiate `Dispatcher`.
    3.  Instantiate `LeftPupilEngine` and `RightPupilEngine`.
    4.  Call `dispatcher.attach_engines(...)`.
    5.  Call `dispatcher.execute(tc_ir)`.

### 2. Missing Parallel Execution
- **File**: `backend/app/tasks/execution_tasks.py`
- **Problem**: The `ExecutionRequest` accepts `parallel=True` and `max_workers`, but the task iterates sequentially.
    ```python
    for i, tc_id in enumerate(tc_ids): # Sequential loop
        # ...
    ```
- **Fix**: Use `asyncio.gather` or a `ProcessPoolExecutor` (if CPU bound, though here IO bound) to execute test cases in parallel if `config['parallel']` is True.

### 3. Dispatcher Isolation
- **File**: `backend/app/engines/dispatcher.py`
- **Problem**: `Dispatcher` relies on `attach_engines` to function. If the caller (`execution_tasks`) forgets this, `execute` raises `RuntimeError`.
- **Fix**: Verify `execute_test_cases` properly sets up the `Dispatcher` dependency graph.

## ⚠️ Major Issues (Medium Severity)

### 4. UI Runner Coordinate Strategy
- **File**: `backend/app/services/runner/ui_runner.py`
- **Method**: `_handle_interaction`
- **Problem**: When using `visual` strategy, it converts `target.value` to `int` (SoM ID). If the ID map is missing or stale, it raises `ValueError` causing the step to fail.
- **Fix**: Ensure `SoMRenderer` (in Right Pupil) provides a fresh, valid `id_map` for every visual step execution.

## ✅ Conclusion
The Turbo Engine is currently **Dysfunctional**. The core routing logic (`Dispatcher`) is written but **unplugged**. The Celery task system is merely "going through the motions" without performing work.

**Priority Actions:**
1.  **Implement `execute_test_cases`**: Connect the wires between Celery, Dispatcher, and Engines.
2.  **Enable Parallelism**: Implement `asyncio.gather` for concurrent test execution.
3.  **Mock/DB Integration**: Since DB might be missing, create a `TestCaseLoader` mock to provide TC-IR data for execution.
