"""Application settings management."""

from functools import lru_cache
from typing import List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime environment
    APP_ENV: Literal["dev", "staging", "prod"] = "dev"

    # Core
    MODEL_CUSTOM_GEMINI: str = "gemini-3-pro-high"
    PROJECT_NAME: str = "ChongMing API"
    VERSION: str = "0.1.1"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_STR: str = "/api/v1"
    SERVER_HOST: str = "http://localhost:8000"

    # Security
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "password"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"

    # Redis/Celery
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_RESULT_BACKEND: str = "db+sqlite:///./celery_results.db"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # AI/LLM
    QWEN_API_KEY: str = "sk-fecda1b83bfe4208892248adffc7cc38"
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    GEMINI_API_KEY: str = "sk-fecda1b83bfe4208892248adffc7cc38"
    GEMINI_BASE_URL: str = "http://127.0.0.1:8045/v1"

    MODEL_NEURAL_INTENT: str = "qwen3-max"
    MODEL_NEURAL_SCENARIO: str = "qwen3-max"
    MODEL_NEURAL_CRITIC: str = "qwen3-max"

    MODEL_RIGHT_PUPIL_PLANNER: str = "qwen-plus"
    MODEL_RIGHT_PUPIL_VL: str = "qwen-vl-plus"

    MODEL_LEFT_PUPIL_CHAIN: str = "qwen-plus"
    MODEL_LEFT_PUPIL_PARAM: str = "qwen-turbo"
    QWEN_MODEL_OMNI: str = "qwen-omni-turbo"

    MODEL_PHOENIX_CODEGEN: str = "qwen-plus"

    MODEL_DEFECT_ANALYSIS: str = "qwen-max"

    MODEL_GENERAL_CHAT: str = "qwen-turbo"
    MODEL_GENERAL_LONG: str = "qwen-long"
    MODEL_EMBEDDING: str = "text-embedding-v3"

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: str = "19530"

    # OmniParser
    OMNIPARSER_URL: str = "http://localhost:7861"
    MOCK_OMNIPARSER: bool = False

    # Git
    GIT_REPO_PATH: str = "./test_repo"
    GIT_USER_NAME: str = "ChongMing Bot"
    GIT_USER_EMAIL: str = "bot@chongming.ai"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # Assets
    ASSET_DIR: str = "assets"
    SCREENSHOT_DIR: str = "screenshots"
    TRACE_DIR: str = "traces"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._apply_env_defaults()
        self._validate_env_consistency()

    def _apply_env_defaults(self) -> None:
        """Apply safe defaults by environment."""
        env = self.APP_ENV.lower()
        if env in {"staging", "prod"}:
            self.DEBUG = False

    def _validate_env_consistency(self) -> None:
        """Fail fast for unsafe non-dev combinations."""
        env = self.APP_ENV.lower()
        broker = (self.CELERY_BROKER_URL or "").strip().lower()
        uses_memory_broker = broker.startswith("memory://")

        if env in {"staging", "prod"}:
            if uses_memory_broker:
                raise ValueError(
                    "Invalid configuration: memory broker is forbidden when APP_ENV is staging/prod."
                )
            if self.CELERY_TASK_ALWAYS_EAGER:
                raise ValueError(
                    "Invalid configuration: CELERY_TASK_ALWAYS_EAGER must be false when APP_ENV is staging/prod."
                )

        if env == "dev" and uses_memory_broker and not self.CELERY_TASK_ALWAYS_EAGER:
            raise ValueError(
                "Invalid configuration: memory broker in dev requires CELERY_TASK_ALWAYS_EAGER=true."
            )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()


settings = get_settings()
