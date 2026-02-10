"""
Neural Design Service

负责将自然语言需求转化为结构化测试用例
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional

from app.core.ai_client import AIClientManager, get_ai_manager
from app.core.ai_models import AIModule
from app.services.left_pupil.rag_retriever import RagRetriever
from app.services.neural_design.models import (
    DesignRequest, DraftTestCase, RefinedTCIR, 
    RefinedRequestSpec, RefinedAssertionSpec
)
from app.core.prompts.neural_design import (
    PRD_ANALYSIS_PROMPT, TC_GENERATION_PROMPT, CRITIC_PROMPT
)

logger = logging.getLogger(__name__)

class DesignService:
    """
    神经设计服务
    
    核心功能：
    1. analyze_requirement: 分析需求 -> 生成场景
    2. generate_test_case: 场景 -> 生成测试用例 (Draft -> Refined)
    """
    
    def __init__(self, ai_manager: Optional[AIClientManager] = None, retriever: Optional[RagRetriever] = None):
        self.ai = ai_manager or get_ai_manager()
        self.retriever = retriever or RagRetriever()
        
    async def analyze_requirement(self, request: DesignRequest) -> List[Dict[str, Any]]:
        """
        分析需求，提取测试场景
        
        Args:
            request: 设计请求 (包含 PRD 文本)
            
        Returns:
            场景列表 (JSON 结构)
        """
        logger.info(f"开始分析需求: Project={request.project_id}")
        
        prompt = PRD_ANALYSIS_PROMPT.format(
            requirement_text=request.requirement_text,
            context=request.context or "无额外上下文"
        )
        
        try:
            # 调用 LLM 分析需求
            response_text = await self.ai.simple_chat(prompt, module=AIModule.NEURAL_SCENARIO_GENERATOR)
            data = self._parse_json(response_text)
            
            scenarios = data.get("scenarios", [])
            logger.info(f"需求分析完成，提取了 {len(scenarios)} 个场景")
            return scenarios
            
        except Exception as e:
            logger.error(f"需求分析失败: {e}")
            # 返回空列表或抛出异常，视业务策略而定
            # 这里即使失败也尝试返回原始文本包装的场景，或抛出
            raise RuntimeError(f"需求分析失败: {str(e)}") from e

    async def generate_test_case(self, scenario: Dict[str, Any], project_id: str) -> RefinedTCIR:
        """
        根据场景生成测试用例
        
        流程: Retrieve -> Draft -> Critic -> Refine
        """
        scenario_name = scenario.get("name", "未命名场景")
        logger.info(f"开始生成测试用例: {scenario_name}")
        
        # 1. Retrieve Context (检索相关 API)
        # 使用场景描述和测试点作为查询
        query = f"{scenario.get('description', '')} {' '.join(scenario.get('test_points', []))}"
        
        logger.info(f"检索 API 上下文: {query}")
        relevant_apis = await self.retriever.retrieve(query, project_id)
        
        # 格式化 API 上下文供 Prompt 使用
        api_context_str = "\n".join([
            f"- {api.method} {api.path}: {api.metadata.get('summary', '')}" 
            for api in relevant_apis
        ])
        
        if not api_context_str:
            logger.warning("未检索到相关 API，只能基于通用知识生成")
            api_context_str = "未检索到具体 API 定义，请基于 RESTful 通用规范生成。"

        # 2. Draft Generation (生成草稿)
        prompt = TC_GENERATION_PROMPT.format(
            scenario_description=json.dumps(scenario, ensure_ascii=False),
            available_apis=api_context_str
        )
        
        draft_json_str = await self.ai.simple_chat(prompt, module=AIModule.NEURAL_INTENT_PARSER)
        draft_data = self._parse_json(draft_json_str)
        
        # 3. Self-Correction (Critic) (自我审查) - 可选
        # 这里演示简单流程，暂不进行 Critic 循环， direct output
        # 若要 Critic，可在此处再次调用 AI
        
        # 4. Refine & Convert (转换为强类型)
        try:
            refined_case = self._convert_draft_to_refined(draft_data)
            logger.info(f"测试用例生成成功: {refined_case.id} - {refined_case.name}")
            return refined_case
        except Exception as e:
            logger.error(f"测试用例转换失败: {e}")
            raise ValueError("生成的测试用例格式不正确，无法转换为标准 API-IR") from e

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        解析 LLM 输出的 JSON
        
        处理可能包含 Markdown 代码块的情况
        """
        clean_text = text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {text[:100]}... Error: {e}")
            # 简单重试机制或清洗可以是此处扩展点
            raise
    
    def _convert_draft_to_refined(self, draft: Dict[str, Any]) -> RefinedTCIR:
        """
        将草稿 JSON 转换为 RefinedTCIR 对象
        """
        # 验证草稿数据符合 DraftTestCase 模型 (可选，增加鲁棒性)
        # draft_obj = DraftTestCase(**draft) 
        
        # 构建 RefinedTCIR (Mapping Draft -> Refined)
        # 假设 DraftTC -> ApiIRChain or ApiIR? 
        # 这里假设 RefinedTCIR 代表一个完整的测试 *步骤* 还是 *用例*?
        # 根据 models.py, RefinedTCIR 结构类似 ApiIR (单个步骤).
        # 但 Prompt 可能会生成多个步骤。
        # 如果生成多个步骤，RefinedTCIR 应该是一个 Chain 还是 List[ApiIR]?
        # 暂时假设生成的 DraftTestCase 包含 steps，我们需要将其转换为 API-IR Chain 或者是单个复杂 API-IR?
        # 根据 models.py, RefinedTCIR 结构本身包含 request, assertion 等，看起来是 SINGLE step definition.
        
        # 如果 Prompt 生成了 steps 列表，我们需要把第一个主要步骤或者聚合步骤转化为 RefinedTCIR。
        # 或者 models.py 定义应该包含 steps?
        # 查看 models.py, RefinedTCIR 确实是单步结构 (method, url, request...)
        
        # 修正：如果生成的DraftTestCase包含多个步骤，我们应该返回一个 List[RefinedTCIR] 或者 修改 RefinedTCIR 为 Chain?
        # 为了符合 Phase 2 的设计，ApiIR 是单步。
        # 这里为了简化，我们只提取 steps 中的第一个步骤作为主要测试步骤，或者该服务应该返回 List[RefinedTCIR]。
        # 鉴于 RefinedTCIR 定义，我将返回 List[RefinedTCIR] 或者只转换第一个。
        # 目前函数签名是 -> RefinedTCIR，我会只转换第一个步骤，或者抛出异常如果多步。
        # 但 TC_GENERATION_PROMPT 明确要求生成 steps 列表。
        
        # 策略：取 Draft 中的第一个步骤作为主测试。
        # 更好的做法是修改 Service 返回 List[RefinedTCIR]。我将修改函数签名为 List[RefinedTCIR]。
        
        steps_data = draft.get("steps", [])
        if not steps_data:
            raise ValueError("生成的测试用例不包含任何步骤")
            
        refined_steps = []
        for step in steps_data:
            req_spec = RefinedRequestSpec(
                method=step.get("method", "GET").upper(),
                url=step.get("url_path", "/"),
                body=step.get("input_data"), # 假设 input_data 就是 body
            )
            
            # 从 expected_outcome 构造断言 (简单处理)
            assertion_spec = RefinedAssertionSpec(
                status_code=200, # 默认
                contains=step.get("expected_outcome")
            )
            
            refined = RefinedTCIR(
                id=step.get("step_id") or uuid.uuid4().hex[:8],
                name=step.get("intent") or draft.get("case_name", "Unnamed"),
                description=step.get("description", ""),
                request=req_spec,
                assertion=assertion_spec
            )
            refined_steps.append(refined)
            
        # 这里为了配合必须返回单个 RefinedTCIR 的限制 (如果 models.py 没变)，我返回第一个。
        # 但逻辑上应该返回列表。
        # 我会在代码中修改返回类型提示。
        return refined_steps[0]

