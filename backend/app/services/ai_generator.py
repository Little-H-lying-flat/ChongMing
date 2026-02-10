"""
AI 数据生成器

使用 LLM 生成语义真实的测试数据
对应 Issue: #DF-004
"""

import json
from typing import Any

from openai import AsyncOpenAI
from loguru import logger

from app.core.config import settings


class AIGenerator:
    """
    AI 数据生成器
    
    使用 Qwen API 生成符合业务语义的测试数据
    """
    
    # 生成模式
    MODE_REALISTIC = "realistic"      # 真实数据（符合业务逻辑）
    MODE_BOUNDARY = "boundary"        # 边界测试数据
    MODE_ADVERSARIAL = "adversarial"  # 对抗性测试数据
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        初始化 AI 生成器
        
        Args:
            api_key: Qwen API 密钥，默认从配置读取
            model: 使用的模型，默认 qwen-turbo
        """
        self.api_key = api_key or settings.QWEN_API_KEY
        self.model = model or settings.MODEL_GENERAL_CHAT
        self.base_url = settings.QWEN_BASE_URL
        
        self._client: AsyncOpenAI | None = None
    
    @property
    def client(self) -> AsyncOpenAI:
        """懒加载 OpenAI 客户端"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("未配置 QWEN_API_KEY，无法使用 AI 生成器")
            
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client
    
    async def generate(
        self,
        schema: dict[str, Any],
        count: int = 1,
        mode: str = MODE_REALISTIC,
        context: str | None = None,
    ) -> list[dict]:
        """
        使用 AI 生成数据
        
        Args:
            schema: 数据结构定义
            count: 生成数量
            mode: 生成模式 (realistic/boundary/adversarial)
            context: 业务上下文描述
            
        Returns:
            生成的数据列表
        """
        prompt = self._build_prompt(schema, count, mode, context)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # 提取数据数组
            if isinstance(result, list):
                return result[:count]
            elif isinstance(result, dict) and "data" in result:
                return result["data"][:count]
            elif isinstance(result, dict) and "items" in result:
                return result["items"][:count]
            else:
                return [result]
                
        except json.JSONDecodeError as e:
            logger.error(f"AI 生成的数据解析失败: {e}")
            raise ValueError(f"AI 生成的数据格式无效: {e}")
        except Exception as e:
            logger.error(f"AI 生成失败: {e}")
            raise
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的测试数据生成器。你的任务是根据给定的数据结构生成符合要求的测试数据。

规则:
1. 严格按照指定的 schema 结构生成数据
2. 生成的数据必须真实、合理、符合业务逻辑
3. 确保数据多样性，避免重复模式
4. 中文内容使用简体中文
5. 返回格式必须是有效的 JSON

输出格式:
{
  "data": [
    {"field1": "value1", "field2": "value2", ...},
    ...
  ]
}"""
    
    def _build_prompt(
        self,
        schema: dict[str, Any],
        count: int,
        mode: str,
        context: str | None,
    ) -> str:
        """构建用户提示词"""
        mode_instructions = {
            self.MODE_REALISTIC: "生成真实、符合业务逻辑的数据",
            self.MODE_BOUNDARY: "生成边界值测试数据（最大值、最小值、空值、特殊字符等）",
            self.MODE_ADVERSARIAL: "生成对抗性测试数据（SQL注入、XSS、超长字符串等）",
        }
        
        prompt_parts = [
            f"请根据以下数据结构生成 {count} 条测试数据。",
            f"\n数据结构:\n```json\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n```",
            f"\n生成模式: {mode_instructions.get(mode, mode_instructions[self.MODE_REALISTIC])}",
        ]
        
        if context:
            prompt_parts.append(f"\n业务背景: {context}")
        
        return "\n".join(prompt_parts)
    
    async def generate_from_description(
        self,
        description: str,
        count: int = 5,
    ) -> dict:
        """
        根据自然语言描述推断 schema 并生成数据
        
        Args:
            description: 数据描述（如 "用户注册信息"、"订单数据"）
            count: 生成数量
            
        Returns:
            包含 schema 和 data 的字典
        """
        infer_prompt = f"""根据以下描述，推断出合适的数据结构（JSON Schema 格式）并生成 {count} 条测试数据。

描述: {description}

请返回以下格式的 JSON:
{{
  "schema": {{
    "字段名1": "类型描述",
    "字段名2": "类型描述",
    ...
  }},
  "data": [
    {{"字段名1": "值1", "字段名2": "值2", ...}},
    ...
  ]
}}"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个测试数据生成专家。根据用户描述，推断数据结构并生成测试数据。",
                    },
                    {
                        "role": "user",
                        "content": infer_prompt,
                    },
                ],
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"AI 推断生成失败: {e}")
            raise


# 全局实例
ai_generator = AIGenerator()
