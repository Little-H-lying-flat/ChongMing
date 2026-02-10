"""
环境管理服务单元测试

测试 EnvironmentManager 的 CRUD、加密、变量注入功能
"""

import pytest
import pytest_asyncio

from app.models.environment import Environment
from app.services.environment_manager import EnvironmentManager


class TestEnvironmentManagerCRUD:
    """测试环境管理 CRUD 操作"""

    @pytest_asyncio.fixture
    async def manager(self, db_session):
        """创建 EnvironmentManager 实例"""
        return EnvironmentManager(db_session)

    @pytest.mark.asyncio
    async def test_create_environment(self, manager, sample_environment_data):
        """测试创建环境"""
        env = await manager.create(
            name=sample_environment_data["name"],
            base_url=sample_environment_data["base_url"],
            description=sample_environment_data["description"],
        )

        assert env is not None
        assert env.id.startswith("env-")
        assert env.name == sample_environment_data["name"]
        assert env.base_url == sample_environment_data["base_url"]
        assert env.is_active is True

    @pytest.mark.asyncio
    async def test_get_environment_by_id(self, manager, sample_environment_data):
        """测试按 ID 获取环境"""
        created = await manager.create(
            name=sample_environment_data["name"],
            base_url=sample_environment_data["base_url"],
        )

        fetched = await manager.get(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == created.name

    @pytest.mark.asyncio
    async def test_get_environment_by_name(self, manager, sample_environment_data):
        """测试按名称获取环境"""
        await manager.create(
            name=sample_environment_data["name"],
            base_url=sample_environment_data["base_url"],
        )

        fetched = await manager.get_by_name(sample_environment_data["name"])

        assert fetched is not None
        assert fetched.name == sample_environment_data["name"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_environment(self, manager):
        """测试获取不存在的环境"""
        result = await manager.get("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_environments(self, manager):
        """测试列出所有环境"""
        # 创建多个环境
        await manager.create(name="Env1", base_url="https://env1.com")
        await manager.create(name="Env2", base_url="https://env2.com")

        envs = await manager.list_all()

        assert len(envs) == 2

    @pytest.mark.asyncio
    async def test_update_environment(self, manager, sample_environment_data):
        """测试更新环境"""
        env = await manager.create(
            name=sample_environment_data["name"],
            base_url=sample_environment_data["base_url"],
        )

        updated = await manager.update(
            env.id,
            name="更新后的环境",
            base_url="https://updated.example.com",
        )

        assert updated is not None
        assert updated.name == "更新后的环境"
        assert updated.base_url == "https://updated.example.com"

    @pytest.mark.asyncio
    async def test_delete_environment(self, manager, sample_environment_data):
        """测试删除环境"""
        env = await manager.create(
            name=sample_environment_data["name"],
            base_url=sample_environment_data["base_url"],
        )

        success = await manager.delete(env.id)
        assert success is True

        # 验证已删除
        fetched = await manager.get(env.id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_set_default_environment(self, manager):
        """测试设置默认环境"""
        env1 = await manager.create(name="Env1", base_url="https://env1.com", is_default=True)
        env2 = await manager.create(name="Env2", base_url="https://env2.com", is_default=True)

        # env2 设置为默认后，env1 应该不再是默认
        default_env = await manager.get_default()
        assert default_env is not None
        assert default_env.id == env2.id


class TestEnvironmentManagerVariables:
    """测试变量管理功能"""

    @pytest_asyncio.fixture
    async def manager(self, db_session):
        return EnvironmentManager(db_session)

    @pytest_asyncio.fixture
    async def env_with_vars(self, manager, sample_environment_data):
        """创建带变量的环境"""
        return await manager.create(
            name=sample_environment_data["name"],
            base_url=sample_environment_data["base_url"],
            variables=sample_environment_data["variables"],
        )

    @pytest.mark.asyncio
    async def test_set_variable(self, manager, sample_environment_data):
        """测试设置变量"""
        env = await manager.create(
            name=sample_environment_data["name"],
            base_url=sample_environment_data["base_url"],
        )

        success = await manager.set_variable(
            env_id=env.id,
            key="test_var",
            value="test_value",
            description="测试变量",
        )

        assert success is True

        # 验证变量已设置
        value = await manager.get_variable(env.id, "test_var")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_get_variable(self, manager, env_with_vars):
        """测试获取变量"""
        value = await manager.get_variable(env_with_vars.id, "api_key")
        assert value == "test-api-key"

    @pytest.mark.asyncio
    async def test_get_nonexistent_variable(self, manager, env_with_vars):
        """测试获取不存在的变量"""
        value = await manager.get_variable(env_with_vars.id, "nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete_variable(self, manager, env_with_vars):
        """测试删除变量"""
        success = await manager.delete_variable(env_with_vars.id, "api_key")
        assert success is True

        # 验证变量已删除
        value = await manager.get_variable(env_with_vars.id, "api_key")
        assert value is None


class TestEnvironmentManagerInjection:
    """测试变量注入功能"""

    @pytest_asyncio.fixture
    async def manager(self, db_session):
        return EnvironmentManager(db_session)

    @pytest_asyncio.fixture
    async def env_for_injection(self, manager):
        """创建用于注入测试的环境"""
        return await manager.create(
            name="Injection Test",
            base_url="https://api.example.com",
            variables={
                "api_version": {"value": "v1", "encrypted": False, "description": ""},
                "user_id": {"value": "12345", "encrypted": False, "description": ""},
            },
        )

    @pytest.mark.asyncio
    async def test_inject_dollar_syntax(self, manager, env_for_injection):
        """测试 ${var} 格式注入"""
        text = "访问 ${base_url}/users/${user_id}"
        result = await manager.inject_variables(env_for_injection.id, text)

        assert result == "访问 https://api.example.com/users/12345"

    @pytest.mark.asyncio
    async def test_inject_brace_syntax(self, manager, env_for_injection):
        """测试 {{var}} 格式注入"""
        text = "API 版本: {{api_version}}"
        result = await manager.inject_variables(env_for_injection.id, text)

        assert result == "API 版本: v1"

    @pytest.mark.asyncio
    async def test_inject_with_additional_vars(self, manager, env_for_injection):
        """测试额外变量覆盖"""
        text = "${user_id} - ${extra}"
        result = await manager.inject_variables(
            env_for_injection.id,
            text,
            additional_vars={"extra": "附加值", "user_id": "覆盖值"},
        )

        # additional_vars 应该优先
        assert "覆盖值" in result
        assert "附加值" in result

    @pytest.mark.asyncio
    async def test_inject_unknown_var_unchanged(self, manager, env_for_injection):
        """测试未知变量保持不变"""
        text = "${unknown_var}"
        result = await manager.inject_variables(env_for_injection.id, text)

        assert result == "${unknown_var}"

    @pytest.mark.asyncio
    async def test_get_injected_url(self, manager, env_for_injection):
        """测试获取注入的完整 URL"""
        path = "/api/${api_version}/users/${user_id}"
        result = await manager.get_injected_url(env_for_injection.id, path)

        assert result == "https://api.example.com/api/v1/users/12345"
