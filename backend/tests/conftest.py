"""
pytest 配置和通用 fixtures

提供测试数据库、测试客户端等 fixtures
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from app.models.base import Base
from app.main import app
from app.core.database import get_db


# 使用 SQLite 内存数据库进行测试
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# 创建测试引擎
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # 内存数据库需要使用 StaticPool
    echo=False,
)


# SQLite 需要启用外键约束
@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 创建测试会话工厂
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    每个测试函数获取独立的数据库会话
    
    测试开始时创建所有表，测试结束后删除
    """
    # 创建所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    async with test_session_maker() as session:
        yield session
    
    # 删除所有表（清理）
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    提供测试用的 HTTP 客户端
    
    自动覆盖数据库依赖为测试数据库
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session
    
    # 覆盖依赖
    app.dependency_overrides[get_db] = override_get_db
    
    # 创建异步客户端
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    # 清理覆盖
    app.dependency_overrides.clear()


@pytest.fixture
def mock_encryption_key():
    """
    模拟加密密钥
    
    用于测试环境管理的加密功能
    """
    with patch("app.core.config.settings.ENCRYPTION_KEY", "test_encryption_key_32bytes"):
        yield


# === 测试数据 fixtures ===

@pytest.fixture
def sample_environment_data():
    """环境测试数据"""
    return {
        "name": "测试环境",
        "base_url": "https://test.example.com",
        "description": "用于单元测试的环境",
        "variables": {
            "api_key": {"value": "test-api-key", "encrypted": False, "description": "API密钥"},
            "secret": {"value": "my-secret", "encrypted": True, "description": "加密密钥"},
        },
        "headers": {"X-Test-Header": "test-value"},
        "auth_type": "bearer",
        "auth_config": {"token": "test-token"},
    }


@pytest.fixture
def sample_schema():
    """数据工厂测试 Schema"""
    return {
        "username": "username",
        "email": "email",
        "phone": "phone",
        "age": {"type": "range", "options": {"min": 18, "max": 60}},
        "status": {"type": "enum", "options": {"choices": ["active", "inactive"]}},
    }
