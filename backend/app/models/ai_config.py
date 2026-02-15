
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, UniqueConstraint, DateTime
from sqlalchemy.sql import func
from app.models.base import Base

class AIModelConfig(Base):
    """
    AI 模型配置表
    
    存储每个功能模块 (module) 对应的 模型 (model_id) 和 提供商 (provider)。
    允许运行时动态修改，无需重启服务。
    """
    __tablename__ = "ai_model_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    module = Column(String, unique=True, index=True, nullable=False, comment="功能模块 (AIModule)")
    model_id = Column(String, nullable=False, comment="模型ID (e.g. qwen-max)")
    provider = Column(String, nullable=False, comment="提供商 (e.g. dashscope)")
    
    # Advanced Config (Override defaults)
    temperature = Column(Float, nullable=True, comment="温度")
    max_tokens = Column(Integer, nullable=True, comment="最大Token数")
    system_prompt = Column(Text, nullable=True, comment="自定义系统提示词")
    
    # Fallback Mechanism
    enable_fallback = Column(Boolean, default=True, comment="是否启用自动降级")
    fallback_model_id = Column(String, nullable=True, comment="降级模型ID (e.g. qwen-plus)")
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now())

class AIProviderConfig(Base):
    """
    AI 提供商配置表 (存储 API Key)
    """
    __tablename__ = "ai_provider_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, unique=True, index=True, nullable=False)
    api_key_ciphertext = Column(String, nullable=False, comment="加密的 API Key")
    base_url = Column(String, nullable=True, comment="自定义 Base URL")
    is_active = Column(Boolean, default=True)

class AICostLog(Base):
    """
    AI 成本日志表
    
    记录每次调用的消耗
    """
    __tablename__ = "ai_cost_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    module = Column(String, index=True, nullable=False)
    model_id = Column(String, index=True, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0, comment="预估成本 (USD/RMB)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
