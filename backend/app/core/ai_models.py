"""
AI 模型配置

定义不同功能模块使用的 AI 模型
支持后期灵活切换和扩展
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ModelProvider(str, Enum):
    """大模型提供商"""
    DASHSCOPE = "dashscope"  # 阿里云百炼
    OPENAI = "openai"        # OpenAI (备用)AI Provider
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
    "qwen-turbo": ModelConfig(
        model_id="qwen-turbo",
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.TEXT,
        max_tokens=8192,
        temperature=0.7,
        description="通义千问 Turbo - 快速响应",
        cost_per_1k_tokens=0.002,
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
    # User specifically asked for this ID
    "qwen3.5-plus": ModelConfig( 
        model_id="qwen3.5-plus", 
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.VISION, # Ensure this handles VL natively
        max_tokens=8192,
        description="Qwen3.5 Plus - 原生视觉语言系列，混合架构，深度思考",
        describe="Qwen3.5原生视觉语言系列Plus模型，基于混合架构设计，融合了线性注意力机制与稀疏混合专家模型，实现了更高的推理效率。在多项任务评测中，3.5系列均展现出与当前顶尖前沿模型相媲美的卓越性能，模型效果在纯文本与多模态方面相较3系列均实现飞跃式进步。(qwen3.5-plus-2026-02-15)",
        cost_per_1k_tokens=0.004, 
    ),
    "qwen3.5-flash": ModelConfig( 
        model_id="qwen3.5-flash", 
        provider=ModelProvider.DASHSCOPE,
        capability=ModelCapability.VISION, # Ensure this handles VL natively for fast mode
        max_tokens=8192,
        description="Qwen3.5 Flash - 原生视觉语言系列，极速多模态",
        cost_per_1k_tokens=0.001, 
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
    
    # === 通用 ===
    GENERAL_CHAT = "general.chat"                       # 通用对话
    GENERAL_SUMMARY = "general.summary"                 # 文档摘要
    RAG_EMBEDDING = "rag.embedding"                     # RAG 向量化
    
    # === 角色智能体挂载点 (Agent Mount Points) ===
    # 1. Neural Design
    AGENT_NEURAL_ADMIN = "agent.neural.admin"
    AGENT_NEURAL_FINDER = "agent.neural.finder"
    AGENT_NEURAL_UI_EXPERT = "agent.neural.ui_expert"
    AGENT_NEURAL_API_EXPERT = "agent.neural.api_expert"
    AGENT_NEURAL_MERGER = "agent.neural.merger"
    
    # 2. Left Pupil (API Flow)
    AGENT_LEFT_SHERLOCK = "agent.left.sherlock"
    AGENT_LEFT_HEALER = "agent.left.healer"
    AGENT_LEFT_PERSONA = "agent.left.persona"
    AGENT_LEFT_RED_TEAMER = "agent.left.red_teamer"
    AGENT_LEFT_JANITOR = "agent.left.janitor"
    
    # 3. Right Pupil (UI Flow)
    AGENT_RIGHT_VISUAL = "agent.right.visual"
    AGENT_RIGHT_PERSONA = "agent.right.persona"
    AGENT_RIGHT_CRITIC = "agent.right.critic"
    AGENT_RIGHT_SHERLOCK = "agent.right.sherlock"
    AGENT_RIGHT_HEALER = "agent.right.healer"


# 默认模型映射配置
DEFAULT_MODEL_MAPPING = {
    
    # === 通用 ===
    AIModule.GENERAL_CHAT: "qwen-turbo",
    AIModule.GENERAL_SUMMARY: "qwen-turbo",
    AIModule.RAG_EMBEDDING: "text-embedding-v3",
    
    # === 角色智能体挂载点默认映射 ===
    # 1. Neural Design (推理为主，qwen3.5-flash 性价比最高)
    AIModule.AGENT_NEURAL_ADMIN: "qwen3.5-flash",
    AIModule.AGENT_NEURAL_FINDER: "qwen3.5-flash",
    AIModule.AGENT_NEURAL_UI_EXPERT: "qwen3.5-flash",
    AIModule.AGENT_NEURAL_API_EXPERT: "qwen3.5-flash",
    AIModule.AGENT_NEURAL_MERGER: "qwen3.5-flash",
    
    # 2. Left Pupil (API Flow - 分析代码和结构，需强推理)
    AIModule.AGENT_LEFT_SHERLOCK: "qwen3.5-plus",  # 根因分析需更强能力
    AIModule.AGENT_LEFT_HEALER: "qwen3.5-plus",    # 载荷自愈需更强能力
    AIModule.AGENT_LEFT_PERSONA: "qwen3.5-flash",
    AIModule.AGENT_LEFT_RED_TEAMER: "qwen3.5-plus",
    AIModule.AGENT_LEFT_JANITOR: "qwen3.5-flash",
    
    # 3. Right Pupil (UI Flow - 强视觉依赖)
    AIModule.AGENT_RIGHT_VISUAL: "qwen3.5-plus",   # 必须 Vision 能力
    AIModule.AGENT_RIGHT_PERSONA: "qwen3.5-flash",
    AIModule.AGENT_RIGHT_CRITIC: "qwen3.5-flash",
    AIModule.AGENT_RIGHT_SHERLOCK: "qwen3.5-plus", # 也可以给文字版
    AIModule.AGENT_RIGHT_HEALER: "qwen3.5-plus",   # UI 自愈需较强能力
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
    # Priority: 1. Override arg, 2. AI_MODELS Default Mapping (Code Config), 3. External Config
    # User Request: Prioritize ai_models.py config
    if override:
        model_id = override
    elif module in DEFAULT_MODEL_MAPPING:
        model_id = DEFAULT_MODEL_MAPPING[module]
    else:
        # Fallback to config only if not defined in code mapping
        try:
            from app.core.config import settings
            config_mapping = {
                AIModule.AGENT_NEURAL_MERGER: settings.MODEL_NEURAL_SCENARIO,
                
                AIModule.AGENT_RIGHT_VISUAL: settings.MODEL_RIGHT_PUPIL_VL,
                AIModule.AGENT_LEFT_SHERLOCK: settings.MODEL_LEFT_PUPIL_CHAIN,
                AIModule.AGENT_NEURAL_API_EXPERT: settings.MODEL_PHOENIX_CODEGEN,
                
                AIModule.GENERAL_CHAT: settings.MODEL_GENERAL_CHAT,
                AIModule.GENERAL_SUMMARY: settings.MODEL_GENERAL_LONG,
                AIModule.RAG_EMBEDDING: settings.MODEL_EMBEDDING,
            }
            model_id = config_mapping.get(module)
        except ImportError:
            model_id = None
            
    if not model_id:
        model_id = "qwen-plus" # Absolute fallback
    
    if model_id not in AVAILABLE_MODELS:
        # Fallback to a known safe model if configured model is missing (e.g. typo in config)
        if "qwen-plus" in AVAILABLE_MODELS:
            return AVAILABLE_MODELS["qwen-plus"]
        raise ValueError(f"未知模型: {model_id}")
    
    return AVAILABLE_MODELS[model_id]
