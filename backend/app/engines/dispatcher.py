"""
调度器 (Dispatcher)

智能路由 TC-IR 到正确的执行引擎
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Any, Dict
from loguru import logger
import base64
from urllib.parse import urlparse



from app.engines.right_pupil import RightPupilEngine
from app.engines.left_pupil import LeftPupilEngine

# Import schemas from new location
from app.schemas.execution import (
    ExecutionMode,
    TCIR,
    StepResult,
    ExecutionResult,
    AUIIR,
    APIIR as SchemaAPIIR
)
from app.engines.left_pupil import APIIR as EngineAPIIR, ExecutionResult as APIExecutionResult
from app.utils.context_injector import render_string

class Dispatcher:
    """
    调度器 - 智能路由引擎
    
    职责:
    1. 解析 TC-IR 的执行模式
    2. 将步骤路由到对应引擎 (UI → 右瞳, API → 左瞳)
    3. 管理执行上下文
    4. 收集执行轨迹
    """
    
    def __init__(self):
        self.right_pupil: Optional[RightPupilEngine] = None
        self.left_pupil: Optional[LeftPupilEngine] = None
        self._trace_log: List[dict] = []
        
        from app.engines.master_dispatcher.router import MasterRouter
        self.master_router = MasterRouter()
    
    def attach_engines(
        self,
        right_pupil: Optional[RightPupilEngine] = None,
        left_pupil: Optional[LeftPupilEngine] = None,
    ):
        """附加执行引擎"""
        self.right_pupil = right_pupil
        self.left_pupil = left_pupil

    @staticmethod
    def _is_selector_target(target: Any) -> bool:
        if not isinstance(target, str):
            return False

        normalized = target.strip()
        if not normalized or normalized in {"browser", "window", "document", "page"}:
            return False
        if normalized.startswith(("http://", "https://")):
            return False
        if normalized.startswith(("#", ".", "[", "/", "(")):
            return True

        return any(marker in normalized for marker in ("[", "]", "=", "#", ".", ">", ":"))

    @staticmethod
    def _is_direct_assert_path(target: Any) -> bool:
        return isinstance(target, str) and target.strip() in {"location.pathname", "location.href"}

    def _build_direct_ui_action(
        self,
        *,
        action_name: str,
        target: Any,
        value: Any,
        url: Optional[str],
    ) -> Optional[AUIIR]:
        if action_name in {"goto", "navigate", "open", "visit"} and url:
            return AUIIR(action_type="navigate", params={"url": url})

        if not self._is_selector_target(target):
            return None

        selector = str(target).strip()
        target_payload = {"strategy": "dom", "value": selector, "description": selector}

        if action_name in {"click", "tap", "submit"}:
            return AUIIR(action_type="click", target=target_payload)
        if action_name in {"type", "input", "fill", "enter"} and isinstance(value, str) and value.strip():
            return AUIIR(
                action_type="type",
                target=target_payload,
                params={"text": value.strip()},
            )
        if action_name in {"wait", "wait_for", "wait_visible"}:
            return AUIIR(
                action_type="wait",
                target=target_payload,
                params={"timeout_ms": 5000},
            )
        if action_name in {"assert", "verify", "expect"}:
            if isinstance(value, str) and value.strip():
                return AUIIR(
                    action_type="assert_text",
                    target=target_payload,
                    params={"text": value.strip()},
                )
            return AUIIR(action_type="assert_visible", target=target_payload)
        return None

    async def _capture_page_screenshot_b64(self) -> Optional[str]:
        page = getattr(self.right_pupil, "page", None) if self.right_pupil else None
        if not page:
            return None
        try:
            screenshot_bytes = await page.screenshot(type="png", full_page=True)
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as exc:
            logger.warning(f"Failed to capture direct UI screenshot: {exc}")
            return None

    async def _execute_direct_assert_path(self, target: str, expected: Any, description: str) -> dict:
        page = getattr(self.right_pupil, "page", None) if self.right_pupil else None
        if not page:
            raise RuntimeError("RightPupil page is unavailable for direct path assertion")

        current_url = page.url or ""
        actual = urlparse(current_url).path if target == "location.pathname" else current_url
        if str(actual) != str(expected):
            raise AssertionError(f"Expected {target}={expected}, got {actual}")

        screenshot_after = await self._capture_page_screenshot_b64()
        page_title = await page.title()
        screenshot_after_uri = f"data:image/png;base64,{screenshot_after}" if screenshot_after else None
        return {
            "success": True,
            "error": None,
            "screenshot": screenshot_after_uri,
            "details": {
                "step_name": description,
                "step_type": "UI",
                "action_taken": "assert_path",
                "target_description": target,
                "screenshot_before": None,
                "screenshot_after": screenshot_after_uri,
                "page_url": current_url,
                "page_title": page_title,
                "strategy": "direct_assert",
            },
        }

    async def _execute_direct_ui_action(
        self,
        *,
        action: AUIIR,
        description: str,
        target: Any,
    ) -> dict:
        screenshot_before = await self._capture_page_screenshot_b64()
        result = await self.right_pupil.execute(action)
        screenshot_after = getattr(result, "screenshot_after", None) or await self._capture_page_screenshot_b64()
        page = getattr(self.right_pupil, "page", None)
        page_url = page.url if page else ""
        page_title = await page.title() if page else ""
        screenshot_before_uri = f"data:image/png;base64,{screenshot_before}" if screenshot_before else None
        screenshot_after_uri = f"data:image/png;base64,{screenshot_after}" if screenshot_after else None

        return {
            "success": getattr(result, "success", False),
            "error": getattr(result, "error", None),
            "screenshot": screenshot_after_uri,
            "details": {
                "step_name": description,
                "step_type": "UI",
                "action_taken": action.action_type,
                "target_description": str(target or getattr(action.target, "value", "") or ""),
                "screenshot_before": screenshot_before_uri,
                "screenshot_after": screenshot_after_uri,
                "page_url": page_url,
                "page_title": page_title,
                "strategy": getattr(action.target, "strategy", None) or "global",
            },
        }
    
    async def execute(self, tc_ir: TCIR, execution_id: Optional[str] = None, initial_context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        执行测试用例
        
        Args:
            tc_ir: 测试用例中间表示
            execution_id: 当前关联的执行任务 ID，用于实时追踪推送
            
        Returns:
            ExecutionResult: 执行结果
        """
        import time
        import uuid
        
        trace_id = f"TRACE_{uuid.uuid4().hex[:8].upper()}"
        start_time = time.time()
        step_results: List[StepResult] = []
        variable_trace: List[dict] = [] # Audit Log
        overall_success = True
        
        # Initialize Context Pool for this execution
        context_pool: Dict[str, Any] = initial_context.copy() if initial_context else {}
        
        # 🔍 Pre-scan: Collect ALL ${var_name} references from all steps
        import re as _re
        all_downstream_vars: List[str] = []
        for s in tc_ir.steps:
            step_dict = s.model_dump() if hasattr(s, 'model_dump') else (s.dict() if hasattr(s, 'dict') else dict(s))  # type: ignore[union-attr]
            # Scan URL, body, headers for ${var_name}
            for field_val in [step_dict.get("url", ""), str(step_dict.get("body", "")), str(step_dict.get("headers", ""))]:
                all_downstream_vars.extend(_re.findall(r'\$\{(\w+)\}', str(field_val)))
        all_downstream_vars = list(set(all_downstream_vars))  # deduplicate
        if all_downstream_vars:
            logger.info(f"🔍 [Pre-Scan] 检测到下游变量引用: {all_downstream_vars}")
        
        logger.info(f"开始执行用例: {tc_ir.id} - {tc_ir.name}")
        
        for i, step in enumerate(tc_ir.steps):
            step_start = time.time()
            
            try:
                # Compute downstream vars needed by steps AFTER current one
                downstream_vars_for_step: List[str] = []
                for future_step in tc_ir.steps[i+1:]:
                    fs_dict = future_step.model_dump() if hasattr(future_step, 'model_dump') else (future_step.dict() if hasattr(future_step, 'dict') else dict(future_step))  # type: ignore[union-attr]
                    for field_val in [fs_dict.get("url", ""), str(fs_dict.get("body", "")), str(fs_dict.get("headers", ""))]:
                        downstream_vars_for_step.extend(_re.findall(r'\$\{(\w+)\}', str(field_val)))
                downstream_vars_for_step = list(set(downstream_vars_for_step))
                
                # Pass context_pool and downstream vars to _execute_step
                result = await self._execute_step(step, tc_ir.mode, context_pool, downstream_vars_for_step, execution_id)
                
                step_result = StepResult(
                    step_index=i,
                    success=result["success"],
                    duration_ms=(time.time() - step_start) * 1000,
                    screenshot=result.get("screenshot"),
                    error=result.get("error"),
                    details=result.get("details"),
                    description=step.get("description") or step.get("name") # Use description or name
                )
                
                if not step_result.success:
                    overall_success = False
                    step_result.error = result.get("error")
                
                # Capture Variable Trace
                extracted = result.get("extracted_values")
                if extracted:
                    # Get extraction rules from the executed APIIR (to find the path)
                    # We might need to access api_ir from the local scope if available, 
                    # but _execute_step follows a different scope.
                    # We need to ensure _execute_step returns the *actual* executed APIIR or we reconstruct logic.
                    # Actually, the result object in _execute_step is constructed from api_ir props.
                    # Let's verify if we can access the rules easily.
                    # We can't easily access the internal 'api_ir' from _execute_step return value (it returns dict).
                    # We might need _execute_step to return the used extraction rules in 'details' or similar.
                    # OR, we assume the user provided extracting rules strictly match what we have.
                    # IMPROVEMENT: Let's modify _execute_step to return the 'extract_rules' used.
                    
                    # For now, let's look at how we can get it. 
                    # Dispatcher._execute_step returns a dict. 
                    # Let's add 'used_extract_rules' to its return value.
                    used_rules = result.get("used_extract_rules", {})
                    
                    for k, v in extracted.items():
                        variable_trace.append({
                            "var_name": k,
                            "value": v,
                            "source_step_index": i + 1,
                            "source_step_name": (step_result.details or {}).get("step_name", f"Step {i+1}"),
                            "json_path": used_rules.get(k, "unknown")
                        })
                                        
            except Exception as e:
                overall_success = False
                step_result = StepResult(
                    step_index=i,
                    success=False,
                    duration_ms=(time.time() - step_start) * 1000,
                    error=str(e),
                )
            
            step_results.append(step_result)
            
            # 记录轨迹
            self._trace_log.append({
                "trace_id": trace_id,
                "tc_id": tc_ir.id,
                "step_index": i,
                "step": step,
                "result": step_result.__dict__,
            })
            
            # 失败立即停止 (可配置)
            if not step_result.success:
                logger.warning(f"步骤 {i} 失败，终止执行")
                break
        
        total_duration = (time.time() - start_time) * 1000
        status = "passed" if overall_success else "failed"
        
        logger.info(f"用例 {tc_ir.id} 执行完成: {status}")
        
        return ExecutionResult(
            tc_id=tc_ir.id,
            success=overall_success,
            status=status,
            step_results=step_results,
            total_duration_ms=total_duration,
            trace_id=trace_id,
            variable_trace=variable_trace 
        )
    
    async def _execute_step(self, step: dict, mode: ExecutionMode, context: Optional[Dict[str, Any]] = None, downstream_var_names: Optional[List[str]] = None, execution_id: Optional[str] = None) -> dict:
        """执行单个步骤"""
        step_dict = step.model_dump() if hasattr(step, 'model_dump') else (step.dict() if hasattr(step, 'dict') else dict(step))  # type: ignore[union-attr]
        logger.debug(f"👀 [Check 1] Dispatcher 接收到的原始 Step: {step_dict}")

        # 如果没有显式指定类型，我们可以为其提供 mode 作为备选推断，不过路由器现在更聪明了
        if "step_type" not in step_dict and "type" not in step_dict:
             step_dict["fallback_mode"] = mode.value if hasattr(mode, 'value') else mode

        # 使用全知中枢路由
        engine_type = await self.master_router.route(step_dict)
        
        if engine_type == "RIGHT_PUPIL":
            if not self.right_pupil:
                raise RuntimeError("右瞳引擎未初始化")
            
            description_raw = step_dict.get("description") or step_dict.get("name") or "UI Step"
            description = render_string(description_raw, context or {}) if isinstance(description_raw, str) else description_raw
            url = step_dict.get("url") or None
            if isinstance(url, str):
                url = render_string(url, context or {})
            action_name = str(step_dict.get("action") or step_dict.get("method") or "").strip().lower()
            target = step_dict.get("target")
            if isinstance(target, str):
                target = render_string(target, context or {})
            raw_value = step_dict.get("value")
            value = render_string(raw_value, context or {}) if isinstance(raw_value, str) else raw_value
            # 空字符串也视为 None
            if url and not url.strip():
                url = None
            # Local UI fallback steps store the navigation target in `value`.
            if (
                not url
                and isinstance(value, str)
                and value.strip()
                and action_name in {"goto", "navigate", "open", "visit"}
                and (value.startswith("http://") or value.startswith("https://"))
            ):
                url = value.strip()
                
            # Fallback: 如果没有 url 但 target 是一个 URL 字符串 (常见于从非标准 IR 转换的情况)
            if not url and isinstance(target, str) and (target.startswith("http://") or target.startswith("https://")):
                url = target
            if (
                action_name in {"type", "input", "fill", "enter"}
                and isinstance(value, str)
                and ("${" in value or "{{" in value)
            ):
                raise ValueError(f"Unresolved execution variable in UI step value: {value}")
            if action_name in {"type", "input", "fill", "enter"} and isinstance(value, str) and value.strip():
                description = f"{description}：{value.strip()}"
            elif action_name in {"assert_text", "verify_text", "expect_text"} and isinstance(value, str) and value.strip():
                description = f"{description}（期望值：{value.strip()}）"

            direct_action = self._build_direct_ui_action(
                action_name=action_name,
                target=target,
                value=value,
                url=url,
            )
            if direct_action:
                logger.info(
                    f"⚡ [Dispatcher] Direct UI step via selector/global action: {action_name}, "
                    f"target={target}, url={url}"
                )
                return await self._execute_direct_ui_action(
                    action=direct_action,
                    description=description,
                    target=target or url,
                )

            if (
                action_name in {"assert", "verify", "expect"}
                and self._is_direct_assert_path(target)
                and isinstance(value, str)
                and value.strip()
            ):
                logger.info(f"⚡ [Dispatcher] Direct UI assert path: target={target}, expected={value}")
                return await self._execute_direct_assert_path(str(target), value.strip(), description)

            logger.info(f"👁️ [Dispatcher] UI 步骤 → AI Agent: {description}, URL: {url}")

            # 调用单步 AI 执行
            ui_result = await self.right_pupil.execute_step(description, url or "", execution_id or "")
            
            # 构建截图 data URI
            screenshot_data_uri = None
            raw_ss = ui_result.get("screenshot_after")
            if raw_ss:
                if not raw_ss.startswith("data:"):
                    screenshot_data_uri = f"data:image/png;base64,{raw_ss}"
                else:
                    screenshot_data_uri = raw_ss
            
            screenshot_before_uri = None
            raw_ss_before = ui_result.get("screenshot_before")
            if raw_ss_before:
                if not raw_ss_before.startswith("data:"):
                    screenshot_before_uri = f"data:image/png;base64,{raw_ss_before}"
                else:
                    screenshot_before_uri = raw_ss_before
            
            return {
                "success": ui_result.get("success", False),
                "error": ui_result.get("error"),
                "screenshot": screenshot_data_uri,
                "details": {
                    "step_name": description,
                    "step_type": "UI",
                    "action_taken": ui_result.get("action_taken"),
                    "target_description": ui_result.get("target_description"),
                    "screenshot_before": screenshot_before_uri,
                    "screenshot_after": screenshot_data_uri,
                    "page_url": ui_result.get("page_url"),
                    "page_title": ui_result.get("page_title"),
                    "strategy": ui_result.get("strategy", "ai_vision"),
                },
            }
        
        elif engine_type == "LEFT_PUPIL":
            if not self.left_pupil:
                raise RuntimeError("左瞳引擎未初始化")
            
            # 转换断言格式 (RefinedAssertionSpec -> List[Dict])
            assertion_spec = step_dict.get("assertion", {})
            assertions_list = step_dict.get("assertions", []) # 兼容直接传递列表的情况
            
            if not assertions_list and assertion_spec:
                # 1. Status Code
                # Priority: explicit argument
                status_val = step_dict.get("expected_status_code")
                if status_val is not None:
                    assertions_list.append({
                        "type": "status_code",
                        "expected": int(status_val)
                    })
                
                # 2. JSON Assertions (JSONPath)
                json_asserts = step_dict.get("json_assertions")
                if json_asserts:
                    for path, expected in json_asserts.items():
                        assertions_list.append({
                            "type": "jsonpath",
                            "path": path,
                            "expected": expected,
                            "operator": "equals"
                        })
                
                # 3. Contains
                if assertion_spec.get("contains"):
                    assertions_list.append({
                        "type": "contains",
                        "expected": assertion_spec["contains"]
                    })

            # --- Runtime Intent Parsing (The Ultimate Patch) ---
            # If assertions are missing, we use a lightweight LLM call to extract them from description
            
            desc = step_dict.get("description", "")
            runtime_status = None
            runtime_json = {}
            runtime_extract = {}
            
            explicit_status = step_dict.get("expected_status_code")
            explicit_json = step_dict.get("json_assertions")
            explicit_extract = step_dict.get("extract")
            
            # Condition: Missing explicit status code OR missing extract rules, AND we have a description
            if (explicit_status is None or not explicit_extract) and desc:
                logger.warning(f"🚨 [Runtime Patch] Assertion/Extract Missing! Attempting to parse intent from: '{desc}'")
                try:
                    extraction_result = await self._runtime_intent_parsing(desc, downstream_var_names or [])
                    if extraction_result:
                        runtime_status = extraction_result.get("expected_status_code")
                        runtime_json = extraction_result.get("json_assertions", {})
                        runtime_extract = extraction_result.get("extract", {})
                        
                        logger.success(f"✅ [Runtime Patch] Extracted: Status={runtime_status}, JSON={runtime_json}, Vars={len(runtime_extract)}")
                except Exception as e:
                    logger.error(f"❌ [Runtime Patch] Failed: {e}")

            # Use EngineAPIIR which has path_params
            api_ir = EngineAPIIR(
                method=step_dict.get("method", "GET"),
                url=step_dict.get("url", ""),
                headers=step_dict.get("headers", {}),
                query_params=step_dict.get("params", step_dict.get("query_params", {})),
                path_params=step_dict.get("path_params", {}),
                body=step_dict.get("body", step_dict.get("json_body")),
                assertions=assertions_list,
                extract=explicit_extract if explicit_extract else runtime_extract, # Fallback to runtime extraction
                expected_status_code=explicit_status if explicit_status is not None else runtime_status,
                json_assertions=explicit_json if explicit_json else runtime_json,
            )
            
            logger.debug(f"👀 [Check 2] Dispatcher 转换后的 APIIR: {api_ir}")
            
            try:
                # Returns Engine's ExecutionResult
                # Pass context to engine
                result: APIExecutionResult = await self.left_pupil.execute(api_ir, context or {})
                
                status_code = 0
                if result.response:
                    status_code = result.response.status_code
                
                # Enrich Step Result with Geeky Details (Standardized Structure)
                details = {
                    "step_name": step_dict.get("description") or step_dict.get("name") or "API Step",
                    "step_type": "API",
                    "request": {
                        "url": getattr(result.response, "request_url", api_ir.url) if result.response else (api_ir.url or ""),
                        "method": getattr(result.response, "request_method", api_ir.method) if result.response else (api_ir.method or "GET"),
                        "headers": api_ir.headers or {},
                        "body": api_ir.body or ""
                    },
                    "response": {
                        "status": result.response.status_code if result.response else 0,
                        "headers": getattr(result.response, "headers", {}) if result.response else {},
                        "body": getattr(result.response, "body", "") if result.response else ""
                    },
                    "extracted": getattr(result, "extracted_values", {}) or {},
                    "assertions_failed": getattr(result, "assertions_failed", []) or []
                }
                
                # Check content type for JSON body
                if result.response and "application/json" in result.response.headers.get("Content-Type", ""):
                     try:
                         details["response"]["body"] = result.response.body # Already parsed in APIExecutor
                     except Exception:
                          pass

                return {
                    "success": result.success,
                    "status_code": status_code,
                    "assertions_failed": result.assertions_failed,
                    "error": result.error,
                    "details": details,
                    "used_extract_rules": api_ir.extract # Pass rules back for trace logging
                }
            except Exception as e:
                 logger.error(f"API Step Failed inside Dispatcher: {e}")
                 # Return failed result structure with empty details to avoid UI crash
                 return {
                    "success": False,
                    "status_code": 0,
                    "assertions_failed": [],
                    "error": str(e),
                    "details": {
                        "step_name": step_dict.get("description") or step_dict.get("name") or "Error Step",
                        "request": {},
                        "response": {},
                        "extracted": {},
                        "assertions_failed": []
                    }
                }
        
        else:
            raise ValueError(f"无法确定执行引擎: {engine_type} / 数据: {step_dict}")
    
    def get_trace_log(self) -> List[dict]:
        """获取执行轨迹"""
        return self._trace_log
    
    def clear_trace_log(self):
        """清空轨迹日志"""
        self._trace_log = []

    async def _runtime_intent_parsing(self, description: str, downstream_var_names: Optional[List[str]] = None) -> Optional[dict]:
        """
        Runtime Intent Parsing
        
        Uses a lightweight LLM call to extract assertions from natural language description.
        If downstream_var_names is provided, instructs the LLM to use those exact names as extract keys.
        """
        from app.core.ai_client import get_ai_manager
        from app.core.ai_models import AIModule
        import json
        
        # Build variable naming instruction
        var_naming_hint = ""
        if downstream_var_names:
            var_naming_hint = f"""
            
            CRITICAL NAMING RULE: The following variable names are referenced by downstream steps: {downstream_var_names}
            If you detect that this step should extract a value, you MUST use one of these exact names as the extract key.
            For example, if downstream needs "target_user_id" and this step returns user data, use: "extract": {{"target_user_id": "id"}}
            DO NOT invent your own variable names like "id" or "user_id" - use the EXACT names from the list above."""
        
        try:
            ai_manager = get_ai_manager()
            
            prompt = f"""
            Analyze the following test step description and extract:
            1. EXPECTED HTTP Status Code
            2. JSON Body assertions
            3. Variable Extraction rules (if the user implies capturing a value for later use).
            
            Description: "{description}"
            {var_naming_hint}
            
            Output strictly valid JSON with keys: 
            - "expected_status_code" (int or null)
            - "json_assertions" (dict)
            - "extract" (dict of var_name -> json_path e.g. "data.id")
            
            Example: 
            {{
                "expected_status_code": 200, 
                "json_assertions": {{"success": true}},
                "extract": {{"target_id": "data.id", "auth_token": "token"}}
            }}
            """
            
            # Use Design Module or a fast model
            response = await ai_manager.simple_chat(
                prompt=prompt,
                module=AIModule.AGENT_NEURAL_MERGER,
                temperature=0.0 # Strict determinism
            )
            
            # Parse JSON from response (handle potential markdown blocks)
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Failed to run runtime intent parsing: {e}")
            return None
