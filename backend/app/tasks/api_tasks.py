"""
API 测试 Celery Worker 任务

对应 Issue: #LP-006
"""

from typing import Any, Dict, List, Optional

from celery import shared_task
from loguru import logger

from app.tasks.base import APITestTask


@shared_task(
    bind=True,
    base=APITestTask,
    name="app.tasks.api_tasks.execute_api_test",
)
def execute_api_test(
    self,
    api_ir: Dict,
    auth_config: Optional[Dict] = None,
    context: Optional[Dict] = None,
) -> Dict:
    """
    执行单个 API 测试
    
    Args:
        api_ir: API 中间表示
        auth_config: 认证配置
        context: 上下文变量
        
    Returns:
        执行结果
    """
    import asyncio
    from app.engines.left_pupil import APIExecutor, AuthConfig, AuthType
    from app.schemas.execution import APIIR
    
    logger.info(f"开始执行 API 测试: {api_ir.get('method')} {api_ir.get('url')}")
    
    # 更新进度
    self.update_progress(0, 1, "准备执行")
    
    try:
        # 构建 APIIR
        ir = APIIR(
            method=api_ir.get("method", "GET"),
            url=api_ir.get("url", ""),
            headers=api_ir.get("headers", {}),
            query_params=api_ir.get("query_params", {}),
            path_params=api_ir.get("path_params", {}),
            body=api_ir.get("body"),
            content_type=api_ir.get("content_type", "application/json"),
            timeout=api_ir.get("timeout", 30.0),
            assertions=api_ir.get("assertions", []),
            extract=api_ir.get("extract", {}),
        )
        
        # 构建认证配置
        auth = None
        if auth_config:
            auth = AuthConfig(
                auth_type=AuthType(auth_config.get("auth_type", "none")),
                token=auth_config.get("token"),
                username=auth_config.get("username"),
                password=auth_config.get("password"),
                api_key_name=auth_config.get("api_key_name"),
                api_key_value=auth_config.get("api_key_value"),
                api_key_location=auth_config.get("api_key_location", "header"),
            )
        
        # 执行
        async def run():
            async with APIExecutor(auth_config=auth) as executor:
                if context:
                    executor.update_context(context)
                return await executor.execute(ir)
        
        result = asyncio.run(run())
        
        # 更新进度
        self.update_progress(1, 1, "执行完成")
        
        return {
            "success": result.success,
            "status_code": result.response.status_code if result.response else None,
            "duration_ms": result.response.duration_ms if result.response else None,
            "body": result.response.body if result.response else None,
            "assertions_passed": result.assertions_passed,
            "assertions_failed": result.assertions_failed,
            "extracted_values": result.extracted_values,
            "error": result.error,
        }
        
    except Exception as e:
        logger.error(f"API 测试执行失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@shared_task(
    bind=True,
    base=APITestTask,
    name="app.tasks.api_tasks.execute_api_chain",
)
def execute_api_chain(
    self,
    chain: List[Dict],
    auth_config: Optional[Dict] = None,
    initial_context: Optional[Dict] = None,
) -> Dict:
    """
    执行 API 链式调用
    
    Args:
        chain: API-IR 列表
        auth_config: 认证配置
        initial_context: 初始上下文
        
    Returns:
        链式执行结果
    """
    import asyncio
    from app.engines.left_pupil import APIExecutor, AuthConfig, AuthType
    from app.schemas.execution import APIIR
    
    logger.info(f"开始执行 API 链: {len(chain)} 个请求")
    
    results = []
    context = initial_context or {}
    
    # 构建认证配置
    auth = None
    if auth_config:
        auth = AuthConfig(
            auth_type=AuthType(auth_config.get("auth_type", "none")),
            token=auth_config.get("token"),
            username=auth_config.get("username"),
            password=auth_config.get("password"),
            api_key_name=auth_config.get("api_key_name"),
            api_key_value=auth_config.get("api_key_value"),
            api_key_location=auth_config.get("api_key_location", "header"),
        )
    
    async def run_chain():
        nonlocal context
        async with APIExecutor(auth_config=auth) as executor:
            executor.update_context(context)
            
            for i, api_ir in enumerate(chain):
                # 更新进度
                self.update_progress(i, len(chain), f"执行第 {i+1}/{len(chain)} 个请求")
                
                ir = APIIR(
                    method=api_ir.get("method", "GET"),
                    url=api_ir.get("url", ""),
                    headers=api_ir.get("headers", {}),
                    query_params=api_ir.get("query_params", {}),
                    path_params=api_ir.get("path_params", {}),
                    body=api_ir.get("body"),
                    content_type=api_ir.get("content_type", "application/json"),
                    assertions=api_ir.get("assertions", []),
                    extract=api_ir.get("extract", {}),
                )
                
                result = await executor.execute(ir)
                
                # 更新上下文
                context.update(result.extracted_values)
                
                results.append({
                    "step": i + 1,
                    "url": api_ir.get("url"),
                    "method": api_ir.get("method"),
                    "success": result.success,
                    "status_code": result.response.status_code if result.response else None,
                    "duration_ms": result.response.duration_ms if result.response else None,
                    "assertions_passed": result.assertions_passed,
                    "assertions_failed": result.assertions_failed,
                    "extracted_values": result.extracted_values,
                    "error": result.error,
                })
                
                # 如果失败且配置了 stop_on_failure
                if not result.success and api_ir.get("stop_on_failure", True):
                    break
    
    asyncio.run(run_chain())
    
    # 更新进度
    self.update_progress(len(chain), len(chain), "链式执行完成")
    
    # 统计
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    
    return {
        "total": len(chain),
        "executed": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
        "final_context": context,
    }


@shared_task(
    bind=True,
    base=APITestTask,
    name="app.tasks.api_tasks.parse_swagger",
)
def parse_swagger(self, swagger_url: str) -> Dict:
    """
    解析 Swagger 文档
    
    Args:
        swagger_url: Swagger 文档 URL
        
    Returns:
        API 规格
    """
    import asyncio
    from app.engines.left_pupil import SwaggerParser
    
    logger.info(f"解析 Swagger 文档: {swagger_url}")
    
    async def run():
        parser = SwaggerParser()
        spec = await parser.load_from_url(swagger_url)
        return spec
    
    spec = asyncio.run(run())
    
    return {
        "title": spec.title,
        "version": spec.version,
        "description": spec.description,
        "base_url": spec.base_url,
        "endpoints_count": len(spec.endpoints),
        "endpoints": [
            {
                "path": e.path,
                "method": e.method,
                "summary": e.summary,
                "tags": e.tags,
            }
            for e in spec.endpoints
        ],
    }
