"""
Neural Design Service

负责将自然语言需求转化为结构化测试用例
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional

from app.core.ai_client import AIClientManager, get_ai_manager, Message
from app.core.ai_models import AIModule
from app.services.left_pupil.rag_retriever import RagRetriever
from app.services.left_pupil.knowledge_retriever import KnowledgeRetriever
from app.services.neural_design.models import (
    DesignRequest, DraftTestCase, RefinedTestCase, RefinedTestStep,
    RefinedRequestSpec, RefinedAssertionSpec
)
from app.core.prompts.neural_design import (
    PRD_ANALYSIS_SYSTEM_PROMPT, PRD_ANALYSIS_USER_TEMPLATE,
    TC_GENERATION_SYSTEM_PROMPT, TC_GENERATION_USER_TEMPLATE,
    CRITIC_SYSTEM_PROMPT, CRITIC_USER_TEMPLATE
)
from app.utils.json_repair import repair_json

logger = logging.getLogger(__name__)

class DesignService:
    """
    神经设计服务
    
    核心功能：
    1. analyze_requirement: 分析需求 -> 生成场景
    2. generate_test_case: 场景 -> 生成测试用例 (Draft -> Refined)
    """
    
    def __init__(self, ai_manager: Optional[AIClientManager] = None, retriever: Optional[RagRetriever] = None, knowledge_retriever: Optional[KnowledgeRetriever] = None):
        self.ai = ai_manager or get_ai_manager()
        self.retriever = retriever or RagRetriever()
        self.knowledge_retriever = knowledge_retriever or KnowledgeRetriever()
        
    async def analyze_requirement(self, request: DesignRequest) -> List[Dict[str, Any]]:
        """
        分析需求，提取测试场景
        
        Args:
            request: 设计请求 (包含 PRD 文本)
            
        Returns:
            场景列表 (JSON 结构)
        """
        logger.info(f"开始分析需求: Project={request.project_id}")
        
        # 使用 System/User Role 分离防止 Prompt Injection
        user_content = PRD_ANALYSIS_USER_TEMPLATE.format(
            requirement_text=request.requirement_text,
            context=request.context or "无额外上下文"
        )
        
        messages = [
            Message(role="system", content=PRD_ANALYSIS_SYSTEM_PROMPT),
            Message(role="user", content=user_content)
        ]
        
        try:
            # 调用 LLM 分析需求 (使用 invoke 以支持 Message 对象)
            response = await self.ai.invoke(
                module=AIModule.NEURAL_SCENARIO_GENERATOR,
                messages=messages
            )
            data = self._parse_json(response.content)
            
            scenarios = data.get("scenarios", [])
            logger.info(f"需求分析完成，提取了 {len(scenarios)} 个场景")
            return scenarios
            
        except Exception as e:
            logger.error(f"需求分析失败: {e}")
            raise RuntimeError(f"需求分析失败: {str(e)}") from e

    async def generate_test_case(self, scenario: Dict[str, Any], project_id: str) -> RefinedTestCase:
        """
        根据场景生成测试用例
        
        流程: Retrieve -> Draft (Retry) -> Critic -> Refine
        """
        scenario_name = scenario.get("name", "未命名场景")
        logger.info(f"开始生成测试用例: {scenario_name}")
        
        # 1. Retrieve Context
        query = f"{scenario.get('description', '')} {' '.join(scenario.get('test_points', []))}"
        relevant_apis = await self.retriever.retrieve(query, project_id)
        
        api_context_str = "\n".join([
            f"- {api.method} {api.path}: {api.metadata.get('summary', '')}" 
            for api in relevant_apis
        ])
        if not api_context_str:
            api_context_str = "未检索到具体 API 定义，请基于 RESTful 通用规范生成。"

        # 2. Retrieve Knowledge (Business Rules / Domain Context)
        knowledge_context = await self.knowledge_retriever.retrieve(query, project_id)
        knowledge_str = "\n".join([f"- {k.content}" for k in knowledge_context])
        if not knowledge_str:
            knowledge_str = "无额外业务规则知识。"

        # 3. Draft Generation with Semantic Retry
        user_content = TC_GENERATION_USER_TEMPLATE.format(
            scenario_description=json.dumps(scenario, ensure_ascii=False),
            available_apis=api_context_str,
            domain_knowledge=knowledge_str
        )
        
        messages = [
            Message(role="system", content=TC_GENERATION_SYSTEM_PROMPT),
            Message(role="user", content=user_content)
        ]
        
        draft_data = await self._invoke_with_retry(messages, AIModule.NEURAL_INTENT_PARSER)
        
        # 3. Self-Correction (Critic)
        try:
            critic_user_content = CRITIC_USER_TEMPLATE.format(
                draft_test_case=json.dumps(draft_data, ensure_ascii=False, indent=2)
            )
            critic_messages = [
                Message(role="system", content=CRITIC_SYSTEM_PROMPT),
                Message(role="user", content=critic_user_content)
            ]
            
            logger.info("执行 Critic 自我审查...")
            critic_response = await self.ai.invoke(
                module=AIModule.NEURAL_INTENT_PARSER, # or CRITIC module
                messages=critic_messages
            )
            
            # 尝试解析 Critic 的输出
            try:
                critic_data = self._parse_json(critic_response.content)
                # 验证是否为有效测试用例
                if "steps" in critic_data and isinstance(critic_data["steps"], list):
                    logger.info("Critic 提供了修正后的测试用例，采纳修正。")
                    draft_data = critic_data
                else:
                     logger.info("Critic 输出有效JSON但非测试用例结构，保持原样。")
            except Exception:
                logger.debug("Critic 未返回 JSON，忽略修正建议。")

        except Exception as e:
            logger.warning(f"Critic 步骤执行失败，回退到原始草稿: {e}")
        
        # 4. Refine & Convert
        try:
            refined_case = self._convert_draft_to_refined(draft_data)
            logger.info(f"测试用例生成成功: {refined_case.id} - {refined_case.name}")
            return refined_case
        except Exception as e:
            logger.error(f"测试用例转换失败: {e}")
            logger.error(f"Draft Data: {json.dumps(draft_data, ensure_ascii=False)}")
            raise ValueError("生成的测试用例格式不正确，无法转换为标准 API-IR") from e

    async def _invoke_with_retry(self, messages: List[Message], module: AIModule, max_retries: int = 2) -> Dict[str, Any]:
        """
        带语义重试的 LLM 调用
        """
        current_messages = messages.copy()
        
        for attempt in range(max_retries + 1):
            try:
                response = await self.ai.invoke(module, current_messages)
                return self._parse_json(response.content)
            except ValueError as e:
                # JSON 解析错误
                logger.warning(f"JSON 解析失败 (尝试 {attempt+1}/{max_retries+1}): {e}")
                if attempt < max_retries:
                    # 将错误反馈给 LLM
                    current_messages.append(Message(role="assistant", content=response.content))
                    current_messages.append(Message(role="user", content=f"JSON Parse Error: {str(e)}. Please fix the JSON and output ONLY the JSON object."))
                else:
                    raise
            except Exception as e:
                # 其他错误 (网络等已经在 Client 层重试，这里处理逻辑错误)
                logger.error(f"LLM 调用严重错误: {e}")
                raise

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        解析 LLM 输出的 JSON (Robust)
        """
        try:
            return repair_json(text)
        except Exception as e:
            logger.error(f"JSON 解析最终失败: {text[:100]}...")
            raise ValueError(f"Invalid JSON: {str(e)}") from e
    
    def _convert_draft_to_refined(self, draft: Dict[str, Any]) -> RefinedTestCase:
        """
        将草稿 JSON 转换为 RefinedTestCase 对象
        """
        steps_data = draft.get("steps", [])
        if not steps_data:
            raise ValueError("生成的测试用例不包含任何步骤")
            
        refined_steps = []
        for step in steps_data:
            req_spec = RefinedRequestSpec(
                method=step.get("method", "GET").upper(),
                url=step.get("url_path", "/"),
                body=step.get("input_data"),
            )
            
            expected_outcome = step.get("expected_outcome")
            if isinstance(expected_outcome, (dict, list)):
                expected_outcome = json.dumps(expected_outcome, ensure_ascii=False)
            elif expected_outcome is None:
                expected_outcome = ""
            else:
                expected_outcome = str(expected_outcome)

            assertion_spec = RefinedAssertionSpec(
                status_code=200, 
                contains=expected_outcome
            )
            
            refined_step = RefinedTestStep(
                id=step.get("step_id") or uuid.uuid4().hex[:8],
                name=step.get("intent") or "Step",
                description=step.get("description", ""),
                request=req_spec,
                assertion=assertion_spec
            )
            refined_steps.append(refined_step)
            
        return RefinedTestCase(
            id=uuid.uuid4().hex[:8],
            name=draft.get("case_name", "Generated Case"),
            description=draft.get("description", ""),
            steps=refined_steps,
            metadata={"origin": "neural_design"} 
        )

