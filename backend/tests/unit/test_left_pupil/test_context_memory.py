"""
上下文内存单元测试
"""

import pytest
from app.services.left_pupil.context_memory import ContextMemory


class TestContextMemory:
    """ContextMemory 测试"""
    
    def test_set_and_get(self):
        """测试设置和获取变量"""
        memory = ContextMemory()
        
        memory.set("token", "abc123", source="login")
        
        assert memory.get("token") == "abc123"
        assert memory.has("token")
        assert "token" in memory
    
    def test_get_default(self):
        """测试默认值"""
        memory = ContextMemory()
        
        assert memory.get("nonexistent") is None
        assert memory.get("nonexistent", "default") == "default"
    
    def test_delete(self):
        """测试删除"""
        memory = ContextMemory()
        memory.set("key", "value")
        
        assert memory.delete("key")
        assert not memory.has("key")
        assert not memory.delete("nonexistent")
    
    def test_inject_dollar_syntax(self):
        """测试 ${var} 语法注入"""
        memory = ContextMemory()
        memory.set("user_id", "123")
        memory.set("token", "Bearer abc")
        
        template = "User ${user_id} with token ${token}"
        result = memory.inject(template)
        
        assert result == "User 123 with token Bearer abc"
    
    def test_inject_brace_syntax(self):
        """测试 {{var}} 语法注入"""
        memory = ContextMemory()
        memory.set("name", "张三")
        
        template = "Hello {{name}}"
        result = memory.inject(template)
        
        assert result == "Hello 张三"
    
    def test_inject_with_default(self):
        """测试带默认值的注入"""
        memory = ContextMemory()
        
        template = "${missing:default_value}"
        result = memory.inject(template)
        
        assert result == "default_value"
    
    def test_inject_dict(self):
        """测试字典注入"""
        memory = ContextMemory()
        memory.set("base_url", "https://api.example.com")
        memory.set("token", "abc")
        
        data = {
            "url": "${base_url}/users",
            "headers": {
                "Authorization": "Bearer ${token}",
            },
        }
        
        result = memory.inject_dict(data)
        
        assert result["url"] == "https://api.example.com/users"
        assert result["headers"]["Authorization"] == "Bearer abc"
    
    def test_alias(self):
        """测试别名"""
        memory = ContextMemory()
        memory.set("access_token", "xyz")
        memory.set_alias("token", "access_token")
        
        assert memory.get("token") == "xyz"
    
    def test_from_dict(self):
        """测试批量导入"""
        memory = ContextMemory()
        
        memory.from_dict({
            "a": 1,
            "b": "hello",
            "c": True,
        })
        
        assert len(memory) == 3
        assert memory.get("a") == 1
        assert memory.get("b") == "hello"
    
    def test_history(self):
        """测试历史记录"""
        memory = ContextMemory()
        
        memory.set("token", "v1", source="step1")
        memory.set("token", "v2", source="step2")
        
        history = memory.get_history("token")
        
        assert len(history) == 2
        assert history[0].value == "v1"
        assert history[1].value == "v2"
    
    def test_clear(self):
        """测试清空"""
        memory = ContextMemory()
        memory.set("a", 1)
        memory.set("b", 2)
        
        memory.clear()
        
        assert len(memory) == 0
