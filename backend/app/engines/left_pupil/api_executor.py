"""
API-IR 执行器

执行 API 中间表示，发送 HTTP 请求
V3.0 (LangGraph + AutoGen)
"""

from typing import Any, Dict, List, Optional
import re
import time
import json
import traceback

import httpx
from loguru import logger

from app.schemas.api_ir import APIIR, APIResponse, AuthConfig, AuthType, ExecutionResult
from app.utils.context_injector import render_string, render_context, extract_values
from app.engines.left_pupil.state import ApiAgentState

class APIExecutor:
    """
    API-IR 执行器 (LangGraph V3.0)
    
    功能:
    - HTTP 请求发送 (node_execute)
    - 断言解析和结果验证 (node_evaluate)
    - 智能自愈与重试 (node_sherlock, node_healer)
    - 生命周期清理 (node_janitor)
    - 安全侦查 (node_red_team)
    """
    
    def __init__(
        self,
        auth_config: Optional[AuthConfig] = None,
        default_headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ):
        self.auth_config = auth_config or AuthConfig()
        self.default_headers = default_headers or {}
        self.timeout = timeout
        self._context: Dict[str, Any] = {}
        self._client: Optional[httpx.AsyncClient] = None
        
        from app.engines.left_pupil.graph import create_left_pupil_graph
        self.graph = create_left_pupil_graph(self)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._client = httpx.AsyncClient(timeout=self.timeout, trust_env=False)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self._client:
            await self._client.aclose()
    
    def set_context(self, key: str, value: Any):
        """设置上下文变量"""
        self._context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文变量"""
        return self._context.get(key, default)
    
    def update_context(self, values: Dict[str, Any]):
        """批量更新上下文"""
        self._context.update(values)
    
    async def execute(self, api_ir: APIIR, context: Dict[str, Any] = None) -> ExecutionResult:
        """图执行入口"""
        active_context = context if context is not None else self._context
        
        import copy
        api_ir_copy = copy.deepcopy(api_ir)
        
        initial_state: ApiAgentState = {
            "api_ir": api_ir_copy,
            "context": active_context,
            "response": None,
            "extracted_values": {},
            "assertions_passed": [],
            "assertions_failed": [],
            "error": None,
            "failure_type": None,
            "retry_count": 0,
            "max_retries": 1, 
            "created_resources": [],
            "security_report": []
        }
        
        logger.info(f"🚀 开始执行 API 工作流: {api_ir.method} {api_ir.url}")
        final_state = await self.graph.ainvoke(initial_state)
        
        # Merge extracted context back
        extracted = final_state.get("extracted_values", {})
        if extracted:
            active_context.update(extracted)
            if context is None:
                self._context.update(extracted)
                
        # Calculate final success
        assertions_failed = final_state.get("assertions_failed", [])
        error = final_state.get("error")
        success = len(assertions_failed) == 0 and not error
        
        return ExecutionResult(
            success=success,
            response=final_state.get("response"),
            assertions_passed=final_state.get("assertions_passed", []),
            assertions_failed=assertions_failed,
            extracted_values=extracted,
            error=error
        )

    # ================= LangGraph Nodes =================
    
    async def node_execute(self, state: ApiAgentState) -> Dict[str, Any]:
        """Node: 构造并发送 HTTP 请求"""
        api_ir = state["api_ir"]
        active_context = state["context"]
        start_time = time.time()
        
        try:
            # 1. 变量替换
            url = self._replace_variables(api_ir.url, active_context)
            url = self._replace_path_params(url, api_ir.path_params, active_context)
            headers = self._build_headers(api_ir, active_context)
            body = self._replace_variables_in_obj(api_ir.body, active_context) if api_ir.body else None
            params = {k: self._replace_variables(str(v), active_context) for k, v in api_ir.query_params.items()}
            
            # URL 洗清
            if not url:
                raise ValueError("解析到的 URL 为空！")
            if not url.startswith(("http://", "https://")):
                protocol = "http://" if "localhost" in url or "127.0.0.1" in url else "https://"
                url = f"{protocol}{url}"

            # Safety Net (检测未注入变量)
            unreplaced = re.findall(r'\$\{(\w+)\}', url)
            if unreplaced:
                err = f"变量注入失败: 未替换的变量 {unreplaced}"
                logger.error(f"🛡️ {err}")
                return {"error": err, "failure_type": "DATA_FORMAT_ERROR"}

            logger.info(f"发送请求: {api_ir.method} {url}")
            
            if not self._client:
                self._client = httpx.AsyncClient(timeout=self.timeout, trust_env=False)
            
            response = await self._client.request(
                method=api_ir.method,
                url=url,
                headers=headers,
                params=params,
                json=body if api_ir.content_type == "application/json" else None,
                content=body if api_ir.content_type != "application/json" else None,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            try:
                response_body = response.json()
            except:
                response_body = response.text
                
            api_response = APIResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response_body,
                raw_body=response.content,
                duration_ms=duration_ms,
                request_url=url,
                request_method=api_ir.method,
            )
            
            # 变量提取
            extracted = self._extract_values(response_body, api_ir.extract)
            for k, v in extracted.items():
                logger.info(f"🧬 成功提取变量: {k} = {v}")
                active_context[k] = v  # update context in state explicitly
                
            return {
                "response": api_response,
                "extracted_values": extracted,
                "context": active_context,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"API 请求失败: {e}")
            logger.debug(traceback.format_exc())
            return {"error": f"Execution failed: {str(e)}", "failure_type": "EXECUTION_ERROR"}

    async def node_evaluate(self, state: ApiAgentState) -> Dict[str, Any]:
        """Node: 执行业务断言和状态码校验"""
        if state.get("error"):
            # If execute node failed outright, pass through to sherlock
            return {}
            
        api_ir = state["api_ir"]
        api_response = state["response"]
        
        # Track POST/PUT resources for Janitor
        # Using a simple heuristic for now: IF POST AND 200-201 AND response contains 'id', track it.
        created_resources = list(state.get("created_resources", []))
        if api_ir.method in ["POST", "PUT"] and api_response and 200 <= api_response.status_code < 300:
             body = api_response.body
             if isinstance(body, dict) and ("id" in body or "data" in body):
                 # Very naive tracking, will be expanded
                 created_resources.append({
                     "method": api_ir.method,
                     "url": api_response.request_url,
                     "response_body": body
                 })
        
        from app.engines.left_pupil.assertion_engine import AssertionEngine
        assertion_engine = AssertionEngine()
        
        status_error = None
        expected_code = getattr(api_ir, "expected_status_code", None)
        actual_code = api_response.status_code
        
        if expected_code is not None:
            if actual_code != expected_code:
                status_error = f"Status Code Mismatch: Expected {expected_code}, got {actual_code}"
        else:
            has_explicit_status = any(a.get("type") == "status_code" for a in getattr(api_ir, "assertions", []))
            if not has_explicit_status and not (200 <= actual_code < 300):
                status_error = f"HTTP Status Error: Expected 2xx, got {actual_code}"

        deep_json_failures = []
        json_assertions = getattr(api_ir, "json_assertions", {})
        if json_assertions:
            resp_json = api_response.body
            if isinstance(resp_json, (dict, list)):
                for key, expected_val in json_assertions.items():
                    actual_val = None
                    if isinstance(resp_json, dict):
                        actual_val = resp_json.get(key)
                        if actual_val is None and "." in key:
                            parts = key.split(".")
                            temp = resp_json
                            for p in parts:
                                if isinstance(temp, dict): temp = temp.get(p)
                                else: temp = None; break
                            actual_val = temp
                    
                    if str(actual_val) != str(expected_val):
                        deep_json_failures.append(f"JSON Mismatch at '{key}': Expected '{expected_val}', got '{actual_val}'")
            else:
                deep_json_failures.append(f"Expected JSON body for assertions")

        assertion_result = assertion_engine.run_assertions(api_ir.assertions, api_response)
        
        failed = []
        if status_error: failed.append(status_error)
        failed.extend(deep_json_failures)
        failed.extend(assertion_result["failed"])
        
        return {
            "assertions_passed": assertion_result["passed"],
            "assertions_failed": failed,
            "created_resources": created_resources
        }
        
    async def node_sherlock(self, state: ApiAgentState) -> Dict[str, Any]:
        """Node: RCA Agent"""
        from app.core.config import settings
        import autogen
        import asyncio
        from app.engines.left_pupil.agents.api_sherlock import APISherlockAgent
        from app.utils.autogen_runtime import get_autogen_runtime_status
        
        logger.info("🕵️ Sherlock analyzing error...")
        
        autogen_status = get_autogen_runtime_status()
        if not autogen_status.available:
            logger.warning(f"Skipping AutoGen API Sherlock: {autogen_status.reason}")
            return {"failure_type": "UNKNOWN_ERROR"}

        from app.services.smart_ops.ai_config_service import AIConfigService
        from app.core.ai_models import AIModule
        
        cfg = await AIConfigService.get_model_config(AIModule.AGENT_LEFT_SHERLOCK)
        llm_config = {
            "config_list": [{
                "model": cfg.model_id,
                "api_key": settings.QWEN_API_KEY,
                "base_url": settings.QWEN_BASE_URL
            }],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        
        sherlock = APISherlockAgent("接口诊断专家_Sherlock", llm_config)
        admin = autogen.UserProxyAgent("Admin", human_input_mode="NEVER", code_execution_config=False, max_consecutive_auto_reply=1)
        
        import dataclasses
        prompt = f"""
        Original API Intent: {json.dumps(dataclasses.asdict(state['api_ir']), ensure_ascii=False)}
        HTTP Response Status: {state['response'].status_code if state['response'] else 'None'}
        HTTP Response Body: {state['response'].body if state['response'] else 'None'}
        Assertion Errors: {json.dumps(state['assertions_failed'], ensure_ascii=False)}
        System Error: {state['error'] if state['error'] else 'None'}
        
        CRITICAL INSTRUCTION: Do NOT use the `search_knowledge_base` tool or any other tools. 
        You must diagnose this error using ONLY the provided context above. 
        Output the JSON diagnostic block immediately.
        """
        
        await admin.a_initiate_chat(sherlock, message=prompt)
        
        # Extract JSON from sherlock response
        try:
            last_msg = ""
            # Iterate backwards to find the last message with content
            for msg in reversed(admin.chat_messages[sherlock]):
                if msg.get("content"):
                    last_msg = msg["content"]
                    break
                    
            if not last_msg:
                # Fallback if content was empty (e.g. only tool call)
                raise ValueError("No text content found in Sherlock response")
                
            json_str = last_msg[last_msg.find("{"):last_msg.rfind("}")+1]
            try:
                res = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback regex extraction if model hallucinated format
                failure_match = re.search(r'"failure_type"\s*:\s*"([^"]+)"', last_msg)
                reason_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', last_msg)
                res = {
                    "failure_type": failure_match.group(1) if failure_match else "UNKNOWN",
                    "reasoning": reason_match.group(1) if reason_match else "Unparseable response"
                }

            failure_type = res.get("failure_type", "UNKNOWN")
            logger.info(f"Sherlock Diagnosis: {failure_type} ({res.get('reasoning', '')})")
            
            # Scribe: Save Memory of the API Diagnosis
            from app.core.memory_base import memory_base
            user_id = state.get("context", {}).get("project_id", "default_user")
            status_code = state['response'].status_code if state.get('response') else 'None'
            memory_base.add_memory(
                content=f"API 缺陷诊断经验: 遇到报错 {state.get('error')} 且状态码 {status_code} 时，根因为 {failure_type}。推理: {res.get('reasoning', '')}",
                user_id=user_id,
                project_id=user_id
            )
            
            return {"failure_type": failure_type}
        except Exception as e:
            logger.error(f"Sherlock parsing failed: {e}")
            return {"failure_type": "UNKNOWN_ERROR"}

    async def node_healer(self, state: ApiAgentState) -> Dict[str, Any]:
        """Node: Healing Agent"""
        from app.core.config import settings
        import autogen
        import asyncio
        from app.engines.left_pupil.agents.api_healer import APIHealerAgent
        from app.engines.left_pupil.agents.data_persona import DataPersonaAgent
        from app.utils.autogen_runtime import get_autogen_runtime_status
        
        logger.info(f"⚕️ Healer attempting to correct payload (Retry {state.get('retry_count', 0)+1}/{state['max_retries']})")
        autogen_status = get_autogen_runtime_status()
        if not autogen_status.available:
            logger.warning(f"Skipping AutoGen API Healer: {autogen_status.reason}")
            return {"failure_type": "ABORT"}
        
        from app.services.smart_ops.ai_config_service import AIConfigService
        from app.core.ai_models import AIModule
        
        healer_cfg = await AIConfigService.get_model_config(AIModule.AGENT_LEFT_HEALER)
        persona_cfg = await AIConfigService.get_model_config(AIModule.AGENT_LEFT_PERSONA)
        
        def build_cfg(cfg):
            return {
                "config_list": [{
                    "model": cfg.model_id,
                    "api_key": settings.QWEN_API_KEY,
                    "base_url": settings.QWEN_BASE_URL
                }],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            }
        
        admin = autogen.UserProxyAgent("Admin", system_message="Wait for Healer to return strictly the JSON.", human_input_mode="NEVER", code_execution_config=False)
        healer = APIHealerAgent("自愈修复师_Healer", build_cfg(healer_cfg))
        persona = DataPersonaAgent("数据拟态师_Persona", build_cfg(persona_cfg))
        
        groupchat = autogen.GroupChat(
            agents=[admin, persona, healer],
            messages=[],
            max_round=4,
            speaker_selection_method="round_robin"
        )
        manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=build_cfg(healer_cfg))
        
        import dataclasses
        prompt = f"""
        Sherlock Diagnosis: {state['failure_type']}
        Original API Intent: {json.dumps(dataclasses.asdict(state['api_ir']), ensure_ascii=False)}
        HTTP Response: {state['response'].body if state['response'] else 'None'}
        
        Provide the corrected API payload. Persona, suggest data if needed, then Healer output the final JSON.
        HEALER MUST output the final response in EXACTLY this JSON format block:
        ```json
        {{
            "action_type": "update",
            "updated_ir": {{
                "url": "<corrected url>",
                "method": "<method>",
                "headers": {{}},
                "body": {{}}
            }}
        }}
        ```
        """
        
        await admin.a_initiate_chat(manager, message=prompt)
        
        try:
            # Find the last message from Healer
            last_msg = ""
            for msg in reversed(groupchat.messages):
                if msg.get("name") == "自愈修复师_Healer":
                    last_msg = msg["content"]
                    break
            
            json_str = last_msg[last_msg.find("{"):last_msg.rfind("}")+1]
            res = json.loads(json_str)
            action_type = res.get("action_type")
            
            if action_type == "abort":
                logger.warning("Healer aborted the recovery.")
                return {"failure_type": "ABORT"}
                
            updated_data = res.get("updated_ir", {})
            # Update the APIIR
            import dataclasses
            valid_keys = {f.name for f in dataclasses.fields(state["api_ir"])}
            filtered_data = {k: v for k, v in updated_data.items() if k in valid_keys}
            new_ir = dataclasses.replace(state["api_ir"], **filtered_data)
            logger.info("Healer successfully generated a new payload.")
            
            # Scribe: Save Memory of the Payload Fix
            from app.core.memory_base import memory_base
            user_id = state.get("context", {}).get("project_id", "default_user")
            memory_base.add_memory(
                content=f"API 载荷自愈经验: 修复 {state['failure_type']} 错误，API为 {state['api_ir'].method} {state['api_ir'].url}。修复为: {json.dumps(updated_data, ensure_ascii=False)}",
                user_id=user_id,
                project_id=user_id
            )
            
            return {
                "api_ir": new_ir,
                "retry_count": state.get("retry_count", 0) + 1,
                "error": None, # Clear errors so evaluate will be clean
                "assertions_failed": [] # Clear assertions for retry
            }
        except Exception as e:
            logger.error(f"Healer parsing failed: {e}")
            return {"failure_type": "HEALER_FAILED"}

    async def node_red_team(self, state: ApiAgentState) -> Dict[str, Any]:
        """Node: Red Team Security Agent"""
        from app.core.config import settings
        import autogen
        import asyncio
        from app.engines.left_pupil.agents.red_teamer import RedTeamerAgent
        
        logger.info("🥷 Red Teamer injecting fuzz payloads...")
        
        from app.services.smart_ops.ai_config_service import AIConfigService
        from app.core.ai_models import AIModule
        
        cfg = await AIConfigService.get_model_config(AIModule.AGENT_LEFT_RED_TEAMER)
        llm_config = {
            "config_list": [{
                "model": cfg.model_id,
                "api_key": settings.QWEN_API_KEY,
                "base_url": settings.QWEN_BASE_URL
            }],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        
        red_teamer = RedTeamerAgent("安全渗透师_RedTeamer", llm_config)
        admin = autogen.UserProxyAgent("Admin", human_input_mode="NEVER", code_execution_config=False, max_consecutive_auto_reply=1)
        
        # Only test successful executions
        if not state.get("response") or state["response"].status_code >= 400:
            return {"security_report": []}
            
        import dataclasses
        prompt = f"""
        Successfully executed API Intent: {json.dumps(dataclasses.asdict(state['api_ir']), ensure_ascii=False)}
        Please identify mutable parameters and suggest fuzzing/injection payloads.
        """
        
        await admin.a_initiate_chat(red_teamer, message=prompt)
        
        try:
            last_msg = admin.chat_messages[red_teamer][-1]["content"]
            json_str = last_msg[last_msg.find("{"):last_msg.rfind("}")+1]
            res = json.loads(json_str)
            mutated_requests = res.get("mutated_requests", [])

            
            security_report = state.get("security_report", [])
            # In a full implementation, we would actually EXECUTE these mutated requests here and check 
            # if they return a 500 or execute JS.
            # For this Phase, we just log the proposed attacks.
            for req in mutated_requests:
                attack = f"Potential {req.get('mutation_type')} vulnerability on field {req.get('target_field')}"
                logger.warning(f"🥷 Red Teamer Alert: {attack}")
                security_report.append(attack)
                
            return {"security_report": security_report}
        except Exception as e:
            logger.error(f"Red Teamer parsing failed: {e}")
            return {"security_report": state.get("security_report", [])}

    async def node_janitor(self, state: ApiAgentState) -> Dict[str, Any]:
        """Node: Janitor Teardown Agent"""
        from app.core.config import settings
        import autogen
        import asyncio
        from app.engines.left_pupil.agents.janitor import JanitorAgent
        
        created_resources = state.get("created_resources", [])
        if not created_resources:
            logger.info("🧹 Janitor: No resources to clean up.")
            return {}
            
        logger.info(f"🧹 Janitor cleaning up {len(created_resources)} created resources...")
        
        from app.services.smart_ops.ai_config_service import AIConfigService
        from app.core.ai_models import AIModule
        
        cfg = await AIConfigService.get_model_config(AIModule.AGENT_LEFT_JANITOR)
        llm_config = {
            "config_list": [{
                "model": cfg.model_id,
                "api_key": settings.QWEN_API_KEY,
                "base_url": settings.QWEN_BASE_URL
            }],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        
        janitor = JanitorAgent("数据清理工_Janitor", llm_config)
        admin = autogen.UserProxyAgent("Admin", human_input_mode="NEVER", code_execution_config=False, max_consecutive_auto_reply=1)
        
        import dataclasses
        prompt = f"""
        Original API Intent: {json.dumps(dataclasses.asdict(state['api_ir']), ensure_ascii=False)}
        Method executed: {state['api_ir'].method}
        Final Response Status: {state['response'].status_code}
        Created Resources Tracked: {json.dumps(created_resources, ensure_ascii=False)}
        
        Please generate the teardown DELETE actions.
        """
        
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, admin.initiate_chat, janitor, prompt)
        
        try:
            last_msg = admin.chat_messages[janitor][-1]["content"]
            json_str = last_msg[last_msg.find("{"):last_msg.rfind("}")+1]
            res = json.loads(json_str)
            teardown_actions = res.get("teardown_actions", [])
            
            # Execute the teardown requests!
            if teardown_actions and not self._client:
                self._client = httpx.AsyncClient(timeout=self.timeout, trust_env=False)
                
            for action_dict in teardown_actions:
                # Basic execution of the DELETE request
                method = action_dict.get("method", "DELETE")
                url_template = action_dict.get("url", "")
                
                # Render the teardown url just in case
                url = self._replace_variables(url_template, state['context'])
                url = self._replace_path_params(url, action_dict.get("path_params", {}), state['context'])
                
                if not url.startswith(("http://", "https://")):
                    protocol = "http://" if "localhost" in url or "127.0.0.1" in url else "https://"
                    url = f"{protocol}{url}"
                
                logger.info(f"🧹 Janitor Sweeping: {method} {url}")
                try:
                    await self._client.request(
                        method=method,
                        url=url,
                        headers=action_dict.get("headers", self.default_headers),
                        params=action_dict.get("query_params", {})
                    )
                except Exception as e:
                    logger.warning(f"Janitor teardown failed for {url}: {e}")
                    
            return {}
        except Exception as e:
            logger.error(f"Janitor parsing/execution failed: {e}")
            return {}


    # ================= 辅助方法 =================

    def _build_headers(self, api_ir: APIIR, context: Dict[str, Any]) -> Dict[str, str]:
        headers = {**self.default_headers, **api_ir.headers}
        if api_ir.body and "Content-Type" not in headers:
            headers["Content-Type"] = api_ir.content_type
            
        if self.auth_config.auth_type == AuthType.BEARER:
            token = self._replace_variables(self.auth_config.token, context)
            headers["Authorization"] = f"Bearer {token}"
            
        elif self.auth_config.auth_type == AuthType.BASIC:
            import base64
            username = self._replace_variables(self.auth_config.username, context)
            password = self._replace_variables(self.auth_config.password, context)
            headers["Authorization"] = f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}"
            
        elif self.auth_config.auth_type == AuthType.API_KEY and self.auth_config.api_key_location == "header":
            headers[self.auth_config.api_key_name] = self._replace_variables(self.auth_config.api_key_value, context)
            
        final_headers = {k: self._replace_variables(v, context) for k, v in headers.items()}
        if "user-agent" not in {k.lower() for k in final_headers}:
            final_headers["User-Agent"] = "ChongMing API Auto / 3.0"
            
        return final_headers
    
    def _replace_variables(self, text: str, context: Dict[str, Any]) -> str:
        merged = {**self._context, **context}
        return render_string(str(text), merged)
    
    def _replace_path_params(self, url: str, path_params: Dict[str, Any], context: Dict[str, Any]) -> str:
        for name, value in path_params.items():
            url = url.replace(f"{{{name}}}", str(self._replace_variables(str(value), context)))
        return url
    
    def _replace_variables_in_obj(self, obj: Any, context: Dict[str, Any]) -> Any:
        merged = {**self._context, **context}
        return render_context(obj, merged)
    
    def _extract_values(self, body: Any, extract_rules: Dict[str, str]) -> Dict[str, Any]:
        return extract_values(body, extract_rules)
