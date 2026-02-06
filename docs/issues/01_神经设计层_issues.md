# 神经设计层 (Neural Design Layer) 开发任务

## Epic: 神经设计层实现

**模块**: 智能层 - 设计侧  
**优先级**: P0 (核心模块)  
**预估工时**: 3 周  

---

## Issue #ND-001: PRD 解析器实现

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `ai`, `neural-design`  
**预估**: 3d

### 描述
实现 PRD 文档解析器，支持从 Markdown/Word/Confluence 格式提取测试意图。

### 验收标准
- [ ] 支持 Markdown 格式 PRD 解析
- [ ] 支持 Word 文档解析 (python-docx)
- [ ] 识别功能模块列表
- [ ] 识别用户场景流程
- [ ] 识别边界条件
- [ ] 识别数据约束
- [ ] 单元测试覆盖 > 80%

### 技术细节
```python
class PRDParser:
    async def parse(self, content: str, format: str) -> PRDParseResult
```

### 依赖
- LangChain
- Qwen3-Max API

---

## Issue #ND-002: 用例生成引擎

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `ai`, `neural-design`  
**预估**: 5d

### 描述
实现基于 LLM 的测试用例生成引擎，将 PRD 解析结果转化为 TC-IR 格式用例。

### 验收标准
- [ ] 支持 UI 模式用例生成
- [ ] 支持 API 模式用例生成
- [ ] 支持 HYBRID 模式用例生成
- [ ] 实现 Smoke/Regression/Full 覆盖策略
- [ ] 生成的 TC-IR 符合 schema 规范
- [ ] 单元测试覆盖 > 80%

### 技术细节
- 使用 LangChain 构建 Chain
- 实现 Few-shot Prompting
- 输出 JSON Schema 约束

---

## Issue #ND-003: Critic Agent 评审器

**类型**: Feature  
**优先级**: P1  
**标签**: `backend`, `ai`, `neural-design`  
**预估**: 3d

### 描述
实现用例质量评审 Agent，为生成的用例打分并提供改进建议。

### 验收标准
- [ ] 评审维度：完整性、可执行性、覆盖度
- [ ] 输出评分 (0-1)
- [ ] 输出改进建议列表
- [ ] 支持迭代优化

---

## Issue #ND-004: 知识库 RAG 检索

**类型**: Feature  
**优先级**: P1  
**标签**: `backend`, `ai`, `rag`  
**预估**: 4d

### 描述
实现基于 ChromaDB 的项目知识库检索，为用例生成提供上下文。

### 验收标准
- [ ] 文档向量化存储
- [ ] 相似度检索 Top-K
- [ ] 上下文注入到 Prompt

### 依赖
- ChromaDB
- text-embedding-3-small

---

## Issue #ND-005: API 端点实现

**类型**: Feature  
**优先级**: P0  
**标签**: `backend`, `api`  
**预估**: 2d

### 描述
实现神经设计层的 REST API 端点。

### 验收标准
- [ ] POST /api/v1/design/parse-prd
- [ ] POST /api/v1/design/generate
- [ ] GET /api/v1/design/generations/{id}
- [ ] SSE 进度推送
- [ ] OpenAPI 文档

---

## Issue #ND-006: 前端集成

**类型**: Feature  
**优先级**: P1  
**标签**: `frontend`, `react`  
**预估**: 3d

### 描述
实现设计工作台前端界面，支持 PRD 输入和用例预览。

### 验收标准
- [ ] PRD 输入区 (Markdown 编辑器)
- [ ] 用例生成按钮
- [ ] 实时进度显示 (SSE)
- [ ] 用例列表预览
- [ ] 用例编辑功能

---

## Checklist

- [ ] #ND-001 PRD 解析器
- [ ] #ND-002 用例生成引擎
- [ ] #ND-003 Critic Agent
- [ ] #ND-004 RAG 检索
- [ ] #ND-005 API 端点
- [ ] #ND-006 前端集成
