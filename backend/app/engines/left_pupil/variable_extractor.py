"""
变量提取器

从 API 响应中提取变量，支持 JSONPath 和正则表达式
对应 Issue: #LP-003
"""

import re
from typing import Any, Optional

from loguru import logger


class VariableExtractor:
    """
    变量提取器
    
    支持:
    - JSONPath 表达式 ($.data.id)
    - 正则表达式 (regex:pattern)
    - 简单路径 (data.items[0].name)
    """
    
    def extract(self, data: Any, rule: str) -> Any:
        """
        从数据中提取值
        
        Args:
            data: 源数据 (通常是 JSON 响应)
            rule: 提取规则
            
        Returns:
            提取的值
        """
        if rule.startswith("regex:"):
            return self._extract_regex(str(data), rule[6:])
        elif rule.startswith("$."):
            return self._extract_jsonpath(data, rule)
        else:
            return self._extract_simple_path(data, rule)
    
    def _extract_jsonpath(self, data: Any, path: str) -> Any:
        """
        JSONPath 提取
        
        支持的语法:
        - $.key - 根对象的 key
        - $.array[0] - 数组索引
        - $.array[*] - 所有数组元素
        - $.obj.nested - 嵌套路径
        - [?(@.price < 10)] - 过滤器 (由 jsonpath-ng 支持)
        """
        try:
            from jsonpath_ng import parse
            jsonpath_expr = parse(path)
            matches = jsonpath_expr.find(data)
            if matches:
                # 如果匹配多个，返回列表；否则返回单个值
                if len(matches) > 1:
                    return [m.value for m in matches]
                return matches[0].value
        except ImportError:
            logger.warning("jsonpath-ng 未安装，回退到简单实现")
        except Exception as e:
            logger.warning(f"jsonpath-ng 提取失败: {path} - {e}, 尝试简单实现")

        try:
            # 移除开头的 $.
            path = path[2:] if path.startswith("$.") else path
            
            # 简单实现，复杂场景可使用 jsonpath-ng 库
            return self._extract_simple_path(data, path)
            
        except Exception as e:
            logger.warning(f"JSONPath 提取失败: {path} - {e}")
            return None
    
    def _extract_simple_path(self, data: Any, path: str) -> Any:
        """
        简单路径提取
        
        支持: data.items[0].name
        """
        if not path:
            return data
        
        current = data
        
        # 分割路径
        parts = self._split_path(path)
        
        for part in parts:
            if current is None:
                return None
            
            if isinstance(part, int):
                # 数组索引
                if isinstance(current, (list, tuple)) and len(current) > part:
                    current = current[part]
                else:
                    return None
            elif part == "*":
                # 通配符 - 返回所有元素
                if isinstance(current, list):
                    return current
                return None
            else:
                # 对象属性
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
        
        return current
    
    def _split_path(self, path: str) -> list:
        """分割路径为部分"""
        parts = []
        current = ""
        
        i = 0
        while i < len(path):
            char = path[i]
            
            if char == ".":
                if current:
                    parts.append(current)
                    current = ""
            elif char == "[":
                if current:
                    parts.append(current)
                    current = ""
                # 查找 ]
                j = path.index("]", i)
                index_str = path[i+1:j]
                if index_str == "*":
                    parts.append("*")
                else:
                    parts.append(int(index_str))
                i = j
            else:
                current += char
            
            i += 1
        
        if current:
            parts.append(current)
        
        return parts
    
    def _extract_regex(self, text: str, pattern: str) -> Optional[str]:
        """
        正则表达式提取
        
        返回第一个捕获组的值
        """
        try:
            match = re.search(pattern, text)
            if match:
                if match.groups():
                    return match.group(1)
                return match.group(0)
            return None
        except Exception as e:
            logger.warning(f"正则提取失败: {pattern} - {e}")
            return None


class VariableStore:
    """
    变量存储
    
    支持多作用域的变量管理
    """
    
    def __init__(self):
        self._global: dict = {}      # 全局变量
        self._session: dict = {}     # 会话变量
        self._step: dict = {}        # 步骤变量
    
    def set(self, name: str, value: Any, scope: str = "step"):
        """设置变量"""
        store = self._get_store(scope)
        store[name] = value
    
    def get(self, name: str, default: Any = None) -> Any:
        """获取变量 (按作用域优先级)"""
        # 优先级: step > session > global
        if name in self._step:
            return self._step[name]
        if name in self._session:
            return self._session[name]
        if name in self._global:
            return self._global[name]
        return default
    
    def clear_step(self):
        """清除步骤变量"""
        self._step.clear()
    
    def clear_session(self):
        """清除会话变量"""
        self._session.clear()
        self._step.clear()
    
    def all(self) -> dict:
        """获取所有变量 (合并)"""
        return {**self._global, **self._session, **self._step}
    
    def _get_store(self, scope: str) -> dict:
        """获取对应作用域的存储"""
        if scope == "global":
            return self._global
        elif scope == "session":
            return self._session
        else:
            return self._step
