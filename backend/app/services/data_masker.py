"""
数据脱敏服务

保护敏感数据，支持多种脱敏策略
对应 Issue: #DF-006
"""

import re
import hashlib
from typing import Any, Callable
from enum import Enum


class MaskStrategy(str, Enum):
    """脱敏策略枚举"""
    MASK = "mask"           # 部分遮盖 (如: 138****8888)
    HASH = "hash"           # 哈希处理
    REPLACE = "replace"     # 完全替换
    SHUFFLE = "shuffle"     # 打乱顺序
    TRUNCATE = "truncate"   # 截断
    NULL = "null"           # 置空


class DataMasker:
    """
    数据脱敏器
    
    提供多种敏感数据脱敏策略
    """
    
    # 敏感字段检测模式
    SENSITIVE_PATTERNS = {
        "phone": re.compile(r"1[3-9]\d{9}"),
        "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
        "id_card": re.compile(r"\d{17}[\dXx]"),
        "bank_card": re.compile(r"\d{16,19}"),
        "password": re.compile(r"password|passwd|pwd|secret", re.IGNORECASE),
        "token": re.compile(r"token|api_key|apikey|access_key", re.IGNORECASE),
    }
    
    # 敏感字段名（用于自动检测）
    SENSITIVE_FIELD_NAMES = {
        "phone", "mobile", "tel", "telephone",
        "email", "mail",
        "id_card", "idcard", "identity",
        "password", "passwd", "pwd", "secret",
        "name", "real_name", "realname", "username",
        "address", "addr",
        "bank_card", "card_no", "account",
        "token", "api_key", "apikey", "access_key", "secret_key",
    }
    
    def __init__(self, default_strategy: MaskStrategy = MaskStrategy.MASK):
        self.default_strategy = default_strategy
        self._custom_maskers: dict[str, Callable] = {}
    
    def register_masker(self, field_type: str, masker: Callable[[str], str]):
        """注册自定义脱敏函数"""
        self._custom_maskers[field_type] = masker
    
    def mask(
        self,
        data: Any,
        strategy: MaskStrategy | None = None,
        fields: list[str] | None = None,
        auto_detect: bool = True,
    ) -> Any:
        """
        脱敏数据
        
        Args:
            data: 要脱敏的数据
            strategy: 脱敏策略
            fields: 指定要脱敏的字段（仅对字典有效）
            auto_detect: 是否自动检测敏感字段
            
        Returns:
            脱敏后的数据
        """
        strategy = strategy or self.default_strategy
        
        if isinstance(data, dict):
            return self._mask_dict(data, strategy, fields, auto_detect)
        elif isinstance(data, list):
            return [self.mask(item, strategy, fields, auto_detect) for item in data]
        elif isinstance(data, str):
            return self._mask_string(data, strategy)
        else:
            return data
    
    def _mask_dict(
        self,
        data: dict,
        strategy: MaskStrategy,
        fields: list[str] | None,
        auto_detect: bool,
    ) -> dict:
        """脱敏字典数据"""
        result = {}
        
        for key, value in data.items():
            should_mask = False
            
            # 检查是否在指定字段列表中
            if fields and key.lower() in [f.lower() for f in fields]:
                should_mask = True
            
            # 自动检测敏感字段
            if auto_detect and not should_mask:
                if key.lower() in self.SENSITIVE_FIELD_NAMES:
                    should_mask = True
            
            if should_mask and isinstance(value, str):
                result[key] = self._mask_string(value, strategy, key)
            elif isinstance(value, (dict, list)):
                result[key] = self.mask(value, strategy, fields, auto_detect)
            else:
                result[key] = value
        
        return result
    
    def _mask_string(
        self,
        value: str,
        strategy: MaskStrategy,
        field_name: str | None = None,
    ) -> str:
        """脱敏字符串"""
        if not value:
            return value
        
        # 使用自定义脱敏器
        if field_name and field_name.lower() in self._custom_maskers:
            return self._custom_maskers[field_name.lower()](value)
        
        # 检测数据类型并应用对应策略
        data_type = self._detect_type(value, field_name)
        
        if strategy == MaskStrategy.NULL:
            return ""
        elif strategy == MaskStrategy.HASH:
            return self._hash_value(value)
        elif strategy == MaskStrategy.REPLACE:
            return "*" * len(value)
        elif strategy == MaskStrategy.TRUNCATE:
            return value[:3] + "..."
        else:  # MASK
            return self._apply_smart_mask(value, data_type)
    
    def _detect_type(self, value: str, field_name: str | None = None) -> str:
        """检测数据类型"""
        if field_name:
            name_lower = field_name.lower()
            if "phone" in name_lower or "mobile" in name_lower:
                return "phone"
            elif "email" in name_lower or "mail" in name_lower:
                return "email"
            elif "id_card" in name_lower or "idcard" in name_lower:
                return "id_card"
            elif "name" in name_lower:
                return "name"
            elif "password" in name_lower or "pwd" in name_lower:
                return "password"
        
        # 正则匹配
        for type_name, pattern in self.SENSITIVE_PATTERNS.items():
            if pattern.fullmatch(value):
                return type_name
        
        return "unknown"
    
    def _apply_smart_mask(self, value: str, data_type: str) -> str:
        """智能遮盖"""
        if data_type == "phone":
            # 138****8888
            if len(value) >= 11:
                return value[:3] + "****" + value[-4:]
        elif data_type == "email":
            # a***@example.com
            parts = value.split("@")
            if len(parts) == 2:
                name = parts[0]
                domain = parts[1]
                if len(name) > 2:
                    return name[0] + "***" + "@" + domain
                return "***@" + domain
        elif data_type == "id_card":
            # 110***********1234
            if len(value) >= 18:
                return value[:3] + "***********" + value[-4:]
        elif data_type == "name":
            # 张*明
            if len(value) >= 2:
                return value[0] + "*" * (len(value) - 2) + value[-1] if len(value) > 2 else value[0] + "*"
        elif data_type == "password":
            return "********"
        
        # 默认遮盖中间部分
        if len(value) <= 4:
            return "*" * len(value)
        return value[:2] + "*" * (len(value) - 4) + value[-2:]
    
    def _hash_value(self, value: str) -> str:
        """哈希处理"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    def mask_phone(self, phone: str) -> str:
        """专门的手机号脱敏"""
        return self._apply_smart_mask(phone, "phone")
    
    def mask_email(self, email: str) -> str:
        """专门的邮箱脱敏"""
        return self._apply_smart_mask(email, "email")
    
    def mask_id_card(self, id_card: str) -> str:
        """专门的身份证脱敏"""
        return self._apply_smart_mask(id_card, "id_card")
    
    def mask_name(self, name: str) -> str:
        """专门的姓名脱敏"""
        return self._apply_smart_mask(name, "name")


# 全局实例
data_masker = DataMasker()
