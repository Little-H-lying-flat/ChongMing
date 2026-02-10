"""
数据池管理单元测试
"""

import pytest
import pytest_asyncio

from app.models.data_record import DataRecord, DataStatus
from app.services.data_pool import DataPool, PoolType


class TestDataPool:
    """测试数据池管理"""

    @pytest_asyncio.fixture
    async def pool(self, db_session):
        """创建 DataPool 实例"""
        return DataPool(db_session)

    @pytest.fixture
    def simple_schema(self):
        """简单测试 schema"""
        return {
            "name": "string",
            "email": "email",
        }

    @pytest.mark.asyncio
    async def test_create_pool(self, pool, simple_schema):
        """测试创建数据池"""
        pool_id = await pool.create_pool(
            pool_name="test_users",
            pool_type=PoolType.TEMPORARY,
            schema=simple_schema,
            size=5,
            ttl_hours=1,
        )

        assert pool_id.startswith("pool-")
        
        stats = await pool.get_pool_stats("test_users")
        assert stats["total"] == 5
        assert stats["available"] == 5
        assert stats["allocated"] == 0

    @pytest.mark.asyncio
    async def test_allocate_data(self, pool, simple_schema):
        """测试分配数据"""
        await pool.create_pool(
            pool_name="alloc_test",
            pool_type=PoolType.ON_DEMAND,
            schema=simple_schema,
            size=10,
        )

        # 分配 3 条数据
        data = await pool.allocate("alloc_test", count=3, execution_id="exec-001")

        assert len(data) == 3
        
        stats = await pool.get_pool_stats("alloc_test")
        assert stats["allocated"] == 3
        assert stats["available"] == 7

    @pytest.mark.asyncio
    async def test_release_data(self, pool, simple_schema):
        """测试释放数据"""
        await pool.create_pool(
            pool_name="release_test",
            pool_type=PoolType.SHARED,
            schema=simple_schema,
            size=5,
        )

        # 分配
        await pool.allocate("release_test", count=3, execution_id="exec-002")
        
        # 释放
        released = await pool.release("release_test", execution_id="exec-002")

        assert released == 3
        
        stats = await pool.get_pool_stats("release_test")
        assert stats["available"] == 5

    @pytest.mark.asyncio
    async def test_get_pool_stats(self, pool, simple_schema):
        """测试获取池统计"""
        await pool.create_pool(
            pool_name="stats_test",
            pool_type=PoolType.PRE_GENERATED,
            schema=simple_schema,
            size=10,
        )

        await pool.allocate("stats_test", count=4, execution_id="exec-003")

        stats = await pool.get_pool_stats("stats_test")

        assert stats["pool_name"] == "stats_test"
        assert stats["total"] == 10
        assert stats["allocated"] == 4
        assert stats["available"] == 6
        assert stats["utilization"] == 40.0

    @pytest.mark.asyncio
    async def test_cleanup_pool(self, pool, simple_schema):
        """测试清理池"""
        await pool.create_pool(
            pool_name="cleanup_test",
            pool_type=PoolType.TEMPORARY,
            schema=simple_schema,
            size=5,
        )

        cleaned = await pool.cleanup_pool("cleanup_test")

        assert cleaned == 5
        
        stats = await pool.get_pool_stats("cleanup_test")
        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_list_pools(self, pool, simple_schema):
        """测试列出所有池"""
        await pool.create_pool(
            pool_name="pool_a",
            pool_type=PoolType.TEMPORARY,
            schema=simple_schema,
            size=3,
        )
        await pool.create_pool(
            pool_name="pool_b",
            pool_type=PoolType.SHARED,
            schema=simple_schema,
            size=5,
        )

        pools = await pool.list_pools()

        assert len(pools) >= 2
        pool_names = [p["pool_name"] for p in pools]
        assert "pool_a" in pool_names
        assert "pool_b" in pool_names


class TestPoolType:
    """测试池类型枚举"""

    def test_pool_types(self):
        """测试池类型值"""
        assert PoolType.PRE_GENERATED.value == "pre_generated"
        assert PoolType.ON_DEMAND.value == "on_demand"
        assert PoolType.SHARED.value == "shared"
        assert PoolType.TEMPORARY.value == "temporary"
