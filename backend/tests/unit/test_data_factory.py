"""
数据工厂服务单元测试

测试 DataFactory 的数据生成、记录管理和清理功能
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC

from app.models.data_record import DataRecord, DataStatus
from app.services.data_factory import DataFactory, SCHEMA_GENERATORS


class TestDataFactoryGeneration:
    """测试数据生成功能"""

    @pytest_asyncio.fixture
    async def factory(self, db_session):
        """创建 DataFactory 实例"""
        return DataFactory(db_session, locale="zh_CN")

    def test_generate_string_field(self, factory):
        """测试字符串字段生成"""
        data = factory.generate_by_schema({"name": "string"}, count=1)

        assert len(data) == 1
        assert "name" in data[0]
        assert isinstance(data[0]["name"], str)

    def test_generate_email_field(self, factory):
        """测试邮箱字段生成"""
        data = factory.generate_by_schema({"email": "email"}, count=1)

        assert "@" in data[0]["email"]

    def test_generate_phone_field(self, factory):
        """测试手机号字段生成"""
        data = factory.generate_by_schema({"phone": "phone"}, count=1)

        assert len(data[0]["phone"]) > 0

    def test_generate_integer_field(self, factory):
        """测试整数字段生成"""
        data = factory.generate_by_schema({"age": "integer"}, count=1)

        assert isinstance(data[0]["age"], int)

    def test_generate_boolean_field(self, factory):
        """测试布尔字段生成"""
        data = factory.generate_by_schema({"is_active": "boolean"}, count=1)

        assert isinstance(data[0]["is_active"], bool)

    def test_generate_uuid_field(self, factory):
        """测试 UUID 字段生成"""
        data = factory.generate_by_schema({"id": "uuid"}, count=1)

        assert len(data[0]["id"]) == 36  # UUID 格式
        assert "-" in data[0]["id"]

    def test_generate_enum_field(self, factory):
        """测试枚举字段生成"""
        schema = {
            "status": {
                "type": "enum",
                "options": {"choices": ["active", "inactive", "pending"]},
            }
        }
        data = factory.generate_by_schema(schema, count=1)

        assert data[0]["status"] in ["active", "inactive", "pending"]

    def test_generate_range_field(self, factory):
        """测试范围字段生成"""
        schema = {
            "age": {
                "type": "range",
                "options": {"min": 18, "max": 60},
            }
        }
        data = factory.generate_by_schema(schema, count=1)

        assert 18 <= data[0]["age"] <= 60

    def test_generate_pattern_field(self, factory):
        """测试模式字段生成"""
        schema = {
            "code": {
                "type": "pattern",
                "options": {"pattern": "???-###"},  # 3字母-3数字
            }
        }
        data = factory.generate_by_schema(schema, count=1)

        assert len(data[0]["code"]) == 7
        assert "-" in data[0]["code"]

    def test_generate_fixed_field(self, factory):
        """测试固定值字段生成"""
        schema = {
            "type": {
                "type": "fixed",
                "options": {"value": "USER"},
            }
        }
        data = factory.generate_by_schema(schema, count=1)

        assert data[0]["type"] == "USER"

    def test_generate_multiple_records(self, factory, sample_schema):
        """测试批量生成"""
        data = factory.generate_by_schema(sample_schema, count=10)

        assert len(data) == 10
        for item in data:
            assert "username" in item
            assert "email" in item
            assert "phone" in item

    def test_generate_complex_schema(self, factory):
        """测试复杂 Schema 生成"""
        schema = {
            "id": "uuid",
            "username": "username",
            "email": "email",
            "phone": "phone",
            "age": {"type": "range", "options": {"min": 18, "max": 65}},
            "status": {"type": "enum", "options": {"choices": ["active", "inactive"]}},
            "created_at": "datetime",
        }
        data = factory.generate_by_schema(schema, count=5)

        assert len(data) == 5
        for item in data:
            assert len(item) == 7
            assert 18 <= item["age"] <= 65
            assert item["status"] in ["active", "inactive"]


class TestDataFactoryStorage:
    """测试数据存储功能"""

    @pytest_asyncio.fixture
    async def factory(self, db_session):
        return DataFactory(db_session, locale="zh_CN")

    @pytest.mark.asyncio
    async def test_generate_and_save(self, factory, sample_schema):
        """测试生成并保存数据"""
        record = await factory.generate_and_save(
            schema_name="user_test",
            schema=sample_schema,
            count=5,
        )

        assert record is not None
        assert record.id.startswith("dr-")
        assert record.batch_id.startswith("batch-")
        assert record.schema_name == "user_test"
        assert record.count == 5
        assert record.status == DataStatus.ACTIVE
        assert len(record.data["items"]) == 5

    @pytest.mark.asyncio
    async def test_generate_with_ttl(self, factory, sample_schema):
        """测试带 TTL 的数据生成"""
        record = await factory.generate_and_save(
            schema_name="temp_data",
            schema=sample_schema,
            count=1,
            ttl_seconds=3600,  # 1 小时
        )

        assert record.ttl_seconds == 3600
        assert record.expires_at is not None
        # 过期时间应该在 1 小时后
        assert record.expires_at > datetime.now(UTC)
        assert record.expires_at < datetime.now(UTC) + timedelta(hours=2)

    @pytest.mark.asyncio
    async def test_get_record(self, factory, sample_schema):
        """测试获取记录"""
        created = await factory.generate_and_save(
            schema_name="get_test",
            schema=sample_schema,
            count=1,
        )

        fetched = await factory.get_record(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.schema_name == "get_test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_record(self, factory):
        """测试获取不存在的记录"""
        result = await factory.get_record("nonexistent-id")
        assert result is None


class TestDataFactoryCleanup:
    """测试数据清理功能"""

    @pytest_asyncio.fixture
    async def factory(self, db_session):
        return DataFactory(db_session, locale="zh_CN")

    @pytest.mark.asyncio
    async def test_cleanup_by_batch(self, factory, sample_schema):
        """测试按批次清理"""
        record = await factory.generate_and_save(
            schema_name="cleanup_test",
            schema=sample_schema,
            count=1,
        )
        batch_id = record.batch_id

        cleaned_count = await factory.cleanup_by_batch(batch_id)

        assert cleaned_count == 1

        # 验证状态已更新
        fetched = await factory.get_record(record.id)
        assert fetched.status == DataStatus.CLEANED
        assert fetched.cleaned_at is not None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, factory, db_session, sample_schema):
        """测试清理过期数据"""
        # 创建一条过期的记录
        record = await factory.generate_and_save(
            schema_name="expired_test",
            schema=sample_schema,
            count=1,
            ttl_seconds=1,  # 1 秒
        )

        # 手动设置过期时间为过去
        record.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await db_session.flush()

        cleaned_count = await factory.cleanup_expired()

        assert cleaned_count == 1

        fetched = await factory.get_record(record.id)
        assert fetched.status == DataStatus.EXPIRED


class TestSchemaGenerators:
    """测试预定义的 Schema 生成器"""

    def test_all_generators_exist(self):
        """验证所有预定义生成器存在"""
        expected_types = [
            "string", "text", "integer", "float", "boolean", "uuid",
            "name", "username", "email", "phone", "address", "company",
            "url", "ip", "mac",
            "date", "datetime", "timestamp",
            "price", "currency",
            "chinese_name", "chinese_address", "id_card",
        ]

        for field_type in expected_types:
            assert field_type in SCHEMA_GENERATORS, f"缺少生成器: {field_type}"

    def test_generators_are_callable(self):
        """验证所有生成器可调用"""
        from faker import Faker

        fake = Faker("zh_CN")
        for field_type, generator in SCHEMA_GENERATORS.items():
            try:
                result = generator(fake)
                assert result is not None, f"生成器 {field_type} 返回 None"
            except Exception as e:
                pytest.fail(f"生成器 {field_type} 执行失败: {e}")
