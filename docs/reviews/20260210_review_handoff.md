# 审查与交付报告: 左瞳引擎 (Left Pupil) & 神经设计层 (Neural Design)

**报告日期**: 2026-02-10
**审查人**: 技术负责人 (Tech Lead)
**状态**: 🔴 有条件的通过 (Conditional Pass)

---

## 1. Code Review (代码深度审查)

### 🔴 Critical Issues (严重问题)
1.  **配置项缺失导致运行时崩溃**:
    - **文件**: `backend/app/services/left_pupil/rag_retriever.py`
    - **位置**: Line 126 (`"model": settings.QWEN_MODEL_NAME`)
    - **问题**: `config.py` 中不存在 `QWEN_MODEL_NAME` 配置项。虽然定义了多个特定模型配置 (如 `MODEL_NEURAL_INTENT`, `MODEL_LEFT_PUPIL_CHAIN` 等)，但没有通用的 `QWEN_MODEL_NAME`。
    - **建议**: 应修改为使用具体的模型配置，例如: `settings.MODEL_General_CHAT` 或在 `config.py` 中添加缺失的配置。

2.  **安全隐患: 动态代码执行**:
    - **文件**: `backend/app/engines/left_pupil/assertion_engine.py`
    - **位置**: Line 337 (`passed = bool(eval(expression, {"__builtins__": {}}, context))`)
    - **问题**: 使用 `eval()` 处理用户输入的表达式断言存在 RCE 风险，即使限制了 `__builtins__`，也不是完全安全的。
    - **建议**: 替换为 `simpleeval` 库或类似的安全表达式解析器。

### ⚠️ Warning Issues (警告问题)
1.  **JSONPath 实现局限性**:
    - **文件**: `backend/app/engines/left_pupil/variable_extractor.py`
    - **位置**: `VariableExtractor._extract_simple_path`
    - **问题**: 当前实现主要依赖简单的字符串分割和索引访问，对于标准的 JSONPath (如过滤表达式 `$.store.book[?(@.price < 10)]`) 支持不足。虽然尝试导入 `jsonpath-ng`，但未强制依赖。
    - **建议**: 应该强制依赖 `jsonpath-ng` 或完善自定义解析器的功能。

2.  **神经设计层 (Neural Design Layer) 实现缺失**:
    - **状态**: 根据 Context 描述该模块 "已经完成代码开发"，但实际审查发现后端服务层 (`backend/app/services/neural_design/`) 缺失，API 端点 (`backend/app/api/v1/endpoints/design.py`) 仅包含 TODO 注释的桩代码。
    - **结论**: **无法进入 Review 阶段**，请确认代码是否已提交或处于另一分支。

3.  **命名规范**:
    - **左瞳引擎**: 整体符合 Python PEP8 规范。类名 (e.g., `LeftPupilEngine`, `APIExecutor`) 清晰，函数命名 (snake_case) 规范。
    - **建议**: 统一 `backend/app/engines/left_pupil/` 和 `backend/app/services/left_pupil/` 下的命名空间管理，避免类名冲突 (如两个 `SwaggerParser`)。

### ✅ Architecture Consistency (架构一致性)
- **左瞳引擎**: 代码结构深受设计文档影响，分层清晰 (Engine -> Executor -> Asserter)，符合设计初衷。
- **Vector DB**: `SpecIngestor` 正确使用了 ChromaDB。

---

## 2. Integration Analysis (接口联调预演)

### A. 左瞳引擎 (Left Pupil Engine)
- **Input**: `API-IR` (JSON Object) 或 `Intent` (String).
- **Output**: `ExecutionResult` / `ExecutionReport`.
- **交互预测**:
    - **痛点**: `SwaggerParser` 解析复杂 OpenAPI 3.1 文档时可能会遇到 `$ref` 解析循环引用问题 (Current implementation handles simple refs only).
    - **数据不一致**: `RagRetriever` 返回的 `ApiContext` 可能与实际运行时 API 响应结构不匹配，导致 Hallucination (幻觉) 生成错误的 `API-IR`。

### B. 神经设计层 (Neural Design Layer) [设计态]
- **交互**: 
    - `DesignRequest` (PRD文本) -> **[Missing Logic]** -> `Draft TC-IR` (API/UI Test Case).
    - `Draft TC-IR` -> **[Critic Agent]** -> `Confirmed TC-IR`.
- **集成风险**: 
    - 由于核心逻辑未实现，该层目前无法与左瞳引擎集成。预期的流程 "Neural Design -> TC-IR -> Left Pupil" 将在第一步断裂。

---

## 3. API Documentation (Update)

以下为 **左瞳引擎** 核心 API 的 OpenAPI 定义片段 (基于 `backend/app/api/v1/endpoints/left_pupil.py`):

```yaml
paths:
  /api-engine/execute/step:
    post:
      summary: 执行单个 API 测试步骤
      description: 执行包含请求、提取和断言的单步 API 测试任务。
      tags:
        - 左瞳引擎
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExecuteStepRequest'
      responses:
        '200':
          description: 执行成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StepResultResponse'
        '500':
          description: 执行引擎错误

  /api-engine/swagger/parse:
    post:
      summary: 解析 Swagger/OpenAPI 文档
      description: 解析 URL 或内容形式的 Swagger 文档，提取 API 端点信息。
      tags:
        - 左瞳引擎
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SwaggerParseRequest'
      responses:
        '200':
          description: 解析成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SwaggerParseResponse'

components:
  schemas:
    ExecuteStepRequest:
      type: object
      properties:
        base_url:
          type: string
          example: "https://api.example.com"
        step:
          $ref: '#/components/schemas/ApiIRStepModel'
        context:
          type: object
          additionalProperties: true
        default_headers:
          type: object
          additionalProperties:
            type: string
      required:
        - base_url
        - step

    ApiIRStepModel:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        request:
          $ref: '#/components/schemas/RequestSpecModel'
        extraction:
          type: object
          additionalProperties:
            type: string
        assertion:
          $ref: '#/components/schemas/AssertionModel'
      required:
        - id
        - request
```

---

## 4. README / Wiki Update

### **左瞳引擎 (Left Pupil Engine)**

**功能简介**:
左瞳引擎是重明系统的 **API 自动化与推理核心**。它负责解析 Swagger 文档建立 API 知识库，通过 LLM 推理 API 间的依赖关系 (Chain Inference)，并执行包含复杂断言和变量提取的 API 测试任务。它是 "读" 和 "做" 的大脑。

**配置项更新**:
在 `.env` 或 `config.py` 中需新增以下配置 (对应模型选择):

```dotenv
# === 左瞳引擎模型配置 ===
# 用于 API 调用链推理 (Dependency Planner)
MODEL_LEFT_PUPIL_CHAIN="qwen-plus"
# 用于参数推导与填充 (Parameter Injection)
MODEL_LEFT_PUPIL_PARAM="qwen-turbo"

# === 向量数据库 ===
CHROMA_DB_PATH="chroma_db"
```

**依赖项变更**:
- `httpx>=0.27.0`: 异步 HTTP 客户端
- `pydantic-settings>=2.1.0`: 配置管理
- `jsonpath-ng` (建议新增): 增强 JSONPath 解析能力

---

## 5. Changelog

### [Unreleased] - 2026-02-10

#### Added (左瞳引擎)
- 新增 `SwaggerParser`: 支持 OpenAPI 3.0/3.1 和 Swagger 2.0 文档的解析与端点提取。
- 新增 `APIExecutor`: 支持基于 API-IR 协议的 HTTP 请求执行，包括 Bearer/Basic 认证、Header 注入。
- 新增 `AssertionEngine`: 实现状态码、JSONPath、正则匹配、Schema 校验等多维度断言机制。
- 新增 `VariableExtractor`: 支持响应数据提取并注入上下文 (`${var}` 语法)。
- 新增 `RagRetriever`: 基于向量数据库的 API 意图检索 (RAG) 基础实现。

#### Changed
- 重构 `config.py`: 引入分层模型配置 (`MODEL_NEURAL_*`, `MODEL_LEFT_PUPIL_*`) 以替代单一模型配置。

#### Fixed
- 修复 `endpoints/left_pupil.py` 中的 Pydantic 模型定义，支持嵌套 Schema 验证。

#### Known Issues
- ⚠️ `Neural Design Layer` (神经设计层) 目前仅包含接口定义，实现逻辑缺失，需在该模块代码提交后重新进行 Review。
- ⚠️ `QWEN_MODEL_NAME` 配置缺失导致 `RagRetriever` 无法通过单元测试。
