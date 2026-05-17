"""
数据工厂服务

对应 Issue #DF-001, #DF-002
- Faker 集成与 Schema 驱动生成
- 中文本地化
- 数据清理
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from faker import Faker
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_record import DataRecord, DataStatus


# 初始化 Faker (中文本地化)
fake_zh = Faker("zh_CN")
fake_en = Faker("en_US")


# 预定义 Schema 类型映射
SCHEMA_GENERATORS = {
    # 基础类型
    "string": lambda f: f.pystr(max_chars=20),
    "text": lambda f: f.text(max_nb_chars=200),
    "integer": lambda f: f.random_int(min=1, max=10000),
    "float": lambda f: f.pyfloat(min_value=0, max_value=1000),
    "boolean": lambda f: f.boolean(),
    "uuid": lambda f: str(uuid.uuid4()),
    
    # 个人信息
    "name": lambda f: f.name(),
    "username": lambda f: f.user_name(),
    "email": lambda f: f.email(),
    "phone": lambda f: f.phone_number(),
    "address": lambda f: f.address(),
    "company": lambda f: f.company(),
    
    # 网络相关
    "url": lambda f: f.url(),
    "ip": lambda f: f.ipv4(),
    "mac": lambda f: f.mac_address(),
    
    # 时间日期
    "date": lambda f: f.date(),
    "datetime": lambda f: f.date_time().isoformat(),
    "timestamp": lambda f: int(f.date_time().timestamp()),
    
    # 金融
    "price": lambda f: round(f.pyfloat(min_value=1, max_value=9999), 2),
    "currency": lambda f: f.currency_code(),
    
    # 中文特定
    "chinese_name": lambda f: f.name(),
    "chinese_address": lambda f: f.address(),
    "id_card": lambda f: f.ssn(),
}


class DataFactory:
    """数据工厂服务"""
    
    def __init__(self, db: AsyncSession, locale: str = "zh_CN"):
        self.db = db
        self.faker = fake_zh if locale == "zh_CN" else fake_en
    
    def generate_by_schema(
        self,
        schema: dict[str, str | dict],
        count: int = 1,
    ) -> list[dict]:
        """
        根据 Schema 生成数据
        
        Args:
            schema: 字段定义，格式: {"field_name": "type" | {"type": "...", "options": {}}}
            count: 生成数量
        
        Returns:
            生成的数据列表
        """
        results = []
        for _ in range(count):
            item = {}
            for field_name, field_def in schema.items():
                item[field_name] = self._generate_field(field_def)
            results.append(item)
        return results
    
    def _generate_field(self, field_def: str | dict) -> Any:
        """生成单个字段值"""
        if isinstance(field_def, str):
            field_type = field_def
            options = {}
        else:
            field_type = field_def.get("type", "string")
            options = field_def.get("options", {})
        
        # 使用预定义生成器
        if field_type in SCHEMA_GENERATORS:
            return SCHEMA_GENERATORS[field_type](self.faker)
        
        # 特殊处理
        if field_type == "enum":
            choices = options.get("choices", ["A", "B", "C"])
            return self.faker.random_element(choices)
        
        if field_type == "range":
            min_val = options.get("min", 0)
            max_val = options.get("max", 100)
            return self.faker.random_int(min=min_val, max=max_val)
        
        if field_type == "pattern":
            pattern = options.get("pattern", "???-###")
            return self.faker.bothify(pattern)
        
        if field_type == "fixed":
            return options.get("value", "")
        
        # 默认返回字符串
        return self.faker.pystr(max_chars=20)
    
    async def generate_and_save(
        self,
        schema_name: str,
        schema: dict[str, str | dict],
        count: int = 1,
        ttl_seconds: int | None = None,
        execution_id: str | None = None,
        environment_id: str | None = None,
        tenant_id: str | None = None,
    ) -> DataRecord:
        """生成数据并保存记录"""
        # 生成数据
        data_list = self.generate_by_schema(schema, count)
        
        # 计算过期时间
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        
        # 创建记录
        record_id = f"dr-{uuid.uuid4().hex[:8]}"
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        
        record = DataRecord(
            id=record_id,
            schema_name=schema_name,
            batch_id=batch_id,
            data={"items": data_list, "schema": schema},
            count=count,
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
            execution_id=execution_id,
            environment_id=environment_id,
            tenant_id=tenant_id,
        )
        
        self.db.add(record)
        await self.db.flush()
        return record
    
    async def get_record(self, record_id: str) -> DataRecord | None:
        """获取数据记录"""
        result = await self.db.execute(
            select(DataRecord).where(DataRecord.id == record_id)
        )
        return result.scalar_one_or_none()
    
    async def cleanup_expired(self, tenant_id: str | None = None) -> int:
        """清理过期数据"""
        now = datetime.now(timezone.utc)
        query = (
            update(DataRecord)
            .where(DataRecord.expires_at < now)
            .where(DataRecord.status == DataStatus.ACTIVE)
            .values(status=DataStatus.EXPIRED, cleaned_at=now)
        )
        if tenant_id:
            query = query.where(DataRecord.tenant_id == tenant_id)
        
        result = await self.db.execute(query)
        return result.rowcount
    
    async def cleanup_by_batch(self, batch_id: str) -> int:
        """按批次清理数据"""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(DataRecord)
            .where(DataRecord.batch_id == batch_id)
            .values(status=DataStatus.CLEANED, cleaned_at=now)
        )
        return result.rowcount
    
    async def delete_cleaned(self, days_old: int = 7) -> int:
        """删除已清理的旧记录"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
        result = await self.db.execute(
            delete(DataRecord)
            .where(DataRecord.status == DataStatus.CLEANED)
            .where(DataRecord.cleaned_at < cutoff)
        )
        return result.rowcount
