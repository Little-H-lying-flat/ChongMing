"""
Swagger 解析器单元测试
"""

import pytest
from app.services.left_pupil.swagger_parser import (
    SwaggerParser, ApiEndpoint, SpecFormat
)


class TestSwaggerParser:
    """SwaggerParser 测试"""
    
    @pytest.fixture
    def parser(self):
        return SwaggerParser()
    
    @pytest.fixture
    def openapi3_spec(self):
        """OpenAPI 3.0 示例"""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0",
            },
            "servers": [{"url": "https://api.example.com/v1"}],
            "paths": {
                "/users": {
                    "get": {
                        "summary": "获取用户列表",
                        "tags": ["users"],
                        "parameters": [
                            {
                                "name": "page",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "成功",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/User"},
                                        }
                                    }
                                }
                            }
                        },
                    },
                    "post": {
                        "summary": "创建用户",
                        "tags": ["users"],
                        "security": [{"bearerAuth": []}],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserCreate"},
                                }
                            },
                        },
                        "responses": {
                            "201": {"description": "创建成功"},
                        },
                    },
                },
                "/users/{id}": {
                    "get": {
                        "summary": "获取单个用户",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {"200": {"description": "成功"}},
                    },
                },
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                        },
                    }
                },
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"},
                },
            },
        }
    
    @pytest.fixture
    def swagger2_spec(self):
        """Swagger 2.0 示例"""
        return {
            "swagger": "2.0",
            "info": {"title": "Test API", "version": "1.0"},
            "basePath": "/api",
            "paths": {
                "/login": {
                    "post": {
                        "summary": "登录",
                        "parameters": [
                            {
                                "name": "body",
                                "in": "body",
                                "required": True,
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "password": {"type": "string"},
                                    },
                                },
                            }
                        ],
                        "responses": {"200": {"description": "成功"}},
                    }
                }
            },
        }
    
    def test_detect_openapi3(self, parser, openapi3_spec):
        """测试检测 OpenAPI 3.0"""
        endpoints = parser.parse(openapi3_spec)
        
        assert parser._format == SpecFormat.OPENAPI_3
    
    def test_detect_swagger2(self, parser, swagger2_spec):
        """测试检测 Swagger 2.0"""
        endpoints = parser.parse(swagger2_spec)
        
        assert parser._format == SpecFormat.SWAGGER_2
    
    def test_parse_endpoints(self, parser, openapi3_spec):
        """测试解析端点"""
        endpoints = parser.parse(openapi3_spec)
        
        assert len(endpoints) == 3
        
        # 检查 GET /users
        get_users = next(e for e in endpoints if e.id == "GET /users")
        assert get_users.method == "GET"
        assert get_users.path == "/users"
        assert get_users.summary == "获取用户列表"
        assert "users" in get_users.tags
    
    def test_parse_parameters(self, parser, openapi3_spec):
        """测试解析参数"""
        endpoints = parser.parse(openapi3_spec)
        
        get_users = next(e for e in endpoints if e.id == "GET /users")
        assert len(get_users.parameters) == 1
        assert get_users.parameters[0].name == "page"
        assert get_users.parameters[0].location == "query"
    
    def test_parse_request_body(self, parser, openapi3_spec):
        """测试解析请求体"""
        endpoints = parser.parse(openapi3_spec)
        
        post_users = next(e for e in endpoints if e.id == "POST /users")
        assert post_users.request_body is not None
        assert post_users.request_body.content_type == "application/json"
        assert post_users.request_body.required is True
    
    def test_parse_security(self, parser, openapi3_spec):
        """测试解析认证"""
        endpoints = parser.parse(openapi3_spec)
        
        post_users = next(e for e in endpoints if e.id == "POST /users")
        assert len(post_users.security) == 1
    
    def test_parse_swagger2_body(self, parser, swagger2_spec):
        """测试解析 Swagger 2.0 body 参数"""
        endpoints = parser.parse(swagger2_spec)
        
        login = endpoints[0]
        assert login.request_body is not None
    
    def test_get_info(self, parser, openapi3_spec):
        """测试获取 API 信息"""
        parser.parse(openapi3_spec)
        info = parser.get_info()
        
        assert info["title"] == "Test API"
        assert info["version"] == "1.0.0"
    
    def test_to_searchable_text(self, parser, openapi3_spec):
        """测试生成可搜索文本"""
        endpoints = parser.parse(openapi3_spec)
        
        get_users = next(e for e in endpoints if e.id == "GET /users")
        text = get_users.to_searchable_text()
        
        assert "GET /users" in text
        assert "获取用户列表" in text
