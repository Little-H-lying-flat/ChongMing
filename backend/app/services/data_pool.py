"""
数据池管理服务

提供测试数据的生命周期管理
对应 Issue: #DF-007
"""

import uuid
from datetime import datetime, timedelta, UTC
from typing import Any
from enum import Enum

from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.data_record import DataRecord, DataStatus


class PoolType(str, Enum):
    """数据池类型"""
    PRE_GENERATED = "pre_generated"  # 预生成池（启动时生成）
    ON_DEMAND = "on_demand"          # 按需池（使用时生成）
    SHARED = "shared"                # 共享池（跨测试共享）
    TEMPORARY = "temporary"          # 临时池（测试后清理）


class DataPool:
    """
    数据池管理器
    
    负责测试数据的生命周期管理：
    - 预生成常用数据
    - 分配和回收数据
    - 自动清理过期数据
    """
    
    # 默认配置
    DEFAULT_POOL_SIZE = 100
    DEFAULT_TTL_HOURS = 24
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_pool(
        self,
        pool_name: str,
        pool_type: PoolType,
        schema: dict[str, Any],
        size: int = DEFAULT_POOL_SIZE,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        tenant_id: str | None = None,
    ) -> str:
        """
        创建数据池
        
        Args:
            pool_name: 池名称（作为 schema_name）
            pool_type: 池类型
            schema: 数据结构
            size: 池大小
            ttl_hours: 生存时间（小时）
            tenant_id: 租户ID
            
        Returns:
            pool_id (batch_id)
        """
        from app.services.data_factory import DataFactory
        
        pool_id = f"pool-{uuid.uuid4().hex[:8]}"
        factory = DataFactory(self.db)
        
        # 计算过期时间
        expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)
        
        # 生成数据
        for i in range(size):
            record_id = f"dr-{uuid.uuid4().hex[:8]}"
            data = factory.generate_by_schema(schema, count=1)[0]
            
            record = DataRecord(
                id=record_id,
                schema_name=pool_name,
                batch_id=pool_id,
                data={"item": data, "pool_type": pool_type.value, "allocated": False},
                count=1,
                status=DataStatus.ACTIVE,
                ttl_seconds=ttl_hours * 3600,
                expires_at=expires_at,
                tenant_id=tenant_id,
            )
            self.db.add(record)
        
        await self.db.flush()
        logger.info(f"创建数据池 {pool_name}（{pool_id}），大小: {size}")
        
        return pool_id
    
    async def allocate(
        self,
        pool_name: str,
        count: int = 1,
        execution_id: str | None = None,
    ) -> list[dict]:
        """
        从池中分配数据
        
        Args:
            pool_name: 池名称
            count: 需要的数据条数
            execution_id: 执行ID（用于追踪）
            
        Returns:
            分配的数据列表
        """
        # 查找未分配的数据
        query = (
            select(DataRecord)
            .where(
                and_(
                    DataRecord.schema_name == pool_name,
                    DataRecord.status == DataStatus.ACTIVE,
                )
            )
            .limit(count)
        )
        
        result = await self.db.execute(query)
        records = result.scalars().all()
        
        allocated_data = []
        for record in records:
            # 检查是否已分配
            if record.data.get("allocated"):
                continue
            
            # 标记为已分配
            record.data = {
                **record.data,
                "allocated": True,
                "allocated_at": datetime.now(UTC).isoformat(),
                "execution_id": execution_id,
            }
            record.execution_id = execution_id
            allocated_data.append(record.data.get("item", record.data))
        
        await self.db.flush()
        logger.debug(f"从池 {pool_name} 分配了 {len(allocated_data)} 条数据")
        
        return allocated_data
    
    async def release(
        self,
        pool_name: str,
        execution_id: str,
    ) -> int:
        """
        释放执行关联的数据（归还到池中）
        
        Args:
            pool_name: 池名称
            execution_id: 执行ID
            
        Returns:
            释放的数据条数
        """
        query = (
            select(DataRecord)
            .where(
                and_(
                    DataRecord.schema_name == pool_name,
                    DataRecord.execution_id == execution_id,
                    DataRecord.status == DataStatus.ACTIVE,
                )
            )
        )
        
        result = await self.db.execute(query)
        records = result.scalars().all()
        
        for record in records:
            record.data = {
                **record.data,
                "allocated": False,
                "released_at": datetime.now(UTC).isoformat(),
            }
            record.execution_id = None
        
        await self.db.flush()
        logger.debug(f"释放了 {len(records)} 条数据到池 {pool_name}")
        
        return len(records)
    
    async def get_pool_stats(self, pool_name: str) -> dict:
        """
        获取池统计信息
        
        Args:
            pool_name: 池名称
            
        Returns:
            统计信息
        """
        query = (
            select(DataRecord)
            .where(
                and_(
                    DataRecord.schema_name == pool_name,
                    DataRecord.status == DataStatus.ACTIVE,
                )
            )
        )
        
        result = await self.db.execute(query)
        records = result.scalars().all()
        
        total = len(records)
        allocated = sum(1 for r in records if r.data.get("allocated"))
        available = total - allocated
        
        return {
            "pool_name": pool_name,
            "total": total,
            "allocated": allocated,
            "available": available,
            "utilization": round(allocated / total * 100, 2) if total > 0 else 0,
        }
    
    async def cleanup_pool(self, pool_name: str) -> int:
        """
        清理整个池
        
        Args:
            pool_name: 池名称
            
        Returns:
            清理的数据条数
        """
        now = datetime.now(UTC)
        result = await self.db.execute(
            update(DataRecord)
            .where(DataRecord.schema_name == pool_name)
            .values(status=DataStatus.CLEANED, cleaned_at=now)
        )
        
        count = result.rowcount
        logger.info(f"清理池 {pool_name}，共 {count} 条记录")
        
        return count
    
    async def refill_pool(
        self,
        pool_name: str,
        schema: dict[str, Any],
        target_size: int | None = None,
    ) -> int:
        """
        补充池数据（补充到目标大小）
        
        Args:
            pool_name: 池名称
            schema: 数据结构
            target_size: 目标大小（默认 DEFAULT_POOL_SIZE）
            
        Returns:
            新增的数据条数
        """
        target_size = target_size or self.DEFAULT_POOL_SIZE
        
        stats = await self.get_pool_stats(pool_name)
        current_available = stats["available"]
        
        if current_available >= target_size:
            return 0
        
        need_count = target_size - current_available
        
        from app.services.data_factory import DataFactory
        
        factory = DataFactory(self.db)
        pool_id = f"pool-{uuid.uuid4().hex[:8]}"
        expires_at = datetime.now(UTC) + timedelta(hours=self.DEFAULT_TTL_HOURS)
        
        for _ in range(need_count):
            record_id = f"dr-{uuid.uuid4().hex[:8]}"
            data = factory.generate_by_schema(schema, count=1)[0]
            
            record = DataRecord(
                id=record_id,
                schema_name=pool_name,
                batch_id=pool_id,
                data={"item": data, "allocated": False},
                count=1,
                status=DataStatus.ACTIVE,
                ttl_seconds=self.DEFAULT_TTL_HOURS * 3600,
                expires_at=expires_at,
            )
            self.db.add(record)
        
        await self.db.flush()
        logger.info(f"补充池 {pool_name}，新增 {need_count} 条数据")
        
        return need_count
    
    async def list_pools(self) -> list[dict]:
        """
        列出所有数据池
        
        Returns:
            池信息列表
        """
        # 获取所有唯一的 schema_name（作为池名称）
        query = select(DataRecord.schema_name).distinct()
        result = await self.db.execute(query)
        pool_names = [row[0] for row in result.fetchall()]
        
        pools = []
        for name in pool_names:
            stats = await self.get_pool_stats(name)
            pools.append(stats)
        
        return pools
