
import httpx
from typing import Optional
from loguru import logger
from app.core.config import settings

class AuthFixture:
    """
    全局认证夹具 (Global Auth Fixture)
    
    负责在回归测试开始前获取认证 Token，并提供给测试用例。
    避免每个测试重复登录。
    """
    
    _token: Optional[str] = None
    
    @classmethod
    async def get_token(cls) -> str:
        """
        获取 Token (单例模式 - Lazy Load)
        """
        if cls._token:
            return cls._token
            
        logger.info("AuthFixture: Acquiring new token...")
        try:
            # 使用 httpx 获取 token
            async with httpx.AsyncClient() as client:
                # 假设登录接口为 /api/v1/login/access-token (OAuth2 standard)
                # 或者 /api/v1/auth/login
                login_url = f"{settings.SERVER_HOST}/api/v1/login/access-token"
                
                # 使用默认强密码用户 (admin)
                data = {
                    "username": settings.FIRST_SUPERUSER,
                    "password": settings.FIRST_SUPERUSER_PASSWORD
                }
                
                response = await client.post(login_url, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                cls._token = token_data.get("access_token")
                
                if not cls._token:
                    raise ValueError("Login response did not contain access_token")
                    
                logger.info("AuthFixture: Token acquired successfully.")
                return cls._token
                
        except Exception as e:
            logger.error(f"AuthFixture Failed: {e}")
            # Fallback for dev/test environments without auth?
            # Or re-raise to block regression
            raise RuntimeError(f"Could not acquire auth token: {e}")

    @classmethod
    def inject_header(cls, headers: dict) -> dict:
        """
        注入认证头
        """
        if cls._token:
            headers["Authorization"] = f"Bearer {cls._token}"
        return headers
