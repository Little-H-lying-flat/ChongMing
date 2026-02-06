# 左瞳引擎 (Left Pupil Engine) 开发任务

## Epic: 左瞳引擎 API 测试实现

**模块**: 执行层 - API 测试侧  
**优先级**: P0 (核心模块)  
**预估工时**: 3 周  

---

## Issue #LP-001: Swagger 解析器

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `api`  
**预估**: 3d

### 描述
实现 OpenAPI/Swagger 文档解析，自动提取 API 接口信息。

### 验收标准
- [ ] 支持 OpenAPI 3.0
- [ ] 支持 Swagger 2.0
- [ ] 提取端点、参数、响应模型
- [ ] 生成 API-IR

---

## Issue #LP-002: API-IR 执行器

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `api`  
**预估**: 4d

### 描述
实现 API-IR 协议的 HTTP 请求执行器。

### 验收标准
- [ ] 支持 GET/POST/PUT/DELETE/PATCH
- [ ] Header 注入
- [ ] 认证处理 (Bearer/Basic/API Key)
- [ ] 请求体序列化
- [ ] 响应解析

---

## Issue #LP-003: 变量提取与链式调用

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `api`  
**预估**: 3d

### 描述
实现响应变量提取和 API 链式调用。

### 验收标准
- [ ] JSONPath 提取
- [ ] 正则提取
- [ ] 变量存储
- [ ] 变量注入下一请求
- [ ] 链式执行

---

## Issue #LP-004: 断言引擎

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `api`  
**预估**: 2d

### 描述
实现 API 响应断言引擎。

### 验收标准
- [ ] 状态码断言
- [ ] JSONPath 断言
- [ ] Schema 断言
- [ ] 响应时间断言
- [ ] 自定义断言

---

## Issue #LP-005: RAG 用例生成

**类型**: Feature  
**优先级**: P1  
**标签**: `backend`, `ai`, `rag`  
**预估**: 3d

### 描述
基于 Swagger 和业务知识库，使用 RAG 生成 API 测试用例。

### 验收标准
- [ ] Swagger 向量化
- [ ] 业务规则检索
- [ ] 用例生成
- [ ] 边界值生成

---

## Issue #LP-006: API Worker 实现

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `celery`  
**预估**: 2d

### 描述
实现 API 测试 Celery Worker。

### 验收标准
- [ ] API 执行 Task
- [ ] api_queue 队列
- [ ] 并发执行
- [ ] 结果汇总

---

## Issue #LP-007: API 端点实现

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `api`  
**预估**: 2d

### 描述
实现左瞳引擎的 REST API。

### 验收标准
- [ ] POST /api/v1/api-engine/execute
- [ ] POST /api/v1/api-engine/swagger/parse
- [ ] GET /api/v1/api-engine/executions/{id}

---

## Checklist

- [x] #LP-001 Swagger 解析 ✅ (2026-02-06 swagger_parser.py)
- [x] #LP-002 API-IR 执行器 ✅ (2026-02-06 api_executor.py)
- [x] #LP-003 变量提取 ✅ (2026-02-06 variable_extractor.py)
- [x] #LP-004 断言引擎 ✅ (2026-02-06 assertion_engine.py)
- [ ] #LP-005 RAG 用例生成 (P1 待后续实现)
- [x] #LP-006 API Worker ✅ (2026-02-06 api_tasks.py)
- [x] #LP-007 API 端点 ✅ (2026-02-06 api_engine.py)

**🎉 左瞳引擎 6/7 完成！(RAG 待后续)**

