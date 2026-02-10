"""
环境管理 API 集成测试

测试环境管理的完整 API 流程
"""

import pytest
import pytest_asyncio


class TestEnvironmentAPI:
    """环境管理 API 集成测试"""

    @pytest.mark.asyncio
    async def test_create_environment(self, client):
        """测试创建环境 API"""
        response = await client.post(
            "/api/v1/environments",
            json={
                "name": "测试环境",
                "base_url": "https://test.example.com",
                "description": "API 集成测试环境",
                "variables": {
                    "api_key": {"value": "test-key", "encrypted": False, "description": "API密钥"},
                },
                "headers": {"X-Test": "true"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "测试环境"
        assert data["base_url"] == "https://test.example.com"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_environments(self, client):
        """测试列出环境 API"""
        # 先创建一个环境
        await client.post(
            "/api/v1/environments",
            json={
                "name": "列表测试环境",
                "base_url": "https://list.example.com",
            },
        )

        response = await client.get("/api/v1/environments")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_environment(self, client):
        """测试获取环境详情 API"""
        # 创建环境
        create_response = await client.post(
            "/api/v1/environments",
            json={
                "name": "详情测试环境",
                "base_url": "https://detail.example.com",
            },
        )
        env_id = create_response.json()["id"]

        # 获取详情
        response = await client.get(f"/api/v1/environments/{env_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == env_id
        assert data["name"] == "详情测试环境"

    @pytest.mark.asyncio
    async def test_update_environment(self, client):
        """测试更新环境 API"""
        # 创建环境
        create_response = await client.post(
            "/api/v1/environments",
            json={
                "name": "更新测试环境",
                "base_url": "https://update.example.com",
            },
        )
        env_id = create_response.json()["id"]

        # 更新环境
        response = await client.put(
            f"/api/v1/environments/{env_id}",
            json={
                "name": "已更新环境",
                "base_url": "https://updated.example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "已更新环境"
        assert data["base_url"] == "https://updated.example.com"

    @pytest.mark.asyncio
    async def test_delete_environment(self, client):
        """测试删除环境 API"""
        # 创建环境
        create_response = await client.post(
            "/api/v1/environments",
            json={
                "name": "删除测试环境",
                "base_url": "https://delete.example.com",
            },
        )
        env_id = create_response.json()["id"]

        # 删除环境
        response = await client.delete(f"/api/v1/environments/{env_id}")
        assert response.status_code == 204

        # 验证已删除
        get_response = await client.get(f"/api/v1/environments/{env_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_set_variable(self, client):
        """测试设置变量 API"""
        # 创建环境
        create_response = await client.post(
            "/api/v1/environments",
            json={
                "name": "变量测试环境",
                "base_url": "https://var.example.com",
            },
        )
        env_id = create_response.json()["id"]

        # 设置变量
        response = await client.post(
            f"/api/v1/environments/{env_id}/variables",
            json={
                "key": "new_var",
                "value": "new_value",
                "encrypted": False,
                "description": "新变量",
            },
        )

        assert response.status_code == 200
        data = response.json()
        # 实际 API 返回 {"message": "变量 'xxx' 已设置"}
        assert "message" in data

    @pytest.mark.asyncio
    async def test_get_all_variables(self, client):
        """测试获取所有变量 API"""
        # 创建带变量的环境
        create_response = await client.post(
            "/api/v1/environments",
            json={
                "name": "获取变量测试",
                "base_url": "https://getvar.example.com",
                "variables": {
                    "test_key": {"value": "test_value", "encrypted": False, "description": ""},
                },
            },
        )
        env_id = create_response.json()["id"]

        # 获取所有变量 (GET /{env_id}/variables 返回所有变量)
        response = await client.get(f"/api/v1/environments/{env_id}/variables")

        assert response.status_code == 200
        data = response.json()
        assert "variables" in data
        assert "test_key" in data["variables"]

    @pytest.mark.asyncio
    async def test_inject_variables(self, client):
        """测试变量注入 API"""
        # 创建环境
        create_response = await client.post(
            "/api/v1/environments",
            json={
                "name": "注入测试环境",
                "base_url": "https://inject.example.com",
                "variables": {
                    "version": {"value": "v1", "encrypted": False, "description": ""},
                },
            },
        )
        env_id = create_response.json()["id"]

        # 注入变量
        response = await client.post(
            f"/api/v1/environments/{env_id}/inject",
            json={
                "text": "API版本: ${version}",
            },
        )

        assert response.status_code == 200
        data = response.json()
        # 实际 API 返回 {"original": "...", "injected": "..."}
        assert "injected" in data
        assert "v1" in data["injected"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_environment(self, client):
        """测试获取不存在的环境"""
        response = await client.get("/api/v1/environments/nonexistent-id")

        assert response.status_code == 404
