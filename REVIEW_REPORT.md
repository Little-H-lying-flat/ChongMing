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

---

# 可用性修复记录

**Date**: 2026-05-17
**Scope**: Smart Ops、Design/API Auto/Left Pupil、Executions、Visual UI、Turbo、pytest 根目录配置

## 已修复问题

1. **Smart Ops Provider API Key 保存**
   - 后端 `POST /smart-ops/provider` 不再返回 501，改为校验 provider 与 API key 后保存。
   - API key 写入 `AIProviderConfig.api_key_ciphertext` 前会加密，响应不返回明文。
   - `AIConfigService.get_provider_config()` 优先读取数据库 active provider 配置，解密后供调用链使用；无数据库配置时 fallback 到环境变量配置。

2. **Design 保存 API 用例 step schema**
   - Design 生成的 API step 统一保存为 API Auto / Left Pupil 期望的 `request`、`assertion`、`extraction` 结构。
   - 同时保留 `method`、`url`、`expected_status_code`、`json_assertions`、`extract` 等旧扁平字段，兼容历史数据和旧 dispatcher 路径。
   - Left Pupil 增加旧扁平 step 的后端兼容归一化，避免旧用例执行时 422。

3. **Executions 环境选择**
   - 前端回归执行环境从自由文本输入改为环境下拉，提交环境 ID。
   - 后端环境解析改为 ID 优先、name fallback、未传时使用默认环境，API 层和异步任务执行层保持一致。

4. **Visual UI 执行结果耗时字段**
   - 前端执行结果类型补齐后端真实字段。
   - Visual UI 详情页总耗时优先展示 `duration_seconds`，保留 `duration_ms / 1000` 作为旧响应 fallback。

5. **API Auto / Turbo 分页参数**
   - API 用例列表请求统一使用后端契约 `page_size=100`，不再发送 `pageSize` 或只取默认 20 条。

6. **根目录 pytest 配置**
   - 新增根目录 `pytest.ini`，限制 pytest 从 `backend/tests` 收集，避免误收集 `.txt` 输出产物。
   - 同步 backend 现有 pytest 关键配置和 warning 过滤。

## 验证结果

- `backend/.venv-py312/Scripts/python.exe -m pytest backend/tests/e2e/test_flow6_smart_ops.py backend/tests/unit/services/test_ai_config_service.py -v`：6 passed
- `backend/.venv-py312/Scripts/python.exe -m pytest backend/tests/integration/test_test_cases_api_contract.py backend/tests/integration/test_test_cases_backward_compat.py -v`：8 passed
- `backend/.venv-py312/Scripts/python.exe -m pytest backend/tests/integration/test_environment_api.py backend/tests/unit/test_environment_manager.py -v`：26 passed
- `backend/.venv-py312/Scripts/python.exe -m pytest --collect-only`：从仓库根目录收集 277 items，未再收集 `.txt` 产物
- `npm --prefix frontend run lint`：通过
- `npm --prefix frontend run build`：通过；仍有既有 Recharts 容器尺寸 warning，不阻塞构建
