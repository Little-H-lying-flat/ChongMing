"""
AI 调用示例

展示如何在不同模块中使用 AI 客户端
"""

import asyncio
from app.core.ai_client import get_ai_manager, Message, AIModule


async def example_neural_layer():
    """神经设计层示例 - 意图解析"""
    manager = get_ai_manager()
    
    # 使用神经设计层的意图解析模块 (自动使用 qwen-max)
    response = await manager.invoke(
        module=AIModule.AGENT_NEURAL_ADMIN,
        messages=[
            Message(
                role="system",
                content="你是一个测试用例设计专家，负责解析用户意图并生成测试场景。"
            ),
            Message(
                role="user",
                content="测试用户登录功能，包含正常登录、密码错误、账号不存在等场景"
            ),
        ],
    )
    
    print(f"意图解析结果:\n{response.content}")
    print(f"Token 消耗: {response.usage}")


async def example_right_pupil_vision():
    """右瞳引擎示例 - 视觉元素定位"""
    manager = get_ai_manager()
    
    # 使用视觉模型定位页面元素
    response = await manager.invoke_vision(
        module=AIModule.RIGHT_PUPIL_GROUNDING,
        prompt="请找到页面中的'登录'按钮，返回其位置描述和可能的选择器。",
        image_path="screenshots/login_page.png",
    )
    
    print(f"视觉定位结果:\n{response.content}")


async def example_phoenix_codegen():
    """凤凰涅槃层示例 - 代码生成"""
    manager = get_ai_manager()
    
    trace_data = {
        "steps": [
            {"action": "navigate", "url": "https://example.com/login"},
            {"action": "input", "selector": "#username", "value": "testuser"},
            {"action": "input", "selector": "#password", "value": "password123"},
            {"action": "click", "selector": "#login-btn"},
            {"action": "verify", "expected": "登录成功"},
        ]
    }
    
    response = await manager.invoke(
        module=AIModule.AGENT_NEURAL_API_EXPERT,
        messages=[
            Message(
                role="system",
                content="你是一个 Playwright 测试代码生成器，将执行轨迹转化为 Python 测试脚本。"
            ),
            Message(
                role="user",
                content=f"将以下执行轨迹转化为 Pytest + Playwright 测试脚本:\n{trace_data}"
            ),
        ],
    )
    
    print(f"生成的代码:\n{response.content}")


async def example_simple_chat():
    """简单对话示例"""
    manager = get_ai_manager()
    
    # 便捷方法，使用通用对话模块 (qwen-turbo)
    result = await manager.simple_chat(
        prompt="什么是 UI 自动化测试？简单介绍一下。",
        module=AIModule.GENERAL_CHAT,
    )
    
    print(f"回答: {result}")


async def example_stream():
    """流式输出示例"""
    manager = get_ai_manager()
    
    print("流式输出: ", end="", flush=True)
    
    async for chunk in manager.invoke_stream(
        module=AIModule.GENERAL_CHAT,
        messages=[
            Message(role="user", content="用三句话介绍 AI 测试自动化的优势")
        ],
    ):
        print(chunk, end="", flush=True)
    
    print()  # 换行


async def example_override_model():
    """模型覆盖示例"""
    manager = get_ai_manager()
    
    # 临时使用更高级的模型
    response = await manager.invoke(
        module=AIModule.GENERAL_CHAT,
        messages=[
            Message(role="user", content="复杂的问题...")
        ],
        model_override="qwen-max",  # 覆盖默认模型
        temperature=0.3,            # 降低随机性
    )
    
    print(f"使用覆盖模型的结果: {response.content}")


# ══════════════════════════════════════════════════════════════════════════════
# 在实际模块中的使用示例
# ══════════════════════════════════════════════════════════════════════════════

# 示例 1: 神经设计层 intent_parser.py
'''
from app.core.ai_client import get_ai_manager, Message, AIModule

class IntentParser:
    def __init__(self):
        self.ai = get_ai_manager()
    
    async def parse(self, user_input: str) -> dict:
        response = await self.ai.invoke(
            module=AIModule.AGENT_NEURAL_ADMIN,
            messages=[
                Message(role="system", content=INTENT_SYSTEM_PROMPT),
                Message(role="user", content=user_input),
            ],
        )
        return self._parse_response(response.content)
'''

# 示例 2: 右瞳引擎 vision_planner.py
'''
from app.core.ai_client import get_ai_manager, AIModule

class VisionPlanner:
    def __init__(self):
        self.ai = get_ai_manager()
    
    async def locate_element(self, screenshot_path: str, target: str) -> dict:
        response = await self.ai.invoke_vision(
            module=AIModule.AGENT_RIGHT_VISUAL,
            prompt=f"找到页面中的 '{target}'，返回坐标和选择器",
            image_path=screenshot_path,
        )
        return self._parse_location(response.content)
'''

# 示例 3: 缺陷分析 root_cause.py
'''
from app.core.ai_client import get_ai_manager, Message, AIModule

class RootCauseAnalyzer:
    def __init__(self):
        self.ai = get_ai_manager()
    
    async def analyze(self, error_log: str, screenshot: str) -> dict:
        response = await self.ai.invoke_vision(
            module=AIModule.AGENT_LEFT_SHERLOCK,
            prompt=f"分析以下错误的根因:\n{error_log}",
            image_path=screenshot,
        )
        return response.content
'''


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_simple_chat())
