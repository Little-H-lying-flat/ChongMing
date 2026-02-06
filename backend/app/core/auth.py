"""
认证中间件

JWT 认证和权限检查
对应 Issue #AG-002
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings


# 安全配置
SECRET_KEY = "chongming-secret-key-change-in-production"  # 生产环境从 settings 读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时


class TokenPayload(BaseModel):
    """Token 载荷"""
    sub: str  # 用户 ID
    exp: datetime
    role: str = "user"


class CurrentUser(BaseModel):
    """当前用户"""
    id: str
    role: str


# Bearer Token 提取器
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(
    user_id: str,
    role: str = "user",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建访问令牌
    
    Args:
        user_id: 用户 ID
        role: 用户角色
        expires_delta: 过期时间
        
    Returns:
        JWT 令牌字符串
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "role": role,
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> TokenPayload:
    """
    解码令牌
    
    Args:
        token: JWT 令牌
        
    Returns:
        TokenPayload: 解码后的载荷
        
    Raises:
        HTTPException: 令牌无效或过期
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """
    获取当前用户 (FastAPI 依赖)
    
    使用示例:
        @router.get("/me")
        async def get_me(user: CurrentUser = Depends(get_current_user)):
            return user
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_payload = decode_token(credentials.credentials)
    
    return CurrentUser(
        id=token_payload.sub,
        role=token_payload.role,
    )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> Optional[CurrentUser]:
    """
    可选获取当前用户 (未登录返回 None)
    """
    if not credentials:
        return None
    
    try:
        token_payload = decode_token(credentials.credentials)
        return CurrentUser(
            id=token_payload.sub,
            role=token_payload.role,
        )
    except HTTPException:
        return None


def require_role(required_role: str):
    """
    角色检查装饰器
    
    使用示例:
        @router.get("/admin")
        async def admin_only(user: CurrentUser = Depends(require_role("admin"))):
            return {"message": "Welcome admin"}
    """
    async def role_checker(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if user.role != required_role and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 {required_role} 权限",
            )
        return user
    
    return role_checker
