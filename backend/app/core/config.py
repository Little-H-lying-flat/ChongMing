"""
重明配置管理

使用 Pydantic Settings 管理配置，支持环境变量覆盖
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict



import sys

class Settings(BaseSettings):
    """应用配置"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print(f"DEBUG: Config Loaded. DB={self.DATABASE_URL}, Broker={self.CELERY_BROKER_URL}", file=sys.stderr)

    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # === 基础配置 ===
    VERSION: str = "2.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_STR: str = "/api/v1"
    SERVER_HOST: str = "http://localhost:8000"
    
    # === Security ===
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "password"
    
    # === 数据库 ===
    # DATABASE_URL: str = "postgresql+asyncpg://postgres:chongming123@localhost:5432/chongming"
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    
    # === Redis ===
    # REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_URL: str = "redis://127.0.0.1:6379/0" # Keep for code that might rely on it, but we won't have it running
    
    # === Celery ===
    CELERY_BROKER_URL: str = "memory://"
    CELERY_RESULT_BACKEND: str = "db+sqlite:///./celery_results.db"
    CELERY_TASK_ALWAYS_EAGER: bool = True # Enable for local testing without Redis
    
    # === AI/LLM (阿里云 DashScope) ===
    QWEN_API_KEY: str = "sk-fecda1b83bfe4208892248adffc7cc38"
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # 模型配置 - 按功能模块分组
    # 神经设计层 (高智能任务)
    MODEL_NEURAL_INTENT: str = "qwen-max"
    MODEL_NEURAL_SCENARIO: str = "qwen-max"
    MODEL_NEURAL_CRITIC: str = "qwen-plus"
    
    # 右瞳引擎 (视觉任务)
    MODEL_RIGHT_PUPIL_PLANNER: str = "qwen-plus"
    MODEL_RIGHT_PUPIL_VL: str = "qwen-vl-plus"
    
    # 左瞳引擎 (API 推理)
    MODEL_LEFT_PUPIL_CHAIN: str = "qwen-plus"
    MODEL_LEFT_PUPIL_PARAM: str = "qwen-turbo"
    
    # 凤凰涅槃层 (代码生成)
    MODEL_PHOENIX_CODEGEN: str = "qwen-plus"
    
    # 缺陷分析 (推理任务)
    MODEL_DEFECT_ANALYSIS: str = "qwen-max"
    
    # 通用任务
    MODEL_GENERAL_CHAT: str = "qwen-turbo"
    MODEL_GENERAL_LONG: str = "qwen-long"
    MODEL_EMBEDDING: str = "text-embedding-v3"

    
    # === Milvus (Vector DB) ===
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: str = "19530"

    # === OmniParser ===
    OMNIPARSER_URL: str = "http://localhost:7861"
    MOCK_OMNIPARSER: bool = False
    
    # === Git Integration ===
    GIT_REPO_PATH: str = "./test_repo"
    GIT_USER_NAME: str = "ChongMing Bot"
    GIT_USER_EMAIL: str = "bot@chongming.ai"
    
    # === CORS ===
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # === 日志 ===
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    
    # === 测试资产存储 ===
    ASSET_DIR: str = "assets"
    SCREENSHOT_DIR: str = "screenshots"
    TRACE_DIR: str = "traces"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 导出配置实例
settings = get_settings()
