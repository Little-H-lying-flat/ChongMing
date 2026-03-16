"""
UI Runner (The Hands)
右瞳引擎执行器

负责执行基于视觉或 DOM 的操作指令。
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from playwright.async_api import Page

from app.schemas.aui_ir import VisualActionIR, VisualLocator
from app.engines.vision.dom_service import DomService

logger = logging.getLogger(__name__)

class UiRunner:
    """
    UI 动作执行器
    """
    
    def __init__(self, page: Page, dom_service: DomService):
        self.page = page
        self.dom_service = dom_service
        self.trace_logs: List[Dict[str, Any]] = []

    @staticmethod
    def _normalize_semantic_hint(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
        return re.sub(r"\s+", " ", normalized).strip()

    async def _resolve_semantic_click_target(
        self,
        *,
        x: float,
        y: float,
        semantic_hint: str,
    ) -> Optional[Dict[str, Any]]:
        hint = self._normalize_semantic_hint(semantic_hint)
        if not hint:
            return None

        try:
            return await self.page.evaluate(
                """
                ({ x, y, semanticHint }) => {
                    const hint = semanticHint;
                    if (!hint) return null;

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

                    function isClickable(element) {
                        if (!element) return false;
                        const tag = element.tagName.toLowerCase();
                        if (["button", "a", "summary"].includes(tag)) return true;
                        if (tag === "input" && ["button", "submit", "reset"].includes((element.type || "").toLowerCase())) return true;
                        const role = (element.getAttribute("role") || "").toLowerCase();
                        if (["button", "link", "menuitem", "tab"].includes(role)) return true;
                        return false;
                    }

                    function clickableRoot(element) {
                        let current = element;
                        for (let i = 0; i < 6 && current; i += 1) {
                            if (isClickable(current)) return current;
                            current = current.parentElement;
                        }
                        return null;
                    }

                    function signature(element) {
                        if (!element) return "";
                        return normalize(
                            element.innerText ||
                            element.getAttribute("aria-label") ||
                            element.getAttribute("data-test") ||
                            element.value ||
                            element.textContent ||
                            element.tagName
                        );
                    }

                    function contextScore(element) {
                        let current = element;
                        for (let depth = 0; depth < 6 && current; depth += 1) {
                            const text = normalize(
                                current.getAttribute("aria-label") ||
                                current.getAttribute("data-test") ||
                                current.innerText ||
                                current.textContent
                            );
                            if (text.includes(hint)) {
                                return 200 - depth * 20;
                            }
                            current = current.parentElement;
                        }
                        return 0;
                    }

                    const anchor = clickableRoot(document.elementFromPoint(x, y));
                    const anchorSignature = signature(anchor);
                    if (!anchor || !anchorSignature) return null;

                    const candidateSet = new Set();
                    for (const element of document.querySelectorAll("button, a, input[type='button'], input[type='submit'], [role='button'], [role='link'], [role='menuitem'], [role='tab']")) {
                        const root = clickableRoot(element);
                        if (root && isVisible(root)) candidateSet.add(root);
                    }

                    let best = null;
                    for (const candidate of candidateSet) {
                        if (signature(candidate) !== anchorSignature) continue;

                        const rect = candidate.getBoundingClientRect();
                        const cx = rect.left + rect.width / 2;
                        const cy = rect.top + rect.height / 2;
                        const distancePenalty = Math.sqrt((cx - x) ** 2 + (cy - y) ** 2) / 10;
                        const score = contextScore(candidate) - distancePenalty;
                        if (score <= 0) continue;

                        if (!best || score > best.score) {
                            best = {
                                x: cx,
                                y: cy,
                                score,
                            };
                        }
                    }

                    return best;
                }
                """,
                {"x": x, "y": y, "semanticHint": hint},
            )
        except Exception as exc:
            logger.warning(f"Semantic click disambiguation failed: {exc}")
            return None

    async def _resolve_semantic_input_target(
        self,
        *,
        x: float,
        y: float,
        field_hint: str,
    ) -> Optional[Dict[str, Any]]:
        hint = self._normalize_semantic_hint(field_hint)
        if not hint:
            return None

        try:
            return await self.page.evaluate(
                """
                ({ x, y, fieldHint }) => {
                    const hint = fieldHint;
                    if (!hint) return null;

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

                    const candidates = Array.from(
                        document.querySelectorAll(
                            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"]):not([type="image"]), textarea, [contenteditable="true"], [role="textbox"], [role="searchbox"], [role="combobox"]'
                        )
                    ).filter(isVisible);

                    let best = null;
                    for (const candidate of candidates) {
                        const labels = labelText(candidate);
                        const matchScore = labels.includes(hint) ? 300 : 0;
                        if (!matchScore) continue;

                        const rect = candidate.getBoundingClientRect();
                        const cx = rect.left + rect.width / 2;
                        const cy = rect.top + rect.height / 2;
                        const distancePenalty = Math.sqrt((cx - x) ** 2 + (cy - y) ** 2) / 10;
                        const score = matchScore - distancePenalty;

                        if (!best || score > best.score) {
                            best = {
                                x: cx,
                                y: cy,
                                score,
                            };
                        }
                    }

                    if (best) return best;

                    const fallback = editableRoot(document.elementFromPoint(x, y));
                    if (!fallback || !isVisible(fallback)) return null;

                    const rect = fallback.getBoundingClientRect();
                    return {
                        x: rect.left + rect.width / 2,
                        y: rect.top + rect.height / 2,
                        score: 0,
                    };
```
                }
                """,
                {"x": x, "y": y, "fieldHint": hint},
            )
        except Exception as exc:
            logger.warning(f"Semantic input disambiguation failed: {exc}")
            return None
        """处理交互逻辑 (Click, Type, etc.)"""
        target = action.target
        strategy = target.strategy
        semantic_hint = action.params.get("semantic_hint") if isinstance(action.params, dict) else None
        
        x, y = 0, 0
        selector = None
        
        # A. Visual Strategy (通过 ID Map 获取坐标)
        if strategy == "visual":
            # value 应为 SoM ID (string or int)
            try:
                visual_id = int(target.value)
            except (ValueError, TypeError):
                 raise ValueError(f"Visual strategy requires integer ID, got {target.value}")

            if not id_map or visual_id not in id_map:
                raise ValueError(f"Visual ID {visual_id} not found in current frame")
            
            element_info = id_map[visual_id]
            x, y = element_info["center"]
            trace_entry["coords"] = {"x": x, "y": y}
            
            # 关键：嗅探 Selector 以增强稳定性
            selector = await self.dom_service.sniff_selector(self.page, x, y)
            if selector:
                trace_entry["stable_selector"] = selector
                logger.info(f"Sniffed selector for visual element {visual_id}: {selector}")
            
            # 执行动作 (优先使用 Playwright 的 locator 如果嗅探成功，否则用坐标)
            # 策略：为了模拟最真实的视觉操作，且 OmniParser 坐标通常即见即所得，
            # 我们优先使用坐标点击。如果失败再考虑 selector。
            # 但用户提示词要求： "在点击前调用 sniff_selector... 然后执行 page.mouse.click"
            # 这意味着 sniff 主要是为了记录(trace)和可能的后续恢复，但动作本身是用鼠标坐标。
            
            if action.action_type in ["click", "dblclick", "hover"] and semantic_hint:
                resolved_target = await self._resolve_semantic_click_target(
                    x=x,
                    y=y,
                    semantic_hint=semantic_hint,
                )
                if resolved_target:
                    x, y = resolved_target["x"], resolved_target["y"]
                    trace_entry["semantic_target"] = semantic_hint
                    trace_entry["semantic_resolution"] = {
                        "x": x,
                        "y": y,
                        "score": resolved_target.get("score"),
                    }
                    logger.info(
                        "Semantic click disambiguation relocated target to "
                        f"({x:.1f}, {y:.1f}) for hint '{semantic_hint}'"
                    )

            if action.action_type == "click":
                await self.page.mouse.click(x, y)
            elif action.action_type == "dblclick":
                await self.page.mouse.dblclick(x, y)
            elif action.action_type == "hover":
                await self.page.mouse.move(x, y)
            elif action.action_type == "type":
                text = action.params.get("text", "")
                field_hint = action.params.get("field_hint") if isinstance(action.params, dict) else None
                if field_hint:
                    resolved_input = await self._resolve_semantic_input_target(
                        x=x,
                        y=y,
                        field_hint=field_hint,
                    )
                    if resolved_input:
                        x, y = resolved_input["x"], resolved_input["y"]
                        trace_entry["field_hint"] = field_hint
                        trace_entry["input_resolution"] = {
                            "x": x,
                            "y": y,
                            "score": resolved_input.get("score"),
                        }
                        logger.info(
                            "Semantic input disambiguation relocated target to "
                            f"({x:.1f}, {y:.1f}) for hint '{field_hint}'"
                        )
                
                # ═══════════════════════════════════════════
                # Smart Input Focus (Layer 2) — JS-First
                # ═══════════════════════════════════════════
                # CRITICAL: Do NOT mouse.click on icon coordinates — this can
                # trigger navigation (e.g. Bing search icon) and destroy context.
                # Instead, use JS to find and focus the nearest input element directly.
                
                focus_result = await self.page.evaluate("""
                    ({x, y}) => {
                        // 1. Check what's at (x, y)
                        const el = document.elementFromPoint(x, y);
                        
                        // 2. Helper: is this element editable?
                        function isEditable(e) {
                            if (!e) return false;
                            const tag = e.tagName.toLowerCase();
                            return (
                                tag === 'input' && !['hidden','submit','button','checkbox','radio','image'].includes(e.type) ||
                                tag === 'textarea' ||
                                e.contentEditable === 'true' ||
                                e.getAttribute('role') === 'textbox' ||
                                e.getAttribute('role') === 'searchbox' ||
                                e.getAttribute('role') === 'combobox'
                            );
                        }
                        
                        // 3. If element at point is editable, focus it directly
                        if (isEditable(el)) {
                            el.focus();
                            el.click();
                            const r = el.getBoundingClientRect();
                            return {
                                success: true,
                                tag: el.tagName.toLowerCase(),
                                relocated: false,
                                x: r.left + r.width / 2,
                                y: r.top + r.height / 2
                            };
                        }
                        
                        // 4. Walk up the DOM tree — maybe the input wraps the icon
                        let parent = el ? el.parentElement : null;
                        for (let i = 0; i < 5 && parent; i++) {
                            if (isEditable(parent)) {
                                parent.focus();
                                parent.click();
                                const r = parent.getBoundingClientRect();
                                return {
                                    success: true,
                                    tag: parent.tagName.toLowerCase(),
                                    relocated: true,
                                    x: r.left + r.width / 2,
                                    y: r.top + r.height / 2
                                };
                            }
                            parent = parent.parentElement;
                        }
                        
                        // 5. Search nearby for the nearest editable element
                        const candidates = document.querySelectorAll(
                            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"]):not([type="image"]), ' +
                            'textarea, [contenteditable="true"], [role="textbox"], [role="searchbox"], [role="combobox"]'
                        );
                        
                        let nearest = null;
                        let minDist = Infinity;
                        
                        for (const c of candidates) {
                            const r = c.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) continue;
                            const cx = r.left + r.width / 2;
                            const cy = r.top + r.height / 2;
                            const dist = Math.sqrt((cx - x) ** 2 + (cy - y) ** 2);
                            if (dist < 400 && dist < minDist) {
                                minDist = dist;
                                nearest = c;
                            }
                        }
                        
                        if (nearest) {
                            nearest.focus();
                            nearest.click();
                            const r = nearest.getBoundingClientRect();
                            return {
                                success: true,
                                tag: nearest.tagName.toLowerCase(),
                                relocated: true,
                                x: r.left + r.width / 2,
                                y: r.top + r.height / 2
                            };
                        }
                        
                        return { success: false };
                    }
                """, {"x": x, "y": y})
                
                if focus_result and focus_result.get("success"):
                    tag = focus_result.get("tag", "?")
                    if focus_result.get("relocated"):
                        fx, fy = focus_result["x"], focus_result["y"]
                        logger.warning(f"🎯 JS direct focus: ({x},{y}) → <{tag}> at ({fx},{fy})")
                        trace_entry["relocated_to"] = {"x": fx, "y": fy}
                    else:
                        logger.info(f"✅ JS direct focus on <{tag}> at ({x},{y})")
                    
                    # Small delay for focus events to settle
                    await asyncio.sleep(0.2)
                    
                    # Select all existing text and clear
                    await self.page.keyboard.press("Control+a")
                    await asyncio.sleep(0.1)
                    
                    # Type the text
                    await self.page.keyboard.type(text, delay=50)
                else:
                    # Absolute fallback: click original coords + type (risky but last resort)
                    logger.warning(f"⚠️ JS focus failed, falling back to mouse.click({x},{y}) + type")
                    await self.page.mouse.click(x, y)
                    await asyncio.sleep(0.3)
                    await self.page.keyboard.type(text, delay=50)

        # B. DOM Strategy (传统 Selector)
        elif strategy == "dom":
            selector = target.value
            if not selector:
                raise ValueError("DOM strategy requires a selector value")
            
            trace_entry["stable_selector"] = selector
            locator = self.page.locator(selector).first
            
            if action.action_type == "click":
                await locator.click()
            elif action.action_type == "dblclick":
                await locator.dblclick()
            elif action.action_type == "hover":
                await locator.hover()
            elif action.action_type == "type":
                text = action.params.get("text", "")
                await locator.fill(text)

        # C. Point Strategy (直接坐标)
        elif strategy == "point":
            # value 可能是 "x,y"
            if target.bbox:
                # 使用 bbox 中心
                x = (target.bbox[0] + target.bbox[2]) / 2
                y = (target.bbox[1] + target.bbox[3]) / 2
            elif "," in str(target.value):
                parts = str(target.value).split(",")
                x, y = float(parts[0]), float(parts[1])
            else:
                raise ValueError("Point strategy requires bbox or 'x,y' value")

            trace_entry["coords"] = {"x": x, "y": y}
            if action.action_type == "click":
                await self.page.mouse.click(x, y)
            elif action.action_type == "type":
                await self.page.mouse.click(x, y)
                await self.page.keyboard.type(action.params.get("text", ""))

        else:
            raise NotImplementedError(f"Strategy {strategy} not supported yet")

    # ═══════════════════════════════════════════
    # Smart Input Relocation (Layer 2)
    # ═══════════════════════════════════════════
    async def _find_input_at_or_near(self, x: float, y: float, radius: int = 200) -> Optional[Dict]:
        """
        检查 (x, y) 处的元素是否为输入框。
        如果不是，在附近 radius 像素范围内搜索最近的 input/textarea。
        
        Returns:
            {"x": float, "y": float, "tag": str, "relocated": bool} or None
        """
        try:
            result = await self.page.evaluate("""
                ({x, y, radius}) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    
                    // Check if current element is editable
                    const tag = el.tagName.toLowerCase();
                    const isEditable = (
                        tag === 'input' || 
                        tag === 'textarea' || 
                        el.contentEditable === 'true' ||
                        el.getAttribute('role') === 'textbox' ||
                        el.getAttribute('role') === 'searchbox'
                    );
                    
                    if (isEditable) {
                        const rect = el.getBoundingClientRect();
                        return {
                            x: rect.left + rect.width / 2,
                            y: rect.top + rect.height / 2,
                            tag: tag,
                            relocated: false
                        };
                    }
                    
                    // Not editable — search nearby for input/textarea
                    const candidates = document.querySelectorAll(
                        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"]), ' +
                        'textarea, ' +
                        '[contenteditable="true"], ' +
                        '[role="textbox"], ' +
                        '[role="searchbox"]'
                    );
                    
                    let nearest = null;
                    let minDist = Infinity;
                    
                    for (const c of candidates) {
                        const r = c.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) continue;
                        
                        const cx = r.left + r.width / 2;
                        const cy = r.top + r.height / 2;
                        const dist = Math.sqrt((cx - x) ** 2 + (cy - y) ** 2);
                        
                        if (dist < radius && dist < minDist) {
                            minDist = dist;
                            nearest = {
                                x: cx,
                                y: cy,
                                tag: c.tagName.toLowerCase(),
                                relocated: true
                            };
                        }
                    }
                    
                    return nearest;
                }
            """, {"x": x, "y": y, "radius": radius})
            return result
        except Exception as e:
            logger.error(f"Smart input relocation failed: {e}")
            return None
