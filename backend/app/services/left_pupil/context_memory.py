"""
上下文内存管理

管理跨 API 调用的变量传递和模板注入
"""

import re
from datetime import datetime, UTC
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class VariableRecord:
    """变量记录"""
    key: str
    value: Any
    source: str  # 来源步骤 ID
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class ContextMemory:
    """
    上下文内存
    
    管理跨步骤的变量存储和模板注入
    """
    
    def __init__(self):
        self._store: dict[str, Any] = {}
        self._history: list[VariableRecord] = []
        self._aliases: dict[str, str] = {}  # 变量别名
    
    def set(self, key: str, value: Any, source: str = "manual") -> None:
        """
        设置变量
        
        Args:
            key: 变量名
            value: 变量值
            source: 来源步骤 ID
        """
        self._store[key] = value
        self._history.append(VariableRecord(
            key=key,
            value=value,
            source=source,
        ))
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取变量值
        
        Args:
            key: 变量名
            default: 默认值
        
        Returns:
            变量值或默认值
        """
        # 检查别名
        actual_key = self._aliases.get(key, key)
        return self._store.get(actual_key, default)
    
    def delete(self, key: str) -> bool:
        """删除变量"""
        if key in self._store:
            del self._store[key]
            return True
        return False
    
    def has(self, key: str) -> bool:
        """检查变量是否存在"""
        actual_key = self._aliases.get(key, key)
        return actual_key in self._store
    
    def set_alias(self, alias: str, target: str) -> None:
        """设置变量别名"""
        self._aliases[alias] = target
    
    def _to_json_str(self, value: Any) -> str:
        """转换为 JSON 安全的字符串表示"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def inject(self, template: str) -> str:
        """
        将模板中的变量占位符替换为实际值
        
        支持语法：
        - ${var} - 标准语法
        - {{var}} - 双花括号语法
        - ${var:default} - 带默认值语法
        
        Args:
            template: 包含占位符的模板字符串
        
        Returns:
            替换后的字符串
        """
        result = template
        
        # 处理 ${var} 和 ${var:default} 语法
        pattern_dollar = r'\$\{([^}:]+)(?::([^}]*))?\}'
        for match in re.finditer(pattern_dollar, template):
            var_name = match.group(1)
            default_value = match.group(2) or ""
            value = self.get(var_name, default_value)
            result = result.replace(match.group(0), self._to_json_str(value))
        
        # 处理 {{var}} 语法
        pattern_brace = r'\{\{([^}]+)\}\}'
        for match in re.finditer(pattern_brace, result):
            var_name = match.group(1).strip()
            value = self.get(var_name, "")
            result = result.replace(match.group(0), self._to_json_str(value))
        
        return result
    
    def inject_dict(self, data: dict) -> dict:
        """
        递归注入字典中的变量
        
        Args:
            data: 包含变量占位符的字典
        
        Returns:
            替换后的字典
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.inject(value)
            elif isinstance(value, dict):
                result[key] = self.inject_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.inject(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result
    
    def to_dict(self) -> dict[str, Any]:
        """导出所有变量"""
        return dict(self._store)
    
    def from_dict(self, data: dict[str, Any], source: str = "import") -> None:
        """批量导入变量"""
        for key, value in data.items():
            self.set(key, value, source=source)
    
    def clear(self) -> None:
        """清空所有变量"""
        self._store.clear()
        self._history.clear()
        self._aliases.clear()
    
    def get_history(self, key: Optional[str] = None) -> list[VariableRecord]:
        """
        获取变量历史
        
        Args:
            key: 可选，指定变量名过滤
        
        Returns:
            变量记录列表
        """
        if key:
            return [r for r in self._history if r.key == key]
        return list(self._history)
    
    def __len__(self) -> int:
        return len(self._store)
    
    def __contains__(self, key: str) -> bool:
        return self.has(key)
    
    def __getitem__(self, key: str) -> Any:
        return self.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)
