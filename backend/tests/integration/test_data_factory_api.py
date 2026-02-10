"""
数据工厂 API 集成测试

测试数据工厂的完整 API 流程
"""

import pytest
import pytest_asyncio


class TestDataFactoryAPI:
    """数据工厂 API 集成测试"""

    @pytest.mark.asyncio
    async def test_generate_data(self, client):
        """测试生成数据 API"""
        response = await client.post(
            "/api/v1/data-factory/generate",
            json={
                "schema_name": "test_users",
                "schema": {
                    "username": "username",
                    "email": "email",
                    "phone": "phone",
                },
                "count": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # 根据实际 GenerateResponse 格式验证
        assert "record_id" in data
        assert "batch_id" in data
        assert data["count"] == 5
        assert "data" in data
        assert len(data["data"]) == 5

    @pytest.mark.asyncio
    async def test_generate_with_enum(self, client):
        """测试枚举类型生成"""
        response = await client.post(
            "/api/v1/data-factory/generate",
            json={
                "schema_name": "enum_test",
                "schema": {
                    "status": {"type": "enum", "options": {"choices": ["a", "b", "c"]}},
                },
                "count": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        items = data["data"]
        for item in items:
            assert item["status"] in ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_generate_with_range(self, client):
        """测试范围类型生成"""
        response = await client.post(
            "/api/v1/data-factory/generate",
            json={
                "schema_name": "range_test",
                "schema": {
                    "age": {"type": "range", "options": {"min": 18, "max": 60}},
                },
                "count": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        items = data["data"]
        for item in items:
            assert 18 <= item["age"] <= 60

    @pytest.mark.asyncio
    async def test_get_data_record(self, client):
        """测试获取数据记录"""
        # 先生成数据
        gen_response = await client.post(
            "/api/v1/data-factory/generate",
            json={
                "schema_name": "get_test",
                "schema": {"id": "uuid"},
                "count": 1,
            },
        )
        record_id = gen_response.json()["record_id"]

        # 获取记录
        response = await client.get(f"/api/v1/data-factory/records/{record_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == record_id

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, client):
        """测试清理过期数据"""
        # 使用 DELETE 方法，传递请求体
        response = await client.request(
            "DELETE",
            "/api/v1/data-factory/cleanup",
            json={
                "cleanup_expired": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "results" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_record(self, client):
        """测试获取不存在的记录"""
        response = await client.get("/api/v1/data-factory/records/nonexistent-id")

        assert response.status_code == 404


class TestDataFactorySchemas:
    """测试 Schema 列表 API"""

    @pytest.mark.asyncio
    async def test_list_schemas(self, client):
        """测试列出可用 schema 类型"""
        response = await client.get("/api/v1/data-factory/schemas")

        assert response.status_code == 200
        data = response.json()
        
        # 根据实际响应格式验证
        assert "available_types" in data
        schemas = data["available_types"]
        
        # 验证常用类型存在
        assert "string" in schemas
        assert "email" in schemas
        assert "phone" in schemas
        assert "uuid" in schemas
