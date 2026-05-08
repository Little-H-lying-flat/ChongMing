"""
Right Pupil Engine (The Orchestrator)
右瞳引擎主编排器

集成视觉感知、规划和执行能力，实现端到端的 UI 自动化。
"""

import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth

from app.engines.vision.omni_client import OmniClient
from app.engines.vision.smart_waiter import SmartWaiter
from app.engines.vision.som_renderer import SoMRenderer
from app.engines.vision.dom_service import DomService
from .planner import VisualPlanner
from app.engines.runner.ui_runner import UiRunner
from app.engines.turbo.synthesizer import DataSynthesizer
from app.schemas.execution import AUIIR
from app.utils.autogen_runtime import get_autogen_runtime_status
from app.utils.json_repair import repair_json
from .state import AgentState
from .graph import create_right_pupil_graph

logger = logging.getLogger(__name__)

class RightPupilEngine:
    """
    右瞳引擎 (Visual-First UI Automation Engine)
    """
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None, omni_url: str = ""):
        # 初始化核心组件
        self.omni_client = OmniClient(base_url=omni_url, client=http_client)
        self.som_renderer = SoMRenderer()
        self.dom_service = DomService()
        self.planner = VisualPlanner()
        self.data_synthesizer = DataSynthesizer()
        self.max_steps = 10
        self.waiter: Optional[SmartWaiter] = None
        
        # Initialize LangGraph
        self.graph = create_right_pupil_graph(self)


    async def start_session(self, headless: bool = True):
        """Start a browser session"""
        if hasattr(self, 'browser') and self.browser:
            return

        self.playwright = await async_playwright().start()
        # 注入防检测参数
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="local_runtime/traces/videos",
            # 伪装 User-Agent
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        
        # 应用潜行魔法
        await Stealth().apply_stealth_async(self.page)
        logger.info("🥷 Stealth Mode Activated")
        
        # Initialize Runner with the new page
        self.runner = UiRunner(self.page, self.dom_service)
        self.waiter = SmartWaiter(self.page)
        logger.info("RightPupil Session Started")

    async def stop_session(self):
        """Stop the browser session"""
        try:
            if hasattr(self, 'context') and self.context:
                await self.context.close()
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error stopping RightPupil session: {e}")
        finally:
            self.context = None
            self.browser = None
            self.playwright = None
            self.runner = None
            logger.info("RightPupil Session Stopped")

    # ═══════════════════════════════════════════
    # Task-Aware Action Correction (Layer 1)
    # ═══════════════════════════════════════════
    _INPUT_KEYWORDS = re.compile(
        r"输入|填写|键入|type|搜索框中|在.*框.*中.*输入|在.*中.*填|"
        r"username|user\s*name|password|email|account|query|search",
        re.IGNORECASE,
    )
    _TEXT_EXTRACT = re.compile(r"""['‘’“”"](.+?)['‘’“”"]""")  # 提取引号内的文本

    @staticmethod
    def _register_tool_if_supported(
        autogen_module: Any,
        *,
        func: Any,
        caller: Any,
        executor: Any,
        name: str,
        description: str,
    ) -> bool:
        """Register AutoGen tool only when current autogen version supports it."""
        agentchat = getattr(autogen_module, "agentchat", None)
        register_fn = getattr(agentchat, "register_function", None) if agentchat else None
        if callable(register_fn):
            register_fn(
                func,
                caller=caller,
                executor=executor,
                name=name,
                description=description,
            )
            return True

        logger.warning(
            "AutoGen register_function is unavailable in current version; "
            "continuing without tool registration."
        )
        return False

    @staticmethod
    async def _initiate_chat_async(admin: Any, recipient: Any, prompt: str) -> None:
        """Run AutoGen chat with async API when available, otherwise sync fallback."""
        if hasattr(admin, "a_initiate_chat"):
            try:
                await admin.a_initiate_chat(recipient, message=prompt)
                return
            except TypeError:
                await admin.a_initiate_chat(recipient, prompt)
                return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, admin.initiate_chat, recipient, prompt)

    @staticmethod
    def _build_groupchat(
        autogen_module: Any,
        *,
        agents: List[Any],
        messages: List[Dict[str, Any]],
        max_round: int,
    ) -> Any:
        """Build GroupChat with graceful fallback for autogen version differences."""
        base_kwargs = {
            "agents": agents,
            "messages": messages,
            "max_round": max_round,
        }
        try:
            return autogen_module.GroupChat(
                **base_kwargs,
                speaker_selection_method="round_robin",
                allow_repeat_speaker=False,
            )
        except TypeError as exc:
            logger.warning(
                f"AutoGen GroupChat kwargs not supported in current version, "
                f"fallback to default turn policy: {exc}"
            )
            return autogen_module.GroupChat(**base_kwargs)

    @staticmethod
    def _extract_message_text(message: Any) -> str:
        """Extract best-effort text payload from AutoGen message object."""
        if isinstance(message, str):
            return message
        if isinstance(message, dict):
            for key in ("content", "message", "text"):
                value = message.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return ""

    @staticmethod
    def _get_agent_messages(user_proxy: Any, agent: Any) -> List[Any]:
        """Read chat history robustly across AutoGen versions."""
        chat_messages = getattr(user_proxy, "chat_messages", {}) or {}
        if not isinstance(chat_messages, dict):
            return []

        if agent in chat_messages and isinstance(chat_messages[agent], list):
            return chat_messages[agent]

        agent_name = getattr(agent, "name", None)
        if agent_name and agent_name in chat_messages and isinstance(chat_messages[agent_name], list):
            return chat_messages[agent_name]

        for value in chat_messages.values():
            if isinstance(value, list):
                return value

        return []

    @staticmethod
    def _extract_json_candidates(text: str) -> List[str]:
        """Collect likely JSON payload candidates from a model reply."""
        if not text or not text.strip():
            return []

        candidates: List[str] = [text.strip()]
        fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        candidates.extend(block.strip() for block in fenced_blocks if block.strip())

        object_matches = re.findall(r"(\{[\s\S]*?\})", text)
        array_matches = re.findall(r"(\[[\s\S]*?\])", text)
        candidates.extend(match.strip() for match in object_matches if match.strip())
        candidates.extend(match.strip() for match in array_matches if match.strip())

        unique_candidates: List[str] = []
        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            unique_candidates.append(candidate)
        return unique_candidates

    @staticmethod
    def _parse_agent_json_response(
        messages: List[Any],
        *,
        required_keys: List[str],
        fallback_message: str = "",
    ) -> Dict[str, Any]:
        """Parse the latest valid assistant JSON reply that contains required keys."""
        candidate_texts: List[str] = []
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") != "assistant":
                continue
            text = RightPupilEngine._extract_message_text(message)
            if text:
                candidate_texts.append(text)

        if fallback_message:
            candidate_texts.append(fallback_message)

        for text in candidate_texts:
            for candidate in RightPupilEngine._extract_json_candidates(text):
                try:
                    parsed = repair_json(candidate)
                except Exception:
                    continue

                if isinstance(parsed, dict) and all(key in parsed for key in required_keys):
                    return parsed

        raise ValueError(f"No valid JSON reply found with keys: {required_keys}")

    @staticmethod
    def _safe_netloc(raw_url: Optional[str]) -> str:
        """Extract normalized netloc from URL string."""
        if not raw_url:
            return ""
        try:
            return (urlparse(raw_url).netloc or "").lower().strip()
        except Exception:
            return ""

    @staticmethod
    def _should_bootstrap_navigation(state: AgentState) -> bool:
        """Navigate to task_url only once at the beginning of a step."""
        return bool(
            state.get("task_url")
            and not state.get("action_intent")
            and not state.get("history")
        )

    @staticmethod
    def _classify_failure_heuristic(error_msg: str) -> str:
        """Fallback failure classification when Sherlock/LLM path is unavailable."""
        text = (error_msg or "").lower()
        if "cross-domain" in text or "redirect" in text:
            return "ENVIRONMENT_ISSUE"
        if "omniparser" in text or "perception" in text or "no elements found" in text:
            return "VISION_FAILED"
        if "timeout" in text or "execution error" in text:
            return "RETRYABLE"
        return "UNKNOWN_ERROR"

    @staticmethod
    def _infer_input_text(step_description: str) -> Optional[str]:
        """Infer type action text when LLM omits params.text."""
        if not step_description:
            return None

        quoted = RightPupilEngine._TEXT_EXTRACT.search(step_description)
        if quoted:
            return quoted.group(1)

        tail_pattern = re.search(
            r"(?:输入|填写|键入|type)\s*[:：]?\s*(\S+)\s*$",
            step_description,
            flags=re.IGNORECASE,
        )
        if tail_pattern:
            return tail_pattern.group(1)

        parts = step_description.strip().split()
        if len(parts) >= 2:
            candidate = parts[-1].strip()
            if candidate and candidate.lower() not in {"输入", "填写", "键入", "type"}:
                return candidate

        return None

    @staticmethod
    def _extract_semantic_hint(step_description: str) -> Optional[str]:
        """Extract the entity name referenced by a click-like action."""
        if not step_description:
            return None

        quoted = RightPupilEngine._TEXT_EXTRACT.search(step_description)
        if quoted:
            hint = quoted.group(1).strip()
            return hint or None

        patterns = [
            r"\bfor\s+([A-Za-z0-9][A-Za-z0-9\s_\-().]+?)(?:\s*(?:button|link|item|card))?\s*$",
            r"\bnamed\s+([A-Za-z0-9][A-Za-z0-9\s_\-().]+?)\s*$",
            r"\bcalled\s+([A-Za-z0-9][A-Za-z0-9\s_\-().]+?)\s*$",
            r"名为\s*[\"“”']?(.+?)[\"“”']?(?:的|\s*$)",
            r"叫做\s*[\"“”']?(.+?)[\"“”']?(?:的|\s*$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, step_description, flags=re.IGNORECASE)
            if not match:
                continue
            hint = match.group(1).strip(" .,:;!?")
            if len(hint) >= 3:
                return hint

        return None

    @staticmethod
    def _extract_field_hint(step_description: str) -> Optional[str]:
        """Extract the semantic field name referenced by a type action."""
        if not step_description:
            return None

        patterns = [
            r"\binto\s+(?:the\s+)?(.+?)\s+(?:input|field|textbox|text box|box)\b",
            r"\bin\s+(?:the\s+)?(.+?)\s+(?:input|field|textbox|text box|box)\b",
            r"\bfor\s+(?:the\s+)?(.+?)\s+(?:input|field|textbox|text box|box)\b",
            r"在\s*(.+?)\s*(?:输入框|字段|文本框|框)",
        ]
        for pattern in patterns:
            match = re.search(pattern, step_description, flags=re.IGNORECASE)
            if not match:
                continue
            hint = match.group(1).strip(" .,:;!?\"'“”")
            if len(hint) >= 2:
                return hint

        return None

    @staticmethod
    async def _read_input_value_by_hint(
        page: Page,
        *,
        field_hint: Optional[str],
        fallback_x: Optional[float] = None,
        fallback_y: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Read the current value of the best-matching editable field."""
        if not page:
            return None

        hint = (field_hint or "").strip().lower()
        try:
            return await page.evaluate(
                """
                ({ fieldHint, fallbackX, fallbackY }) => {
                    function normalize(text) {
                        return String(text || "")
                            .toLowerCase()
                            .replace(/[^a-z0-9]+/g, " ")
                            .replace(/\\s+/g, " ")
                            .trim();
                    }

                    function isVisible(element) {
                        if (!element) return false;
                        const style = window.getComputedStyle(element);
                        const rect = element.getBoundingClientRect();
                        return style.display !== "none" &&
                            style.visibility !== "hidden" &&
                            style.opacity !== "0" &&
                            rect.width > 0 &&
                            rect.height > 0;
                    }

                    function isEditable(element) {
                        if (!element) return false;
                        const tag = element.tagName.toLowerCase();
                        const role = (element.getAttribute("role") || "").toLowerCase();
                        return (
                            (tag === "input" && !["hidden", "submit", "button", "checkbox", "radio", "image"].includes((element.type || "").toLowerCase())) ||
                            tag === "textarea" ||
                            element.contentEditable === "true" ||
                            ["textbox", "searchbox", "combobox"].includes(role)
                        );
                    }

                    function editableRoot(element) {
                        let current = element;
                        for (let i = 0; i < 6 && current; i += 1) {
                            if (isEditable(current)) return current;
                            current = current.parentElement;
                        }
                        return null;
                    }

                    function labelText(element) {
                        const parts = [];
                        for (const attr of ["placeholder", "aria-label", "name", "id", "data-test"]) {
                            const value = element.getAttribute(attr);
                            if (value) parts.push(value);
                        }
                        if (element.labels) {
                            for (const label of element.labels) {
                                parts.push(label.innerText || label.textContent || "");
                            }
                        }
                        let current = element.parentElement;
                        for (let depth = 0; depth < 4 && current; depth += 1) {
                            parts.push(current.getAttribute("aria-label") || "");
                            parts.push(current.innerText || current.textContent || "");
                            current = current.parentElement;
                        }
                        return normalize(parts.join(" "));
                    }

                    function currentValue(element) {
                        if (!element) return "";
                        if (element.tagName.toLowerCase() === "textarea" || element.tagName.toLowerCase() === "input") {
                            return element.value || "";
                        }
                        if (element.contentEditable === "true") {
                            return element.innerText || element.textContent || "";
                        }
                        return "";
                    }

                    const hint = normalize(fieldHint);
                    const candidates = Array.from(
                        document.querySelectorAll(
                            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"]):not([type="image"]), textarea, [contenteditable="true"], [role="textbox"], [role="searchbox"], [role="combobox"]'
                        )
                    ).filter(isVisible);

                    let best = null;
                    if (hint) {
                        for (const candidate of candidates) {
                            const labels = labelText(candidate);
                            if (!labels.includes(hint)) continue;
                            const rect = candidate.getBoundingClientRect();
                            const cx = rect.left + rect.width / 2;
                            const cy = rect.top + rect.height / 2;
                            const hasPoint = Number.isFinite(fallbackX) && Number.isFinite(fallbackY);
                            const distancePenalty = hasPoint
                                ? Math.sqrt((cx - fallbackX) ** 2 + (cy - fallbackY) ** 2) / 10
                                : 0;
                            const score = 300 - distancePenalty;
                            if (!best || score > best.score) {
                                best = {
                                    value: currentValue(candidate),
                                    score,
                                    matched_by: "hint",
                                };
                            }
                        }
                    }

                    if (best) return best;

                    if (Number.isFinite(fallbackX) && Number.isFinite(fallbackY)) {
                        const fallback = editableRoot(document.elementFromPoint(fallbackX, fallbackY));
                        if (fallback && isVisible(fallback)) {
                            return {
                                value: currentValue(fallback),
                                score: 0,
                                matched_by: "coords",
                            };
                        }
                    }

                    return null;
                }
                """,
                {
                    "fieldHint": hint,
                    "fallbackX": fallback_x,
                    "fallbackY": fallback_y,
                },
            )
        except Exception as exc:
            logger.warning(f"Typed value verification failed: {exc}")
            return None

    def _enrich_action_context(self, action, step_description: str):
        """Attach generic semantic hints to actions for downstream disambiguation."""
        if not action:
            return action

        if not isinstance(getattr(action, "params", None), dict):
            action.params = {}

        if action.action_type in {"click", "dblclick", "hover"} and not action.params.get("semantic_hint"):
            hint = self._extract_semantic_hint(step_description)
            if hint:
                action.params["semantic_hint"] = hint

        if action.action_type == "type":
            field_hint = action.params.get("field_hint") or self._extract_field_hint(step_description)
            if field_hint:
                action.params["field_hint"] = field_hint
                action.params.setdefault("semantic_hint", field_hint)

        return action

    def _correct_action_type(self, action, step_description: str):
        """
        任务感知动作修正：
        如果步骤描述包含"输入/填写"等关键词，但 AI 返回了 click，则修正为 type。
        同时从描述中提取要输入的文本填入 params.text。
        """
        if not action or not step_description:
            return action
        
        if action.action_type == "click" and self._INPUT_KEYWORDS.search(step_description):
            logger.warning(
                f"🔧 Action correction: click → type (description contains input keywords: '{step_description[:60]}')"
            )
            action.action_type = "type"
            if not isinstance(getattr(action, "params", None), dict):
                action.params = {}
            
            # 如果 params 中没有 text，尝试从描述中提取引号内容
            if not action.params.get("text"):
                inferred = self._infer_input_text(step_description)
                if inferred:
                    action.params["text"] = inferred
                    logger.info(f"   Extracted text from description: '{inferred}'")
        
        return self._enrich_action_context(action, step_description)

    async def execute(self, action: AUIIR) -> Any:
        """
        Execute a single UI action (Step-by-Step mode for Dispatcher)
        """
        if not hasattr(self, 'runner') or not self.runner:
            raise RuntimeError("Session not started. Call start_session() first.")

        try:
            success = await self.runner.execute(action, id_map={})
            
            strategy_name = "unknown"
            if action.target:
                strategy_name = action.target.strategy
            
            # 截取执行后的页面快照
            screenshot_b64 = None
            if hasattr(self, 'page') and self.page:
                try:
                    import base64
                    screenshot_bytes = await self.page.screenshot(type="png", full_page=True)
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                except Exception as e:
                    logger.warning(f"截图失败: {e}")
                
            res = type('Result', (object,), {
                "success": success,
                "strategy_used": type('Strategy', (object,), {"value": strategy_name})(),
                "screenshot_after": screenshot_b64,
                "error": None if success else "Execution failed"
            })()
            return res
        except Exception as e:
            logger.error(f"RightPupil Execute Error: {e}")
            return type('Result', (object,), {
                "success": False,
                "strategy_used": None,
                "screenshot_after": None,
                "error": str(e)
            })()

    # ═══════════════════════════════════════════
    # LangGraph Nodes Implementation
    # ═══════════════════════════════════════════
    
    async def node_perceive(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 感知锚定: 获取截图并调用 OmniParser
        """
        logger.info("--- [Node: Perceive] ---")
        import base64

        # First step with task_url: let reason node emit deterministic navigate action.
        if self._should_bootstrap_navigation(state):
            return {
                "current_screenshot": None,
                "annotated_screenshot": None,
                "id_map": {},
                "som_text": "",
                "error": None,
                "failure_type": None,
            }
        
        # Step 1: Wait & Screenshot
        if self.waiter:
            await self.waiter.wait_until_stable()
            
        screenshot_bytes = await self.page.screenshot(type="png")
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        # Initialize state updates
        updates = {
            "current_screenshot": screenshot_b64,
            "error": None,
            "failure_type": None
        }
        
        # Check if navigating
        if state.get("action_intent") and getattr(state["action_intent"], "action_type", "") == "navigate":
            # Just navigated, return screenshot, no need for OmniParser this cycle until next reasoned action
            return updates

        # Step 2: Perception (OmniParser -> SoM)
        try:
            elements = await self.omni_client.parse_screenshot(screenshot_b64)
            if not elements:
                logger.warning("OmniParser found no elements.")
                updates["error"] = "No elements found on screen."
                updates["failure_type"] = "VISION_FAILED"
                return updates
                
            loop = asyncio.get_running_loop()
            annotated_b64, id_map = await loop.run_in_executor(
                None, self.som_renderer.draw_som, screenshot_b64, elements
            )
            
            # Construct SoM text for the Reason node
            som_text_lines = []
            for k, v in id_map.items():
                bbox = v.get('bbox', [0, 0, 0, 0])
                w = int(bbox[2] - bbox[0])
                h = int(bbox[3] - bbox[1])
                som_text_lines.append(f"ID {k}: [{w}x{h}] {v.get('label')} {v.get('content', '')}")
            som_text = "\n".join(som_text_lines)

            # --- Right Pupil 3.0: Hybrid Perception & Semantic Description ---
            points = []
            for k, v in id_map.items():
                bbox = v.get('bbox', [0, 0, 0, 0])
                cx = (bbox[0] + bbox[2]) / 2.0
                cy = (bbox[1] + bbox[3]) / 2.0
                points.append({"x": cx, "y": cy})
            
            dom_hints = []
            if points:
                try:
                    dom_hints = await self.dom_service.get_dom_hints_from_points(self.page, points)
                except Exception as e:
                    logger.warning(f"Failed to fetch DOM hints: {e}")
                    dom_hints = [None] * len(points)
            
            describer_input = []
            for j, (k, v) in enumerate(id_map.items()):
                item = {
                    "id": int(k),
                    "bbox": [int(x) for x in v.get("bbox", [0, 0, 0, 0])],
                    "ocr": v.get("content", "")
                }
                if j < len(dom_hints) and dom_hints[j]:
                    item["dom_hint"] = dom_hints[j]
                describer_input.append(item)
                
            semantic_elements_str = "[]"
            autogen_status = get_autogen_runtime_status()
            if autogen_status.available:
                 try:
                     import autogen, json, re
                     from app.engines.right_pupil.agents.element_describer import ElementDescriberAgent
                     from app.services.smart_ops.ai_config_service import AIConfigService
                     from app.core.ai_models import AIModule
                     from app.core.config import settings
                     
                     desc_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_VISUAL)
                     desc_llm_config = {
                          "config_list": [{
                              "model": desc_cfg.model_id,
                              "api_key": settings.QWEN_API_KEY,
                              "base_url": settings.QWEN_BASE_URL
                          }],
                          "temperature": 0.1,
                          "max_tokens": desc_cfg.max_tokens,
                     }
                     
                     describer = ElementDescriberAgent("ElementDescriber", desc_llm_config)
                     admin = autogen.UserProxyAgent("Admin", human_input_mode="NEVER", code_execution_config=False, max_consecutive_auto_reply=1)
                     
                     desc_prompt = f"Please translate the following elements into semantic descriptions:\n{json.dumps(describer_input, ensure_ascii=False)}"
                     await self._initiate_chat_async(admin, describer, desc_prompt)
                     
                     last_msg = self._extract_message_text(describer.last_message())
                     json_match = re.search(r'```(?:json)?\n(.*)\n```', last_msg, re.DOTALL)
                     if json_match:
                         semantic_elements_str = json_match.group(1).strip()
                     else:
                         match = re.search(r'(\[.*\])', last_msg, re.DOTALL)
                         semantic_elements_str = match.group(1).strip() if match else last_msg
                         
                     logger.info(f"Element Describer output computed successfully: {len(semantic_elements_str)} chars")
                 except Exception as e:
                     logger.error(f"Element Describer Agent failed: {e}. Falling back to RAW JSON.")
                     semantic_elements_str = json.dumps(describer_input, ensure_ascii=False)
            else:
                 semantic_elements_str = json.dumps(describer_input, ensure_ascii=False)
            
            # Live trace broadcast (Optional)
            execution_id = state.get("execution_id")
            if execution_id:
                from app.api.v1.endpoints.visual_ui import visual_ws_manager
                try:
                    asyncio.create_task(
                        visual_ws_manager.broadcast_to_execution(
                            execution_id,
                            {
                                "event": "live_trace",
                                "step_description": state.get("task_description", ""),
                                "image_b64": f"data:image/png;base64,{annotated_b64}"
                            }
                        )
                    )
                except Exception as e:
                    pass
            
            updates.update({
                "annotated_screenshot": annotated_b64,
                "id_map": id_map,
                "som_text": som_text,
                "semantic_elements": semantic_elements_str
            })
            
        except Exception as e:
            logger.error(f"Perception failed: {e}")
            updates["error"] = f"Perception Error: {str(e)}"
            updates["failure_type"] = "VISION_FAILED"
            
        return updates

    async def node_reason(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 群智决策: AutoGen GroupChat (VisualExpert + Persona + Critic)

        """
        logger.info("--- [Node: Reason] ---")
        
        # If perceive failed, skip reasoning
        if state.get("error"):
            return {}

        # Healer may inject a direct action; keep it and skip a new reasoning pass once.
        if state.get("use_existing_action") and state.get("action_intent"):
            return {"use_existing_action": False}
            
        task_desc = state.get("task_description")
        
        # Handle Navigation specifically if initial step has url but no intent yet
        if self._should_bootstrap_navigation(state):
             # For Phase 1, if we have a URL initially, we navigate first
             from app.schemas.execution import AUIIR
             action = AUIIR(
                 action_type="navigate",
                 target=None,
                 params={"url": state["task_url"]},
                 expected_visual_change=f"Navigate to {state['task_url']}"
             )
             return {"action_intent": action}

        autogen_status = get_autogen_runtime_status()
        if not autogen_status.available:
            logger.warning(
                "Skipping AutoGen reasoning and using VisualPlanner fallback directly: "
                f"{autogen_status.reason}"
            )
            try:
                fallback_action = await self.planner.plan_next_step(
                    task=task_desc or "",
                    screenshot_base64=state.get("current_screenshot") or "",
                    som_text=state.get("som_text") or "",
                    history=state.get("history") or [],
                )
                if fallback_action:
                    fallback_action = self._correct_action_type(
                        fallback_action, task_desc or ""
                    )
                    return {
                        "action_intent": fallback_action,
                        "error": None,
                        "failure_type": None,
                    }
            except Exception as planner_exc:
                logger.error(f"Reasoning fallback (VisualPlanner) failed: {planner_exc}")
                return {
                    "error": f"Reasoning Error: {autogen_status.reason}",
                    "failure_type": "PLANNING_FAILED"
                }
        
        try:
            from app.engines.right_pupil.agents.visual_expert import VisualExpertAgent
            from app.engines.right_pupil.agents.persona import PersonaAgent
            from app.engines.right_pupil.agents.critic import CriticAgent
            import autogen
            import json
            import re
            from app.core.config import settings
            from app.schemas.execution import AUIIR
            from app.core.ai_models import AIModule
            from app.core.ai_client import get_ai_manager
            
            # Setup AutoGen LLM Config using DashScope through our unify config
            # (In a real production setup, we'd wire AIClient in, but AutoGen expects OpenAI-compatible config dict)
            from app.services.smart_ops.ai_config_service import AIConfigService
            from app.core.ai_models import AIModule
            
            visual_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_VISUAL)
            persona_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_PERSONA)
            critic_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_CRITIC)

            def build_cfg(cfg):
                return {
                    "config_list": [{
                        "model": cfg.model_id,
                        "api_key": settings.QWEN_API_KEY,
                        "base_url": settings.QWEN_BASE_URL
                    }],
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                    "timeout": 120,
                }
            
            # 1. Initialize Agents
            admin = autogen.UserProxyAgent(
                name="Orchestrator",
                system_message="You manage the reasoning flow. Provide the SoM data and task to the experts. Wait for the Critic to say TERMINATE.",
                human_input_mode="NEVER",
                code_execution_config=False
            )
            
            visual_expert = VisualExpertAgent("视觉交互专家_VisualExpert", build_cfg(visual_cfg))
            persona = PersonaAgent("视觉意图拆解_Persona", build_cfg(persona_cfg))
            critic = CriticAgent("视觉审查官_Critic", build_cfg(critic_cfg))
            
            from app.engines.right_pupil.agents.librarian import search_knowledge_base
            self._register_tool_if_supported(
                autogen,
                func=search_knowledge_base,
                caller=visual_expert,
                executor=admin,
                name="search_knowledge_base",
                description="Search the knowledge base for historical context or element locators.",
            )
            self._register_tool_if_supported(
                autogen,
                func=search_knowledge_base,
                caller=persona,
                executor=admin,
                name="search_knowledge_base",
                description="Search the knowledge base for historical context or synthetic test data examples.",
            )
            
            # 2. Build GroupChat
            groupchat = self._build_groupchat(
                autogen,
                agents=[admin, visual_expert, persona, critic],
                messages=[],
                max_round=10,
            )
            
            manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=build_cfg(critic_cfg))
            
            # 3. Construct Prompt
            prompt = f"""Task: {task_desc}
            
Recent History: {json.dumps(state.get('history')[-3:] if state.get('history') else [])}

Semantic_Elements (translated from OmniParser & DOM):
{state.get('semantic_elements', '[]')}

Please propose the next action."""

            # 4. Run GroupChat
            await self._initiate_chat_async(admin, manager, prompt)

            # 5. Extract JSON from Critic's last message
            last_msg = None
            # Find the last message from Critic
            for msg in reversed(groupchat.messages):
                msg_name = str(msg.get("name", "")) if isinstance(msg, dict) else ""
                if msg_name == critic.name or "Critic" in msg_name:
                    last_msg = self._extract_message_text(msg)
                    break
            if not last_msg and groupchat.messages:
                last_msg = self._extract_message_text(groupchat.messages[-1])
                    
            if not last_msg:
                raise ValueError("Critic did not provide a final output.")
                
            # Extract JSON block
            import re
            json_str = last_msg
            json_match = re.search(r'```(?:json)?\n(.*?)\n```', last_msg, re.DOTALL)
            if json_match:
               json_str = json_match.group(1)
            else:
               # Try to find { ... }
               match = re.search(r'(\{.*\})', last_msg, re.DOTALL)
               if match:
                   json_str = match.group(1)

            action_data = json.loads(json_str)
            
            # Parse into AUIIR
            action = AUIIR(**action_data)
            
            # Action correction (fallback to our heuristics if needed)
            if action and action.action_type != "done":
                action = self._correct_action_type(action, task_desc)
                
            return {"action_intent": action}
            
        except Exception as e:
            logger.error(f"Reasoning failed (AutoGen): {e}")
            try:
                fallback_action = await self.planner.plan_next_step(
                    task=task_desc or "",
                    screenshot_base64=state.get("current_screenshot") or "",
                    som_text=state.get("som_text") or "",
                    history=state.get("history") or [],
                )
                if fallback_action:
                    fallback_action = self._correct_action_type(
                        fallback_action, task_desc or ""
                    )
                    logger.info("Reasoning fallback: using VisualPlanner output.")
                    return {"action_intent": fallback_action, "error": None, "failure_type": None}
            except Exception as planner_exc:
                logger.error(f"Reasoning fallback (VisualPlanner) failed: {planner_exc}")
            return {
                "error": f"Reasoning Error: {str(e)}",
                "failure_type": "PLANNING_FAILED"
            }

    async def node_act(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 物理执行: 使用 Playwright 执行动作
        """
        logger.info("--- [Node: Act] ---")
        
        if state.get("error"):
            return {}
            
        action = state.get("action_intent")
        if not action:
            return {"error": "No action to execute", "failure_type": "EXECUTION_FAILED"}
            
        if action.action_type == "done":
            return {
                "action_result": {"success": True, "details": "Task marked as done by planner"},
                "use_existing_action": False,
            }
            
        # Execute
        try:
            if action.action_type == "navigate":
                 nav_url = None
                 if isinstance(getattr(action, "params", None), dict):
                     nav_url = action.params.get("url")
                 if not nav_url and getattr(action, "target", None):
                     nav_url = getattr(action.target, "value", None)
                 if not nav_url:
                     raise ValueError("Navigate action missing url in params.url or target.value")
                 await self.page.goto(nav_url, wait_until="domcontentloaded", timeout=30000)
                 success = True
            else:
                 success = await self.runner.execute(action, state.get("id_map", {}))
            
            return {
                "action_result": {
                    "success": success,
                    "action_type": action.action_type,
                    "target": (
                        nav_url
                        if action.action_type == "navigate"
                        else (action.target.value if hasattr(action.target, "value") else None)
                    ),
                },
                "use_existing_action": False,
            }
        except Exception as e:
            logger.error(f"Action Execution failed: {e}")
            return {
                "error": f"Execution Error: {str(e)}",
                "failure_type": "EXECUTION_FAILED"
            }

    async def _verify_type_action(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Verify typed text actually landed in the intended editable field."""
        intent = state.get("action_intent")
        if not intent or getattr(intent, "action_type", None) != "type":
            return None

        params = getattr(intent, "params", {}) or {}
        if not isinstance(params, dict):
            params = {}

        expected_text = str(params.get("text", ""))
        if not expected_text:
            return None

        selectors = []
        target = getattr(intent, "target", None)
        if getattr(target, "strategy", None) == "dom" and getattr(target, "value", None):
            selectors.append(str(target.value))

        trace_logs = getattr(self.runner, "trace_logs", None) or []
        last_trace = trace_logs[-1] if trace_logs else {}
        stable_selector = last_trace.get("stable_selector")
        if stable_selector and stable_selector not in selectors:
            selectors.append(stable_selector)

        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                if await locator.count() < 1:
                    continue
                actual_value = await locator.input_value()
                return {
                    "passed": actual_value == expected_text,
                    "actual_value": actual_value,
                    "expected_value": expected_text,
                    "matched_by": f"selector:{selector}",
                }
            except Exception:
                continue

        field_hint = params.get("field_hint") or params.get("semantic_hint")
        fallback = (
            last_trace.get("input_resolution")
            or last_trace.get("relocated_to")
            or last_trace.get("coords")
            or {}
        )
        verification = await self._read_input_value_by_hint(
            self.page,
            field_hint=field_hint,
            fallback_x=fallback.get("x"),
            fallback_y=fallback.get("y"),
        )
        if verification is None:
            return {
                "passed": False,
                "actual_value": None,
                "expected_value": expected_text,
                "matched_by": "unresolved",
            }

        actual_value = verification.get("value")
        return {
            "passed": actual_value == expected_text,
            "actual_value": actual_value,
            "expected_value": expected_text,
            "matched_by": verification.get("matched_by", "hint"),
        }

    async def node_evaluate(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 结果裁定: 判断动作是否成功
        """
        logger.info("--- [Node: Evaluate] ---")
        # Phase 1: Simple evaluation based on runner success boolean
        action_result = state.get("action_result", {})
        
        # If already errored out upstream
        if state.get("error"):
             return {}
             
        if not action_result.get("success", False):
             return {
                 "error": "Action execution failed in runner",
                 "failure_type": "RETRYABLE"
             }

        # Guard: unexpected cross-domain redirect often means ad/pop-up hijack.
        intent = state.get("action_intent")
        intent_type = getattr(intent, "action_type", "") if intent else ""
        if intent_type not in {"navigate", "done"}:
            expected_netloc = self._safe_netloc(state.get("task_url"))
            current_netloc = self._safe_netloc(self.page.url if getattr(self, "page", None) else "")
            if expected_netloc and current_netloc:
                same_domain = (
                    current_netloc.endswith(expected_netloc)
                    or expected_netloc.endswith(current_netloc)
                )
                if not same_domain:
                    return {
                        "error": (
                            f"Unexpected cross-domain navigation: expected '{expected_netloc}', "
                            f"got '{current_netloc}'"
                        ),
                        "failure_type": "ENVIRONMENT_ISSUE",
                    }

        type_verification = await self._verify_type_action(state)
        if type_verification and not type_verification.get("passed", False):
            return {
                "error": (
                    "Typed value verification failed: "
                    f"expected '{type_verification.get('expected_value', '')}', "
                    f"got '{type_verification.get('actual_value', '')}' "
                    f"via {type_verification.get('matched_by', 'unknown')}"
                ),
                "failure_type": "RETRYABLE",
            }
             
        # Record history on success
        history = state.get("history", [])
        if state.get("action_intent"):
            # safely convert action to dict if model_dump is available
            intent = state["action_intent"]
            intent_dict = intent.model_dump() if hasattr(intent, 'model_dump') else str(intent)
            history.append({
                "action": intent_dict,
                "status": "success",
                "timestamp": __import__('time').time()
            })
            
        return {"history": history, "error": None, "failure_type": "NONE", "use_existing_action": False}

    async def node_sherlock(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 根因分析: Call Sherlock to analyze the failure.
        """
        logger.info("--- [Node: Sherlock] ---")
        autogen_status = get_autogen_runtime_status()
        if not autogen_status.available:
            logger.warning(f"Skipping AutoGen Sherlock: {autogen_status.reason}")
            return {
                "failure_type": self._classify_failure_heuristic(
                    state.get("error", "")
                )
            }

        try:
            import autogen
            from app.engines.right_pupil.agents.sherlock import SherlockAgent
            from app.core.config import settings
            
            from app.services.smart_ops.ai_config_service import AIConfigService
            from app.core.ai_models import AIModule
            
            cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_SHERLOCK)
            llm_config = {
                "config_list": [{
                    "model": cfg.model_id,
                    "api_key": settings.QWEN_API_KEY,
                    "base_url": settings.QWEN_BASE_URL
                }],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            }
            sherlock = SherlockAgent("DOM推断专家_Sherlock", llm_config)
            admin = autogen.UserProxyAgent(
                "Admin",
                human_input_mode="NEVER",
                code_execution_config=False,
                max_consecutive_auto_reply=1
            )
            
            from app.engines.right_pupil.agents.librarian import search_knowledge_base
            # self._register_tool_if_supported(
            #     autogen,
            #     func=search_knowledge_base,
            #     caller=sherlock,
            #     executor=admin,
            #     name="search_knowledge_base",
            #     description="Search the knowledge base for root cause of known errors, system bugs, or UI changes.",
            # )
            
            error_msg = state.get("error", "Unknown error")
            history = state.get("history", [])
            last_action = history[-1] if history else {}
            
            prompt = f"Error: {error_msg}\nLast Action: {json.dumps(last_action)}\nAnalyze the root cause and output strict JSON."
            
            await self._initiate_chat_async(admin, sherlock, prompt)
            
            messages = self._get_agent_messages(admin, sherlock)
            fallback_message = self._extract_message_text(sherlock.last_message())
            res = self._parse_agent_json_response(
                messages,
                required_keys=["failure_type"],
                fallback_message=fallback_message,
            )
            failure_type = res.get("failure_type", "UNKNOWN_ERROR")
            logger.info(f"Sherlock Diagnosis: {failure_type} ({res.get('reasoning', '')})")
            
            # Scribe: Save Memory of the Diagnosis
            from app.core.memory_base import memory_base
            memory_base.add_memory(
                content=f"UI 缺陷诊断特征库: 遇到报错 {error_msg} 时，诊断根因为 {failure_type}。推理逻辑: {res.get('reasoning', '')}",
                user_id=state.get("execution_id", "default_execution_user"),
                project_id="default_proj"
            )
            
            return {"failure_type": failure_type}
            
        except Exception as e:
            logger.error(f"Sherlock failed: {e}")
            return {
                "failure_type": self._classify_failure_heuristic(
                    state.get("error", "")
                )
            }

    async def node_healer(self, state: AgentState) -> Dict[str, Any]:
        """
        [Node] 自愈修正: Call Healer to propose a fix based on Sherlock's RCA.
        """
        logger.info("--- [Node: Healer] ---")
        current_retries = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 1)
        autogen_status = get_autogen_runtime_status()
        if not autogen_status.available:
            logger.warning(f"Skipping AutoGen Healer: {autogen_status.reason}")
            return {"error": "AutoGen healer unavailable", "failure_type": "ABORT"}
        
        if current_retries >= max_retries:
            logger.warning("Max retries reached. Aborting.")
            # Set failure_type to NONE so the edge defaults to END, stopping the loop
            return {"error": f"Max retries ({max_retries}) reached", "failure_type": "ABORT"}

        # Fast-path recovery for ad/pop-up hijack redirects.
        if state.get("failure_type") == "ENVIRONMENT_ISSUE" and state.get("task_url"):
            from app.schemas.execution import AUIIR

            back_action = AUIIR(
                action_type="navigate",
                target=None,
                params={"url": state["task_url"]},
                expected_visual_change=f"Return to {state['task_url']}",
            )
            return {
                "retry_count": current_retries + 1,
                "action_intent": back_action,
                "error": None,
                "failure_type": None,
                "use_existing_action": True,
            }
            
        try:
            import autogen
            from app.engines.right_pupil.agents.healer import HealerAgent
            from app.schemas.execution import AUIIR
            from app.core.config import settings
            
            from app.services.smart_ops.ai_config_service import AIConfigService
            from app.core.ai_models import AIModule
            
            cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_HEALER)
            llm_config = {
                "config_list": [{
                    "model": cfg.model_id,
                    "api_key": settings.QWEN_API_KEY,
                    "base_url": settings.QWEN_BASE_URL
                }],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            }
            healer = HealerAgent("交互纠偏师_Healer", llm_config)
            admin = autogen.UserProxyAgent(
                "Admin",
                human_input_mode="NEVER",
                code_execution_config=False,
                max_consecutive_auto_reply=1
            )
            
            from app.engines.right_pupil.agents.librarian import search_knowledge_base
            # self._register_tool_if_supported(
            #     autogen,
            #     func=search_knowledge_base,
            #     caller=healer,
            #     executor=admin,
            #     name="search_knowledge_base",
            #     description="Search the knowledge base for historical state fixes, known environment issues, and recovery paths.",
            # )
            
            failure_type = state.get("failure_type", "UNKNOWN_ERROR")
            history = state.get("history", [])
            last_action = history[-1] if history else {}
            som_text = state.get("som_text", "")
            
            prompt = f"Failure Type: {failure_type}\nLast Action: {json.dumps(last_action)}\nCurrent SoM:\n{som_text}\nPlease propose a fixing action in strict JSON."
            
            await self._initiate_chat_async(admin, healer, prompt)
            
            messages = self._get_agent_messages(admin, healer)
            fallback_message = self._extract_message_text(healer.last_message())
            res = self._parse_agent_json_response(
                messages,
                required_keys=["action_type"],
                fallback_message=fallback_message,
            )
            if res.get("action_type") == "abort":
                return {"retry_count": current_retries + 1, "error": "Healer aborted", "failure_type": "ABORT"}
                
            action = AUIIR(**res)
            logger.info(f"Healer proposed fix: {action.action_type}")
            
            # Scribe: Save Memory of the Fix
            from app.core.memory_base import memory_base
            memory_base.add_memory(
                content=f"UI 自愈成功经验: 当遭遇 {failure_type} 且任务为 {state.get('task_description')} 时，成功使用了动作: {json.dumps(res, ensure_ascii=False)}",
                user_id=state.get("execution_id", "default_execution_user"), 
                project_id="default_proj" 
            )
            
            # Update state: clear error and failure type to allow a clean retry of node_act
            # We don't go back to node_reason; the Healer outputs the new action bypass.
            return {
                "retry_count": current_retries + 1,
                "action_intent": action,
                "error": None,
                "failure_type": None,
                "use_existing_action": True,
            }
            
        except Exception as e:
            logger.error(f"Healer failed: {e}")
            return {"retry_count": current_retries + 1, "error": f"Healer error: {e}", "failure_type": "ABORT"}


    async def execute_step(self, description: str, url: str = None, execution_id: str = None) -> Dict[str, Any]:
        """
        单步 AI 执行 — Dispatcher 调用入口 (Refactored to LangGraph)
        
        将自然语言描述交给 AI Agent 执行。基于 LangGraph 的状态机完成感知、决策、执行与自愈。
        """
        if not hasattr(self, 'page') or not self.page:
            raise RuntimeError("Session not started. Call start_session() first.")
            
        logger.info(f"🔄 [execute_step] Starting LangGraph for: {description}")
        
        # 1. Initialize State
        initial_state: AgentState = {
            "task_description": description,
            "task_url": url,
            "execution_id": execution_id,
            "history": [],
            "current_screenshot": None,
            "current_dom": None,
            "som_text": None,
            "annotated_screenshot": None,
            "id_map": {},
            "action_intent": None,
            "action_result": None,
            "error": None,
            "failure_type": None,
            "use_existing_action": False,
            "retry_count": 0,
            "max_retries": 1
        }
        
        try:
            # 2. Invoke Graph (Async)
            final_state = await self.graph.ainvoke(initial_state)
            
            # 3. Format Result for Dispatcher
            success = False
            action_taken = None
            target_description = None
            
            history = final_state.get("history", [])
            if history:
                last_action = history[-1]
                if last_action.get("status") == "success":
                    success = True
                    act_intent = last_action.get("action", {})
                    if isinstance(act_intent, dict):
                        action_taken = act_intent.get("action_type")
                        target_dict = act_intent.get("target", {})
                        if isinstance(target_dict, dict):
                            target_description = target_dict.get("value")
                    else:
                        # Fallback for raw object
                        action_taken = getattr(act_intent, "action_type", "unknown")
                        
            # If navigate was successful directly targeting url (early exit from perceive / reason)
            if not success and final_state.get("action_intent"):
                intent = final_state["action_intent"]
                if getattr(intent, "action_type", "") == "navigate":
                    success = True
                    action_taken = "navigate"
                    target_description = url
                    
            # Did it hit evaluating error?
            error_msg = final_state.get("error")
            
            page_url = self.page.url if self.page else ""
            try:
                page_title = await self.page.title() if self.page else ""
            except Exception as title_exc:
                logger.warning(f"Failed to read page title after action: {title_exc}")
                page_title = ""

            return {
                "success": success,
                "action_taken": action_taken,
                "target_description": target_description,
                "screenshot_before": final_state.get("current_screenshot"),
                "screenshot_after": final_state.get("annotated_screenshot") or final_state.get("current_screenshot"),
                "page_url": page_url,
                "page_title": page_title,
                "strategy": "ag_langgraph",
                "error": error_msg
            }
            
        except Exception as e:
            logger.error(f"❌ [execute_step] Graph Execution Error: {e}")
            import base64
            err_b64 = None
            try:
                err_bytes = await self.page.screenshot(type="png")
                err_b64 = base64.b64encode(err_bytes).decode("utf-8")
            except:
                pass
                
            return {
                "success": False,
                "error": str(e),
                "strategy": "ag_langgraph",
                "page_url": self.page.url,
                "screenshot_after": err_b64
            }


    async def run_task(self, prompt: str, url: str) -> List[Dict[str, Any]]:
        """
        Execute automation task (Autonomous Agent Mode)
        """
        logger.info(f"🚀 RightPupil Engine Starting Task: {prompt} on {url}")
        
        await self.start_session(headless=False)
        
        history: List[Dict] = []
        
        try:
            # Navigate
            logger.info(f"Navigate to {url}")
            await self.page.goto(url)
            # await self.page.wait_for_load_state("networkidle") # Replaced by SmartWait loop
            
            step_count = 0
            while step_count < self.max_steps:
                step_count += 1
                logger.info(f"--- Step {step_count}/{self.max_steps} ---")
                
                # 0. Smart Wait (Visual + Network Stability)
                if self.waiter:
                    await self.waiter.wait_until_stable()
                
                # 1. Sensing (Screenshot -> Omni -> SoM)
                screenshot_bytes = await self.page.screenshot(type="png")
                import base64
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                
                try:
                    elements = await self.omni_client.parse_screenshot(screenshot_base64)
                except Exception as e:
                    logger.error(f"OmniParser failed: {e}")
                    break

                loop = asyncio.get_running_loop()
                annotated_base64, id_map = await loop.run_in_executor(
                    None, self.som_renderer.draw_som, screenshot_base64, elements
                )
                
                # Debug: Save annotated screenshot
                try:
                    import os
                    import time
                    debug_dir = os.path.join("local_runtime", "traces", "screenshots")
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = int(time.time())
                    filename = f"step_{step_count}_{timestamp}.png"
                    filepath = os.path.join(debug_dir, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(annotated_base64))
                    logger.info(f"Saved debug screenshot to {filepath}")
                except Exception as e:
                    logger.error(f"Failed to save debug screenshot: {e}")
                
                # ... (Construct SoM Text) ...
                som_text_lines = []
                for k, v in id_map.items():
                    bbox = v.get('bbox', [0, 0, 0, 0])
                    w = int(bbox[2] - bbox[0])
                    h = int(bbox[3] - bbox[1])
                    som_text_lines.append(f"ID {k}: [{w}x{h}] {v.get('label')} {v.get('content', '')}")
                som_text = "\n".join(som_text_lines)

                # --- Right Pupil 3.0: Hybrid Perception & Semantic Description ---
                points = []
                for k, v in id_map.items():
                    bbox = v.get('bbox', [0, 0, 0, 0])
                    cx = (bbox[0] + bbox[2]) / 2.0
                    cy = (bbox[1] + bbox[3]) / 2.0
                    points.append({"x": cx, "y": cy})

                dom_hints = []
                if points:
                    try:
                        dom_hints = await self.dom_service.get_dom_hints_from_points(self.page, points)
                    except Exception as e:
                        logger.warning(f"Failed to fetch DOM hints: {e}")
                        dom_hints = [None] * len(points)

                describer_input = []
                for j, (k, v) in enumerate(id_map.items()):
                    item = {
                        "id": int(k),
                        "bbox": [int(x) for x in v.get("bbox", [0, 0, 0, 0])],
                        "ocr": v.get("content", "")
                    }
                    if j < len(dom_hints) and dom_hints[j]:
                        item["dom_hint"] = dom_hints[j]
                    describer_input.append(item)

                semantic_elements_str = "[]"
                autogen_status = get_autogen_runtime_status()
                if autogen_status.available:
                     try:
                         import autogen, json, re
                         from app.engines.right_pupil.agents.element_describer import ElementDescriberAgent
                         from app.services.smart_ops.ai_config_service import AIConfigService
                         from app.core.ai_models import AIModule
                         from app.core.config import settings

                         desc_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_VISUAL)
                         desc_llm_config = {
                              "config_list": [{
                                  "model": desc_cfg.model_id,
                                  "api_key": settings.QWEN_API_KEY,
                                  "base_url": settings.QWEN_BASE_URL
                              }],
                              "temperature": 0.1,
                              "max_tokens": desc_cfg.max_tokens,
                         }

                         describer = ElementDescriberAgent("ElementDescriber", desc_llm_config)
                         admin = autogen.UserProxyAgent("Admin", human_input_mode="NEVER", code_execution_config=False, max_consecutive_auto_reply=1)

                         desc_prompt = f"Please translate the following elements into semantic descriptions:\n{json.dumps(describer_input, ensure_ascii=False)}"
                         await self._initiate_chat_async(admin, describer, desc_prompt)

                         last_msg = self._extract_message_text(describer.last_message())
                         json_match = re.search(r'```(?:json)?\n(.*)\n```', last_msg, re.DOTALL)
                         if json_match:
                             semantic_elements_str = json_match.group(1).strip()
                         else:
                             match = re.search(r'(\[.*\])', last_msg, re.DOTALL)
                             semantic_elements_str = match.group(1).strip() if match else last_msg

                         logger.info(f"Element Describer output computed successfully: {len(semantic_elements_str)} chars")
                     except Exception as e:
                         logger.error(f"Element Describer Agent failed: {e}. Falling back to RAW JSON.")
                         semantic_elements_str = json.dumps(describer_input, ensure_ascii=False)
                else:
                     semantic_elements_str = json.dumps(describer_input, ensure_ascii=False)

                # 2. Planning
                action = await self.planner.plan_next_step(prompt, annotated_base64, som_text, history)

                # 2.1 Task-aware action correction
                if action and action.action_type != "done":
                    action = self._correct_action_type(action, prompt)

                    if not action:
                        break

                    if action.action_type == "done":
                        break

                    # 3. Execution with Self-Healing Loop
                    max_retries = 1
                    retry_count = 0
                    step_success = False

                    while retry_count <= max_retries:
                        success = await self.runner.execute(action, id_map)

                        if success:
                            history.append({"step": step_count, "action": action.model_dump(), "status": "success"})
                            step_success = True
                            break
                        else:
                            logger.warning(f"Action failed. Attempting Self-Healing (Retry {retry_count + 1}/{max_retries + 1})...")
                            retry_count += 1

                            # --- Healing Strategy 1: Environment Healing (Popup Killer) ---
                            # Check if failure might be due to popup (simplistic check: re-sense)
                            # In a real impl, we'd check error type (ElementIntercepted).
                            # Here we blindly try to find a "Close" button if action failed.
                            logger.info("🛡️ Attempting Environment Healing (Popup Killer)...")

                            # Re-sense to see popup
                            screenshot_bytes_h = await self.page.screenshot(type="png")
                            import base64
                            screenshot_base64_h = base64.b64encode(screenshot_bytes_h).decode("utf-8")
                            try:
                                elements_h = await self.omni_client.parse_screenshot(screenshot_base64_h)
                                loop = asyncio.get_running_loop()
                                _, id_map_h = await loop.run_in_executor(
                                    None, self.som_renderer.draw_som, screenshot_base64_h, elements_h
                                )

                                # specific logic to find X / Close
                                # This is a heuristic: look for "close", "cancel", "x" in content or label
                                popup_close_id = None
                                for pid, pinfo in id_map_h.items():
                                    label = pinfo.get('label', '').lower()
                                    content = pinfo.get('content', '').lower()
                                    if any(k in label or k in content for k in ['close', '关闭', 'cancel', '取消']):
                                         # Simple heuristic: usually popups are on top (high z-index), but Omni doesn't give z-index.
                                         # We just try clicking it.
                                         popup_close_id = pid
                                         break

                                if popup_close_id:
                                    logger.info(f"Found potential popup close button: ID {popup_close_id}")
                                    # Execute Close
                                    close_action = action.model_copy(deep=True) # Deep copy to avoid mutating original action
                                    close_action.action_type = "click"
                                    close_action.target.strategy = "visual"
                                    close_action.target.value = str(popup_close_id)
                                    await self.runner.execute(close_action, id_map_h)
                                    await asyncio.sleep(1) # Wait for popup to close
                                    continue # Retry original action loop

                            except Exception as e:
                                logger.error(f"Environment Healing failed: {e}")

                            # --- Healing Strategy 3: Data Healing (Input Regeneration) ---
                            if action.action_type == "type":
                                logger.info("🧪 Attempting Data Healing (Regenerate Value)...")
                                # Heuristic: use description or locator value as field name hint
                                field_hint = action.target.description or action.target.value or "input_field"
                                new_value = self.data_synthesizer.generate_value(field_hint, context="Previous input caused failure")

                                logger.info(f"Regenerated value for {field_hint}: {new_value}")

                                data_action = action.model_copy(deep=True)
                                data_action.params["text"] = new_value
                                success_data = await self.runner.execute(data_action, id_map)

                                if success_data:
                                    history.append({"step": step_count, "action": data_action.model_dump(), "status": "healed_data"})
                                    step_success = True
                                    break

                            # --- Healing Strategy 2: Locator Healing (Visual -> DOM Fallback) ---
                            logger.info("🩹 Attempting Locator Healing (Visual -> DOM)...")
                            # Capture fresh state for DOM analysis
                            dom_tree = await self.dom_service.get_clickable_elements(self.page)
                            fallback_action = await self.planner.plan_fallback_step(
                                task=prompt,
                                dom_tree=dom_tree,
                                screenshot_base64=screenshot_base64 # Reuse original screenshot or new?
                            )

                            if fallback_action:
                                logger.info(f"Fallback Plan Generated: {fallback_action.action_type} on {fallback_action.target.value}")
                                # Execute fallback immediately (it counts as the retry attempt)
                                success_fb = await self.runner.execute(fallback_action, {}) # DOM doesn't need ID map
                                if success_fb:
                                    history.append({"step": step_count, "action": fallback_action.model_dump(), "status": "healed"})
                                    step_success = True
                                    break

                            logger.error("All healing attempts failed.")

                    if not step_success:
                        history.append({"step": step_count, "action": action.model_dump(), "status": "failed"})
                        break

                    # await asyncio.sleep(2) # Replaced by SmartWait loop start

        except Exception as e:
            logger.error(f"Engine Loop Error: {e}")
        finally:
            logs = self.runner.trace_logs if self.runner else []
            await self.stop_session()
            
        return logs
