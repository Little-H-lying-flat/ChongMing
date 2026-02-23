"""
数据库连接管理

使用 SQLAlchemy 2.0 异步模式
对应 Issue #AG-006
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.base import Base


# 创建异步引擎
print(f"DEBUG: DATABASE_URL={settings.DATABASE_URL}")
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,  # 生产环境可改为 QueuePool
)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db():
    """初始化数据库 - 创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    """删除所有表 - 仅用于测试"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话 (上下文管理器)
    
    使用示例:
        async with get_db_session() as session:
            result = await session.execute(select(User))
    """
    session = async_session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话 (FastAPI 依赖注入)
    """
    async with async_session_maker() as session:
        try:
            yield session
            # 性能修复: 不要在 GET 或只读请求中强行全局提交
            # 强行提交会导致 SQLite 在高并发或压测时为了获得排他锁而卡住 5-10秒！
            # 各个写入接口已经手动调用了 await db.commit()
            
            # 如果非常需要安全兜底，可以不报错，或者这里干脆去掉 await session.commit()
            # 大部分正常业务逻辑都已经手动写了 commit
            # await session.commit() 
        except Exception:
            await session.rollback()
            raise
