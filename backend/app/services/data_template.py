"""
数据模板系统

提供可复用的数据结构模板
对应 Issue: #DF-005
"""

import re
from typing import Any

import yaml
from loguru import logger


class DataTemplate:
    """
    数据模板
    
    定义可复用的数据结构，支持继承和覆盖
    """
    
    def __init__(
        self,
        name: str,
        schema: dict[str, Any],
        description: str = "",
        extends: str | None = None,
        defaults: dict[str, Any] | None = None,
    ):
        self.name = name
        self.schema = schema
        self.description = description
        self.extends = extends
        self.defaults = defaults or {}
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "schema": self.schema,
            "description": self.description,
            "extends": self.extends,
            "defaults": self.defaults,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DataTemplate":
        """从字典创建"""
        return cls(
            name=data["name"],
            schema=data["schema"],
            description=data.get("description", ""),
            extends=data.get("extends"),
            defaults=data.get("defaults"),
        )


class TemplateRegistry:
    """
    模板注册表
    
    管理和解析数据模板
    """
    
    def __init__(self):
        self._templates: dict[str, DataTemplate] = {}
        self._load_builtin_templates()
    
    def _load_builtin_templates(self):
        """加载内置模板"""
        builtin = {
            "user": {
                "name": "user",
                "description": "用户信息模板",
                "schema": {
                    "id": "uuid",
                    "username": "username",
                    "email": "email",
                    "phone": "phone",
                    "created_at": "datetime",
                },
            },
            "address": {
                "name": "address",
                "description": "地址信息模板",
                "schema": {
                    "province": "chinese_address",
                    "city": "string",
                    "district": "string",
                    "street": "address",
                    "postal_code": {"type": "pattern", "options": {"pattern": "######"}},
                },
            },
            "order": {
                "name": "order",
                "description": "订单信息模板",
                "schema": {
                    "order_id": {"type": "pattern", "options": {"pattern": "ORD-########"}},
                    "user_id": "uuid",
                    "amount": "price",
                    "status": {"type": "enum", "options": {"choices": ["pending", "paid", "shipped", "completed"]}},
                    "created_at": "datetime",
                },
            },
            "product": {
                "name": "product",
                "description": "商品信息模板",
                "schema": {
                    "sku": {"type": "pattern", "options": {"pattern": "SKU-????-####"}},
                    "name": "string",
                    "price": "price",
                    "stock": {"type": "range", "options": {"min": 0, "max": 1000}},
                    "category": {"type": "enum", "options": {"choices": ["电子", "服装", "食品", "家居"]}},
                },
            },
        }
        
        for name, data in builtin.items():
            self._templates[name] = DataTemplate.from_dict(data)
    
    def register(self, template: DataTemplate):
        """注册模板"""
        self._templates[template.name] = template
        logger.debug(f"注册模板: {template.name}")
    
    def get(self, name: str) -> DataTemplate | None:
        """获取模板"""
        return self._templates.get(name)
    
    def list_all(self) -> list[DataTemplate]:
        """列出所有模板"""
        return list(self._templates.values())
    
    def resolve(self, name: str) -> dict[str, Any]:
        """
        解析模板获取完整 schema
        
        处理模板继承
        """
        template = self.get(name)
        if not template:
            raise ValueError(f"模板不存在: {name}")
        
        schema = {}
        
        # 处理继承
        if template.extends:
            parent_schema = self.resolve(template.extends)
            schema.update(parent_schema)
        
        # 合并当前模板
        schema.update(template.schema)
        
        # 应用默认值
        for key, value in template.defaults.items():
            if key in schema:
                if isinstance(schema[key], dict):
                    schema[key]["default"] = value
                else:
                    schema[key] = {"type": schema[key], "default": value}
        
        return schema
    
    def load_from_yaml(self, yaml_content: str):
        """从 YAML 加载模板"""
        try:
            data = yaml.safe_load(yaml_content)
            if isinstance(data, list):
                for item in data:
                    template = DataTemplate.from_dict(item)
                    self.register(template)
            elif isinstance(data, dict):
                template = DataTemplate.from_dict(data)
                self.register(template)
        except Exception as e:
            logger.error(f"加载 YAML 模板失败: {e}")
            raise


class TemplateParser:
    """
    模板解析器
    
    将模板实例化为具体数据
    """
    
    # 变量语法: ${var} 或 {{var}}
    VAR_PATTERN = re.compile(r"\$\{(\w+)\}|{{\s*(\w+)\s*}}")
    
    def __init__(self, registry: TemplateRegistry | None = None):
        self.registry = registry or template_registry
    
    def instantiate(
        self,
        template_name: str,
        overrides: dict[str, Any] | None = None,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        实例化模板
        
        Args:
            template_name: 模板名称
            overrides: 字段覆盖
            variables: 变量值
            
        Returns:
            实例化的 schema
        """
        schema = self.registry.resolve(template_name)
        
        # 应用覆盖
        if overrides:
            schema.update(overrides)
        
        # 替换变量
        if variables:
            schema = self._replace_variables(schema, variables)
        
        return schema
    
    def _replace_variables(
        self,
        obj: Any,
        variables: dict[str, Any],
    ) -> Any:
        """递归替换变量"""
        if isinstance(obj, str):
            def replacer(match):
                var_name = match.group(1) or match.group(2)
                return str(variables.get(var_name, match.group(0)))
            return self.VAR_PATTERN.sub(replacer, obj)
        elif isinstance(obj, dict):
            return {k: self._replace_variables(v, variables) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_variables(item, variables) for item in obj]
        else:
            return obj


# 全局实例
template_registry = TemplateRegistry()
template_parser = TemplateParser()
