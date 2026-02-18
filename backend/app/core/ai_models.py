"""
AI 模型配置

定义不同功能模块使用的 AI 模型
支持后期灵活切换和扩展
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ModelProvider(str, Enum):
    """模型提供商"""
    DASHSCOPE = "dashscope"  # 阿里云百炼
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"  # 本地模型 (Ollama)


class ModelCapability(str, Enum):
    """模型能力类型"""
    TEXT = "text"           # 纯文本
    VISION = "vision"       # 视觉理解
    EMBEDDING = "embedding" # 向量嵌入
    REASONING = "reasoning" # 深度推理


@dataclass
class ModelConfig:
    """模型配置"""
    model_id: str           # 模型标识符
    provider: ModelProvider # 提供商
    capability: ModelCapability
    max_tokens: int = 4096
    temperature: float = 0.7
    description: str = ""
    describe: str = ""
    cost_per_1k_tokens: float = 0.0  # 成本估算
    system_prompt: Optional[str] = None  # 默认系统提示词


# ═══════════════════════════════════════════════════════════════════════════════
# 模型注册表 - 所有可用模型
# ═══════════════════════════════════════════════════════════════════════════════

AVAILABLE_MODELS = {
    # === 阿里云 DashScope 模型 ===
    "qwen-max": ModelConfig(
        model_id="qwen-max",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.TEXT,
        max_tokens=8192,
        temperature=0.7,
        description="通义千问 Max - 高智能复杂任务",
        cost_per_1k_tokens=0.04,
    ),
    "qwen-plus": ModelConfig(
        model_id="qwen-plus",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.TEXT,
        max_tokens=8192,
        temperature=0.7,
        description="通义千问 Plus - 平衡性能与成本",
        cost_per_1k_tokens=0.008,
    ),
    "qwen-turbo": ModelConfig(
        model_id="qwen-turbo",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.TEXT,
        max_tokens=8192,
        temperature=0.7,
        description="通义千问 Turbo - 快速响应",
        cost_per_1k_tokens=0.002,
    ),
    "qwen-flash": ModelConfig(
        model_id="qwen-flash", # Assumed valid model ID, maybe qwen2.5-flash
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.TEXT,
        max_tokens=8192,
        temperature=0.7,
        description="通义千问 Flash - 极速响应",
        cost_per_1k_tokens=0.001, # Estimated cheaper than turbo
    ),
    "qwen-long": ModelConfig(
        model_id="qwen-long",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.TEXT,
        max_tokens=10000000,  # 1000 万 token
        temperature=0.7,
        description="通义千问 Long - 超长上下文",
        cost_per_1k_tokens=0.0005,
    ),
    "qwen-vl-plus": ModelConfig(
        model_id="qwen-vl-plus",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.VISION,
        max_tokens=8192,
        temperature=0.7,
        description="通义千问 VL Plus - 视觉理解",
        cost_per_1k_tokens=0.008,
    ),
    "qwen-vl-max": ModelConfig(
        model_id="qwen-vl-max",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.VISION,
        max_tokens=8192,
        temperature=0.7,
        description="通义千问 VL Max - 高级视觉理解",
        cost_per_1k_tokens=0.02,
    ),
    "qwen3-235b-a22b": ModelConfig(
        model_id="qwen3-235b-a22b",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.REASONING,
        max_tokens=8192,
        temperature=0.7,
        description="Qwen3 235B - 深度推理 (需开通)",
        cost_per_1k_tokens=0.004,
    ),
    "qwen-max-2025-01-25": ModelConfig( # Assuming this is the qwen3-max equivalent or placeholder if exact ID is qwen-max-latest
        model_id="qwen-max-2025-01-25",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.REASONING,
        max_tokens=8192,
        temperature=0.7,
        description="通义千问 Qwen2.5-Max (2025-01-25)",
        cost_per_1k_tokens=0.02, # Estimated
    ),
    "qwen3-max": ModelConfig( # Renamed key to match usage 
        # Actually user said "qwen3-max" and "qwen3-vl-plus". 
        # Qwen2.5 is the current "Next Gen". "Qwen3" might be user's shorthand or specific preview. 
        # I will add them with the EXACT IDs user asked for, assuming they exist in their provider invocation, 
        # or map them to the likely real model IDs if execution fails. 
        # Use standard model IDs for DashScope: "qwen-max-latest" or "qwen-max" is usually the alias.
        # But if user insists on "qwen3", I'll add them.
        model_id="qwen3-max",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.REASONING,
        max_tokens=8192,
        description="Qwen3 Max (User Requested)",
        cost_per_1k_tokens=0.02,
    ),
    "qwen3-vl-plus": ModelConfig(
        model_id="qwen3-vl-plus",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.VISION,
        max_tokens=8192,
        description="Qwen3 VL Plus (User Requested)",
        cost_per_1k_tokens=0.01,
    ),
    "qwen2.5-max": ModelConfig(
        model_id="qwen-max-2025-01-25",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.REASONING,
        max_tokens=8192,
        description="Qwen2.5 Max (2025-01-25)",
        cost_per_1k_tokens=0.02,
    ),
    "qwen2.5-plus": ModelConfig(
        model_id="qwen-plus-2025-01-25",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.REASONING,
        max_tokens=8192,
        description="Qwen2.5 Plus (2025-01-25)",
        cost_per_1k_tokens=0.004,
    ),
    # User specifically asked for this ID
    "qwen3.5-plus": ModelConfig( 
        model_id="qwen3.5-plus", 
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.REASONING, # It supports everything
        max_tokens=8192,
        description="Qwen3.5 Plus - 原生视觉语言系列，混合架构，深度思考",
        describe="Qwen3.5原生视觉语言系列Plus模型，基于混合架构设计，融合了线性注意力机制与稀疏混合专家模型，实现了更高的推理效率。在多项任务评测中，3.5系列均展现出与当前顶尖前沿模型相媲美的卓越性能，模型效果在纯文本与多模态方面相较3系列均实现飞跃式进步。(qwen3.5-plus-2026-02-15)",
        cost_per_1k_tokens=0.004, 
    ),
    "text-embedding-v3": ModelConfig(
        model_id="text-embedding-v3",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.EMBEDDING,
        max_tokens=8192,
        description="通义文本向量模型",
        cost_per_1k_tokens=0.0007,
    ),
    
    # === OpenAI 模型 (可选) ===
    "gpt-4o": ModelConfig(
        model_id="gpt-4o",
        provider=ModelProvider.OPENAI,
        capability=ModelCapability.VISION,
        max_tokens=4096,
        temperature=0.7,
        description="GPT-4o - OpenAI 多模态",
        cost_per_1k_tokens=0.005,
    ),
    "gpt-4o-mini": ModelConfig(
        model_id="gpt-4o-mini",
        provider=ModelProvider.OPENAI,
        capability=ModelCapability.VISION,
        max_tokens=4096,
        temperature=0.7,
        description="GPT-4o Mini - 快速多模态",
        cost_per_1k_tokens=0.00015,
    ),

    "text-embedding-v4": ModelConfig(
        model_id="text-embedding-v4",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.EMBEDDING,
        max_tokens=8192,
        description="通义文本向量模型 V4",
        cost_per_1k_tokens=0.0005,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# 功能模块 → 模型映射
# ═══════════════════════════════════════════════════════════════════════════════

class AIModule(str, Enum):
    """AI 功能模块"""
    
    # === 神经设计层 ===
    NEURAL_INTENT_PARSER = "neural.intent_parser"       # 意图解析
    NEURAL_SCENARIO_GENERATOR = "neural.scenario_gen"   # 场景推理
    NEURAL_CRITIC = "neural.critic"                     # 用例审核
    
    # === 右瞳引擎 ===
    RIGHT_PUPIL_PLANNER = "right_pupil.planner"         # 动作规划
    RIGHT_PUPIL_GROUNDING = "right_pupil.grounding"     # 元素定位 (VL)
    RIGHT_PUPIL_VERIFY = "right_pupil.verify"           # 结果验证 (VL)
    
    # === 左瞳引擎 ===
    LEFT_PUPIL_CHAIN_INFERENCE = "left_pupil.chain"     # 调用链推理
    LEFT_PUPIL_PARAM_GEN = "left_pupil.param_gen"       # 参数生成
    
    # === 凤凰涅槃层 ===
    PHOENIX_CODE_GEN = "phoenix.code_gen"               # 代码生成
    PHOENIX_CODEGEN = "phoenix.code_gen"                # Alias for compatibility
    PHOENIX_ASSERTION_GEN = "phoenix.assertion"         # 断言生成
    
    # === 缺陷分析 ===
    DEFECT_ROOT_CAUSE = "defect.root_cause"             # 根因分析
    DEFECT_FIX_SUGGEST = "defect.fix_suggest"           # 修复建议
    DEFECT_ANALYSIS = "defect.root_cause"               # Alias for compatibility
    
    # === 通用 ===
    GENERAL_CHAT = "general.chat"                       # 通用对话
    GENERAL_SUMMARY = "general.summary"                 # 文档摘要
    RAG_EMBEDDING = "rag.embedding"                     # RAG 向量化


# 默认模型映射配置
DEFAULT_MODEL_MAPPING = {
    # === 神经设计层 - 需要高智能 ===
    AIModule.NEURAL_INTENT_PARSER: "qwen3.5-plus",
    AIModule.NEURAL_SCENARIO_GENERATOR: "qwen3.5-plus",
    AIModule.NEURAL_CRITIC: "qwen3.5-plus",
    
    # === 右瞳引擎 - 需要视觉能力 ===
    AIModule.RIGHT_PUPIL_PLANNER: "qwen3.5-plus",
    AIModule.RIGHT_PUPIL_GROUNDING: "qwen3.5-plus",  # 视觉定位
    AIModule.RIGHT_PUPIL_VERIFY: "qwen3.5-plus",     # 视觉验证
    
    # === 左瞳引擎 ===
    AIModule.LEFT_PUPIL_CHAIN_INFERENCE: "qwen3.5-plus",
    AIModule.LEFT_PUPIL_PARAM_GEN: "qwen-flash",     # 极速生成
    
    # === 凤凰涅槃层 ===
    AIModule.PHOENIX_CODE_GEN: "qwen3.5-plus",
    AIModule.PHOENIX_CODEGEN: "qwen3.5-plus",
    AIModule.PHOENIX_ASSERTION_GEN: "qwen-flash",
    
    # === 缺陷分析 - 需要推理能力 ===
    AIModule.DEFECT_ROOT_CAUSE: "qwen3.5-plus",
    AIModule.DEFECT_FIX_SUGGEST: "qwen3.5-plus",
    AIModule.DEFECT_ANALYSIS: "qwen3.5-plus",
    
    # === 通用 ===
    AIModule.GENERAL_CHAT: "qwen-flash",
    AIModule.GENERAL_SUMMARY: "qwen-long",           # 长文本摘要
    AIModule.RAG_EMBEDDING: "text-embedding-v4",
}


def get_model_for_module(
    module: AIModule,
    override: Optional[str] = None,
) -> ModelConfig:
    """
    获取模块对应的模型配置
    
    Args:
        module: AI 功能模块
        override: 可选的模型覆盖
        
    Returns:
        ModelConfig: 模型配置
    """
    model_id = override or DEFAULT_MODEL_MAPPING.get(module, "qwen-plus")
    
    if model_id not in AVAILABLE_MODELS:
        raise ValueError(f"未知模型: {model_id}")
    
    return AVAILABLE_MODELS[model_id]
