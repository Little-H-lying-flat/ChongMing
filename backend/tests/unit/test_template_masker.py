"""
数据模板和脱敏功能单元测试
"""

import pytest

from app.services.data_template import (
    DataTemplate,
    TemplateRegistry,
    TemplateParser,
    template_registry,
)
from app.services.data_masker import (
    DataMasker,
    MaskStrategy,
    data_masker,
)


class TestDataTemplate:
    """测试数据模板"""

    def test_create_template(self):
        """测试创建模板"""
        template = DataTemplate(
            name="test_user",
            schema={"name": "string", "age": "integer"},
            description="测试用户模板",
        )
        
        assert template.name == "test_user"
        assert "name" in template.schema
        assert "age" in template.schema

    def test_template_to_dict(self):
        """测试模板转字典"""
        template = DataTemplate(
            name="test",
            schema={"id": "uuid"},
            description="描述",
        )
        
        data = template.to_dict()
        
        assert data["name"] == "test"
        assert data["schema"] == {"id": "uuid"}
        assert data["description"] == "描述"

    def test_template_from_dict(self):
        """测试从字典创建模板"""
        data = {
            "name": "from_dict",
            "schema": {"email": "email"},
            "description": "从字典创建",
        }
        
        template = DataTemplate.from_dict(data)
        
        assert template.name == "from_dict"
        assert template.schema["email"] == "email"


class TestTemplateRegistry:
    """测试模板注册表"""

    @pytest.fixture
    def registry(self):
        return TemplateRegistry()

    def test_builtin_templates_loaded(self, registry):
        """测试内置模板已加载"""
        user_template = registry.get("user")
        
        assert user_template is not None
        assert "email" in user_template.schema
        assert "phone" in user_template.schema

    def test_list_all_templates(self, registry):
        """测试列出所有模板"""
        templates = registry.list_all()
        
        assert len(templates) >= 4  # user, address, order, product

    def test_register_custom_template(self, registry):
        """测试注册自定义模板"""
        custom = DataTemplate(
            name="custom",
            schema={"field1": "string"},
        )
        registry.register(custom)
        
        assert registry.get("custom") is not None

    def test_resolve_template(self, registry):
        """测试解析模板"""
        schema = registry.resolve("user")
        
        assert "id" in schema
        assert "email" in schema
        assert "phone" in schema

    def test_resolve_nonexistent_template(self, registry):
        """测试解析不存在的模板"""
        with pytest.raises(ValueError, match="模板不存在"):
            registry.resolve("nonexistent")


class TestTemplateParser:
    """测试模板解析器"""

    @pytest.fixture
    def parser(self):
        return TemplateParser()

    def test_instantiate_template(self, parser):
        """测试实例化模板"""
        schema = parser.instantiate("user")
        
        assert "id" in schema
        assert "email" in schema

    def test_instantiate_with_overrides(self, parser):
        """测试带覆盖的实例化"""
        schema = parser.instantiate(
            "user",
            overrides={"extra_field": "string"},
        )
        
        assert "extra_field" in schema

    def test_variable_replacement(self, parser):
        """测试变量替换"""
        # 创建一个临时模板
        registry = TemplateRegistry()
        registry.register(DataTemplate(
            name="var_test",
            schema={
                "env": "${environment}",
                "version": "{{version}}",
            },
        ))
        
        parser = TemplateParser(registry)
        schema = parser.instantiate(
            "var_test",
            variables={"environment": "prod", "version": "1.0"},
        )
        
        assert schema["env"] == "prod"
        assert schema["version"] == "1.0"


class TestDataMasker:
    """测试数据脱敏"""

    @pytest.fixture
    def masker(self):
        return DataMasker()

    def test_mask_phone(self, masker):
        """测试手机号脱敏"""
        result = masker.mask_phone("13812345678")
        
        assert "138" in result
        assert "5678" in result
        assert "****" in result

    def test_mask_email(self, masker):
        """测试邮箱脱敏"""
        result = masker.mask_email("test@example.com")
        
        assert "t***@example.com" == result

    def test_mask_id_card(self, masker):
        """测试身份证脱敏"""
        result = masker.mask_id_card("110101199001011234")
        
        assert result.startswith("110")
        assert result.endswith("1234")
        assert "***" in result

    def test_mask_name(self, masker):
        """测试姓名脱敏"""
        result = masker.mask_name("张三丰")
        
        assert result[0] == "张"
        assert result[-1] == "丰"
        assert "*" in result

    def test_mask_dict_auto_detect(self, masker):
        """测试自动检测并脱敏字典"""
        data = {
            "username": "testuser",
            "phone": "13812345678",
            "email": "test@example.com",
            "password": "secret123",
            "age": 25,  # 非敏感字段
        }
        
        result = masker.mask(data, auto_detect=True)
        
        assert "****" in result["phone"]
        assert "***" in result["email"]
        assert result["password"] == "********"
        assert result["age"] == 25  # 未变

    def test_mask_list_data(self, masker):
        """测试脱敏列表数据"""
        data = [
            {"phone": "13811111111"},
            {"phone": "13822222222"},
        ]
        
        result = masker.mask(data, auto_detect=True)
        
        assert len(result) == 2
        assert "****" in result[0]["phone"]
        assert "****" in result[1]["phone"]

    def test_mask_strategy_null(self, masker):
        """测试置空策略"""
        result = masker.mask("sensitive", strategy=MaskStrategy.NULL)
        
        assert result == ""

    def test_mask_strategy_hash(self, masker):
        """测试哈希策略"""
        result = masker.mask("sensitive", strategy=MaskStrategy.HASH)
        
        assert len(result) == 16  # SHA256 前 16 位
        assert result != "sensitive"

    def test_mask_strategy_replace(self, masker):
        """测试替换策略"""
        result = masker.mask("sensitive", strategy=MaskStrategy.REPLACE)
        
        assert result == "*" * len("sensitive")

    def test_mask_specific_fields(self, masker):
        """测试指定字段脱敏"""
        data = {
            "phone": "13812345678",
            "custom_field": "should_mask",
            "normal": "should_not_mask",
        }
        
        result = masker.mask(data, fields=["custom_field"], auto_detect=False)
        
        # phone 不在指定列表中，不脱敏
        assert result["phone"] == "13812345678"
        # custom_field 被脱敏
        assert result["custom_field"] != "should_mask"
        # normal 不脱敏
        assert result["normal"] == "should_not_mask"


class TestGlobalInstances:
    """测试全局实例"""

    def test_template_registry_exists(self):
        """测试全局模板注册表"""
        assert template_registry is not None
        assert template_registry.get("user") is not None

    def test_data_masker_exists(self):
        """测试全局脱敏器"""
        assert data_masker is not None
        result = data_masker.mask_phone("13812345678")
        assert "****" in result
