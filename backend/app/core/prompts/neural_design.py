"""
Neural Design Layer 提示词模板
"""

PRD_ANALYSIS_PROMPT = """
你是一个资深的 API 测试专家。请分析以下需求文档（PRD）或用户描述，提取出需要测试的关键功能点和业务流程。

### 输入需求
{requirement_text}

### 上下文信息
{context}

### 任务
1. 识别核心业务场景。
2. 提取每个场景的关键测试点（正向和异常）。
3. 输出结果应包含：场景名称、测试点列表、预估的 API 调用链。

请以 JSON 格式输出，结构如下：
{{
    "scenarios": [
        {{
            "name": "场景名称",
            "description": "场景描述",
            "test_points": ["测试点1", "测试点2"],
            "api_chain": ["API1 (Method Path)", "API2"]
        }}
    ]
}}
"""

TC_GENERATION_PROMPT = """
基于以下测试场景和 API 定义，生成详细的 API 测试用例（API-IR 格式）。

### 测试场景
{scenario_description}

### 可用 API
{available_apis}

### 任务
生成一个多步骤的测试用例 (`DraftTestCase`)。
每个步骤应包含：意图、HTTP 方法、URL、请求体示例、预期结果。

请严格遵守以下 JSON 格式：
{{
    "case_name": "...",
    "description": "...",
    "steps": [
        {{
            "step_id": "step1",
            "intent": "...",
            "method": "POST",
            "url_path": "/api/...",
            "description": "...",
            "input_data": {{...}},
            "expected_outcome": "..."
        }}
    ]
}}
"""

CRITIC_PROMPT = """
请审查以下生成的测试用例，并在必要时进行修正。

### 待审查用例
{draft_test_case}

### 审查标准
1. **完整性**: 是否遗漏了必要的鉴权 Token？是否包含了依赖数据的提取（如从登录响应提取 token）？
2. **正确性**: HTTP 方法和 URL 路径是否符合 REST 规范？
3. **安全性**: 是否包含敏感信息硬编码（如密码）？
4. **覆盖率**: 是否包含了必要的断言（Assertion）？

如果发现问题，请输出修改建议或直接修正后的 JSON。
"""
