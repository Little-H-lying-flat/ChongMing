"""
左瞳引擎端到端集成测试

测试完整的 API 测试流程：
1. Swagger 解析
2. API 执行
3. 断言验证

注意：ChromaDB 相关测试因兼容性问题暂时跳过
"""

import pytest
import json

from app.services.left_pupil.swagger_parser import SwaggerParser
from app.services.left_pupil.context_memory import ContextMemory
from app.services.left_pupil.asserter import Asserter, create_rules_from_dict
from app.services.left_pupil.api_runner import ApiRunner, ApiIRStep, RequestSpec
from app.models.api_ir import ApiIR, ApiIRChain, create_api_ir


# 测试用 OpenAPI 规范
SAMPLE_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://jsonplaceholder.typicode.com"}],
    "paths": {
        "/posts": {
            "get": {
                "summary": "获取文章列表",
                "operationId": "getPosts",
                "tags": ["posts"],
                "parameters": [
                    {
                        "name": "_limit",
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
                                    "items": {"$ref": "#/components/schemas/Post"},
                                }
                            }
                        },
                    }
                },
            },
            "post": {
                "summary": "创建文章",
                "operationId": "createPost",
                "tags": ["posts"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PostCreate"},
                        }
                    },
                },
                "responses": {"201": {"description": "创建成功"}},
            },
        },
        "/posts/{id}": {
            "get": {
                "summary": "获取单篇文章",
                "operationId": "getPost",
                "tags": ["posts"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {"200": {"description": "成功"}},
            },
        },
        "/users": {
            "get": {
                "summary": "获取用户列表",
                "operationId": "getUsers",
                "tags": ["users"],
                "responses": {"200": {"description": "成功"}},
            },
        },
        "/users/{id}": {
            "get": {
                "summary": "获取单个用户",
                "operationId": "getUser",
                "tags": ["users"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {"200": {"description": "成功"}},
            },
        },
    },
    "components": {
        "schemas": {
            "Post": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "userId": {"type": "integer"},
                },
            },
            "PostCreate": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "userId": {"type": "integer"},
                },
            },
        },
    },
}


class TestSwaggerParsingFlow:
    """Swagger 解析流程测试"""
    
    def test_parse_openapi_spec(self):
        """测试解析 OpenAPI 规范"""
        parser = SwaggerParser()
        endpoints = parser.parse(SAMPLE_OPENAPI_SPEC)
        
        assert len(endpoints) == 5
        
        # 验证端点
        endpoint_ids = [e.id for e in endpoints]
        assert "GET /posts" in endpoint_ids
        assert "POST /posts" in endpoint_ids
        assert "GET /posts/{id}" in endpoint_ids
        assert "GET /users" in endpoint_ids
        assert "GET /users/{id}" in endpoint_ids
    
    def test_parse_from_file(self, tmp_path):
        """测试从文件解析"""
        # 写入临时文件
        spec_file = tmp_path / "openapi.json"
        spec_file.write_text(json.dumps(SAMPLE_OPENAPI_SPEC), encoding="utf-8")
        
        parser = SwaggerParser()
        endpoints = parser.parse_file(str(spec_file))
        
        assert len(endpoints) == 5
    
    def test_endpoint_metadata(self):
        """测试端点元数据"""
        parser = SwaggerParser()
        endpoints = parser.parse(SAMPLE_OPENAPI_SPEC)
        
        post_posts = next(e for e in endpoints if e.id == "POST /posts")
        
        assert post_posts.request_body is not None
        assert post_posts.request_body.required is True
        assert "posts" in post_posts.tags


class TestApiRunnerFlow:
    """API 执行流程测试"""
    
    @pytest.fixture
    def memory(self):
        return ContextMemory()
    
    @pytest.fixture
    def runner(self, memory):
        return ApiRunner(
            base_url="https://jsonplaceholder.typicode.com",
            memory=memory,
        )
    
    @pytest.mark.asyncio
    async def test_simple_get_request(self, runner):
        """测试简单 GET 请求"""
        step = ApiIRStep(
            id="STEP_01",
            name="获取文章列表",
            request=RequestSpec(
                method="GET",
                url="/posts",
                query_params={"_limit": "3"},
            ),
            extraction={"first_post_id": "$.0.id"},
            assertion={
                "status_code": 200,
                "expression": "isinstance(response, list) and len(response) > 0",
            },
        )
        
        result = await runner.execute(step)
        
        assert result.status == "passed"
        assert result.status_code == 200
        assert "first_post_id" in result.extracted_values
        
        await runner.close()
    
    @pytest.mark.asyncio
    async def test_get_single_resource(self, runner):
        """测试获取单个资源"""
        step = ApiIRStep(
            id="STEP_01",
            name="获取单篇文章",
            request=RequestSpec(
                method="GET",
                url="/posts/1",
            ),
            assertion={
                "status_code": 200,
                "json_assertions": {
                    "$.id": 1,
                },
            },
        )
        
        result = await runner.execute(step)
        
        assert result.status == "passed"
        assert result.response_body.get("id") == 1
        
        await runner.close()
    
    @pytest.mark.asyncio
    async def test_variable_injection(self, runner, memory):
        """测试变量注入"""
        # 预设变量
        memory.set("post_id", 1)
        
        step = ApiIRStep(
            id="STEP_01",
            name="获取指定文章",
            request=RequestSpec(
                method="GET",
                url="/posts/${post_id}",
            ),
            assertion={"status_code": 200},
        )
        
        result = await runner.execute(step)
        
        assert result.status == "passed"
        
        await runner.close()
    
    @pytest.mark.asyncio
    async def test_post_request(self, runner):
        """测试 POST 请求"""
        step = ApiIRStep(
            id="STEP_01",
            name="创建文章",
            request=RequestSpec(
                method="POST",
                url="/posts",
                headers={"Content-Type": "application/json"},
                body={
                    "title": "测试标题",
                    "body": "测试内容",
                    "userId": 1,
                },
            ),
            extraction={"new_post_id": "$.id"},
            assertion={
                "status_code": 201,
                "json_assertions": {
                    "$.title": "测试标题",
                },
            },
        )
        
        result = await runner.execute(step)
        
        assert result.status == "passed"
        assert result.status_code == 201
        assert "new_post_id" in result.extracted_values
        
        await runner.close()
    
    @pytest.mark.asyncio
    async def test_multi_step_flow(self, runner, memory):
        """测试多步骤流程"""
        # Step 1: 获取用户
        step1 = ApiIRStep(
            id="STEP_01",
            name="获取用户",
            request=RequestSpec(method="GET", url="/users/1"),
            extraction={"user_id": "$.id", "username": "$.username"},
            assertion={"status_code": 200},
        )
        
        result1 = await runner.execute(step1)
        assert result1.status == "passed"
        # 从提取结果验证
        assert result1.extracted_values.get("user_id") == 1
        
        # Step 2: 使用 user_id 创建文章
        step2 = ApiIRStep(
            id="STEP_02",
            name="创建文章",
            request=RequestSpec(
                method="POST",
                url="/posts",
                body={
                    "title": "由 ${username} 创建",
                    "body": "内容",
                    "userId": "${user_id}",
                },
            ),
            assertion={"status_code": 201},
        )
        
        result2 = await runner.execute(step2)
        assert result2.status == "passed"
        
        await runner.close()


class TestApiIRModel:
    """API-IR 模型测试"""
    
    def test_create_api_ir(self):
        """测试创建 API-IR"""
        api_ir = create_api_ir(
            method="POST",
            url="/api/login",
            name="用户登录",
            headers={"Content-Type": "application/json"},
            body={"username": "test", "password": "123"},
            extraction={"token": "$.data.token"},
            assertion={"status_code": 200},
        )
        
        assert api_ir.request.method == "POST"
        assert api_ir.request.url == "/api/login"
        assert api_ir.extraction.get("token") == "$.data.token"
    
    def test_api_ir_chain(self):
        """测试 API-IR 执行链"""
        chain = ApiIRChain(
            id="CHAIN_001",
            name="用户登录并获取信息",
        )
        
        # 添加步骤
        chain.add_step(create_api_ir("POST", "/login", name="登录"))
        chain.add_step(create_api_ir("GET", "/users/me", name="获取用户信息"))
        
        assert len(chain.steps) == 2
        
        # 序列化
        data = chain.to_dict()
        assert data["total_steps"] == 2
    
    def test_api_ir_from_dict(self):
        """测试从字典创建 API-IR"""
        data = {
            "id": "STEP_01",
            "name": "测试步骤",
            "request": {
                "method": "GET",
                "url": "/test",
                "headers": {"Authorization": "Bearer token"},
            },
            "assertion": {
                "status_code": 200,
            },
        }
        
        api_ir = ApiIR.from_dict(data)
        
        assert api_ir.id == "STEP_01"
        assert api_ir.request.method == "GET"
        assert api_ir.assertion.status_code == 200


class TestEndToEndFlow:
    """端到端完整流程测试（不依赖 ChromaDB）"""
    
    @pytest.mark.asyncio
    async def test_full_api_test_flow(self):
        """测试完整的 API 测试流程"""
        # 1. 解析 API 文档
        parser = SwaggerParser()
        endpoints = parser.parse(SAMPLE_OPENAPI_SPEC)
        assert len(endpoints) == 5
        
        # 2. 初始化执行组件
        memory = ContextMemory()
        runner = ApiRunner(
            base_url="https://jsonplaceholder.typicode.com",
            memory=memory,
        )
        
        # 3. 构建并执行第一步：获取用户列表
        step1 = ApiIRStep(
            id="STEP_01",
            name="获取用户列表",
            request=RequestSpec(method="GET", url="/users"),
            extraction={"first_user_id": "$.0.id", "first_user_name": "$.0.name"},
            assertion={"status_code": 200, "expression": "isinstance(response, list) and len(response) > 0"},
        )
        
        result1 = await runner.execute(step1)
        assert result1.status == "passed"
        
        # 4. 验证变量提取
        first_user_id = result1.extracted_values.get("first_user_id")
        assert first_user_id is not None
        
        # 5. 使用提取的变量执行下一步
        step2 = ApiIRStep(
            id="STEP_02",
            name="获取单个用户详情",
            request=RequestSpec(method="GET", url="/users/${first_user_id}"),
            extraction={"user_email": "$.email"},
            assertion={
                "status_code": 200,
                "json_assertions": {"$.id": {"type": "exists"}},
            },
        )
        
        result2 = await runner.execute(step2)
        assert result2.status == "passed"
        
        # 6. 使用用户信息创建文章
        step3 = ApiIRStep(
            id="STEP_03",
            name="创建文章",
            request=RequestSpec(
                method="POST",
                url="/posts",
                body={
                    "title": "来自 ${first_user_name} 的文章",
                    "body": "这是由用户 ${first_user_id} 创建的内容",
                    "userId": "${first_user_id}",
                },
            ),
            extraction={"new_post_id": "$.id"},
            assertion={"status_code": 201},
        )
        
        result3 = await runner.execute(step3)
        assert result3.status == "passed"
        
        # 7. 验证所有结果
        all_results = runner.get_results()
        assert len(all_results) == 3
        assert all(r.status == "passed" for r in all_results)
        
        # 8. 验证变量链 - 从各个步骤的提取结果验证
        assert result1.extracted_values.get("first_user_id") is not None
        assert result1.extracted_values.get("first_user_name") is not None
        assert result2.extracted_values.get("user_email") is not None
        assert result3.extracted_values.get("new_post_id") is not None
        
        # 9. 清理
        await runner.close()
    
    @pytest.mark.asyncio
    async def test_assertion_failure_handling(self):
        """测试断言失败处理"""
        memory = ContextMemory()
        runner = ApiRunner(
            base_url="https://jsonplaceholder.typicode.com",
            memory=memory,
        )
        
        step = ApiIRStep(
            id="STEP_01",
            name="故意失败的断言",
            request=RequestSpec(method="GET", url="/posts/1"),
            assertion={
                "status_code": 404,  # 期望 404，但实际是 200
            },
        )
        
        result = await runner.execute(step)
        
        assert result.status == "failed"
        assert result.status_code == 200  # 实际状态码
        assert result.assertion_report is not None
        assert not result.assertion_report.passed
        
        await runner.close()
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """测试连接错误处理"""
        memory = ContextMemory()
        runner = ApiRunner(
            base_url="https://nonexistent-domain-12345.invalid",
            memory=memory,
        )
        
        step = ApiIRStep(
            id="STEP_01",
            name="连接不存在的服务器",
            request=RequestSpec(method="GET", url="/test"),
        )
        
        result = await runner.execute(step)
        
        assert result.status == "error"
        assert result.error is not None
        
        await runner.close()
