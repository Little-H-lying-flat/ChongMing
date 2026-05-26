"""
UI Runner.

Responsible for executing low-level browser actions for Visual UI automation.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import Page

from app.engines.vision.dom_service import DomService
from app.schemas.aui_ir import VisualActionIR


logger = logging.getLogger(__name__)


class UiRunner:
    """Execute UI actions against the current Playwright page."""

    def __init__(self, page: Page, dom_service: DomService):
        self.page = page
        self.dom_service = dom_service
        self.trace_logs: List[Dict[str, Any]] = []

    @staticmethod
    def _normalize_semantic_hint(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _center_from_bbox(bbox: List[float]) -> Tuple[float, float]:
        return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0

    async def _resolve_visual_target(
        self,
        action: VisualActionIR,
        id_map: Dict[int, Dict[str, Any]],
        trace_entry: Dict[str, Any],
    ) -> Tuple[float, float, Optional[str]]:
        target = action.target
        if not target or target.value is None:
            raise ValueError("Visual strategy requires target.value")

        try:
            visual_id = int(str(target.value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Visual strategy requires integer ID, got {target.value}") from exc

        if visual_id not in id_map:
            raise ValueError(f"Visual ID {visual_id} not found in current frame")

        element_info = id_map[visual_id]
        if "center" in element_info:
            x, y = element_info["center"]
        elif "bbox" in element_info and len(element_info["bbox"]) == 4:
            x, y = self._center_from_bbox(element_info["bbox"])
        else:
            raise ValueError(f"Visual target {visual_id} missing center/bbox")

        selector = await self.dom_service.sniff_selector(self.page, x, y)
        trace_entry["coords"] = {"x": x, "y": y}
        if selector:
            trace_entry["stable_selector"] = selector
        return x, y, selector

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
                        return ["button", "link", "menuitem", "tab"].includes(role);
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
                            if (text.includes(hint)) return 200 - depth * 20;
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
                            best = { x: cx, y: cy, score };
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
                            best = { x: cx, y: cy, score };
                        }
                    }

                    return best;
                }
                """,
                {"x": x, "y": y, "fieldHint": hint},
            )
        except Exception as exc:
            logger.warning(f"Semantic input disambiguation failed: {exc}")
            return None

    async def _focus_and_type_by_point(self, x: float, y: float, text: str) -> None:
        focus_result = await self.page.evaluate(
            """
            ({x, y}) => {
                function isEditable(e) {
                    if (!e) return false;
                    const tag = e.tagName.toLowerCase();
                    const role = (e.getAttribute("role") || "").toLowerCase();
                    return (
                        (tag === "input" && !["hidden","submit","button","checkbox","radio","image"].includes((e.type || "").toLowerCase())) ||
                        tag === "textarea" ||
                        e.contentEditable === "true" ||
                        ["textbox", "searchbox", "combobox"].includes(role)
                    );
                }

                const el = document.elementFromPoint(x, y);
                let target = el;
                for (let i = 0; i < 5 && target; i += 1) {
                    if (isEditable(target)) break;
                    target = target.parentElement;
                }

                if (!target || !isEditable(target)) {
                    const candidates = document.querySelectorAll(
                        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"]):not([type="image"]), textarea, [contenteditable="true"], [role="textbox"], [role="searchbox"], [role="combobox"]'
                    );
                    let nearest = null;
                    let minDist = Infinity;
                    for (const candidate of candidates) {
                        const r = candidate.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) continue;
                        const cx = r.left + r.width / 2;
                        const cy = r.top + r.height / 2;
                        const dist = Math.sqrt((cx - x) ** 2 + (cy - y) ** 2);
                        if (dist < 400 && dist < minDist) {
                            minDist = dist;
                            nearest = candidate;
                        }
                    }
                    target = nearest;
                }

                if (!target || !isEditable(target)) return { success: false };
                target.focus();
                if (target.select) target.select();
                const rect = target.getBoundingClientRect();
                return {
                    success: true,
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2,
                };
            }
            """,
            {"x": x, "y": y},
        )

        if not focus_result or not focus_result.get("success"):
            raise ValueError("Unable to focus editable field near target point")

        await asyncio.sleep(0.15)
        await self.page.keyboard.press("Control+a")
        await asyncio.sleep(0.05)
        await self.page.keyboard.type(text, delay=35)

    async def _execute_visual_action(
        self,
        action: VisualActionIR,
        id_map: Dict[int, Dict[str, Any]],
        trace_entry: Dict[str, Any],
    ) -> None:
        x, y, selector = await self._resolve_visual_target(action, id_map, trace_entry)
        params = action.params or {}

        if action.action_type in {"click", "dblclick", "hover"}:
            semantic_hint = params.get("semantic_hint")
            if semantic_hint:
                resolved = await self._resolve_semantic_click_target(
                    x=x,
                    y=y,
                    semantic_hint=str(semantic_hint),
                )
                if resolved:
                    x, y = resolved["x"], resolved["y"]
                    trace_entry["semantic_resolution"] = resolved

            if action.action_type == "click":
                await self.page.mouse.click(x, y)
            elif action.action_type == "dblclick":
                await self.page.mouse.dblclick(x, y)
            else:
                await self.page.mouse.move(x, y)
            return

        if action.action_type == "type":
            text = str(params.get("text", ""))
            if not text or text == "<needs_value>":
                raise ValueError("Type action missing concrete params.text")

            field_hint = params.get("field_hint")
            if field_hint:
                resolved = await self._resolve_semantic_input_target(
                    x=x,
                    y=y,
                    field_hint=str(field_hint),
                )
                if resolved:
                    x, y = resolved["x"], resolved["y"]
                    trace_entry["input_resolution"] = resolved

            if selector:
                try:
                    locator = self.page.locator(selector).first
                    if await locator.count() > 0:
                        await locator.fill(text)
                        return
                except Exception:
                    logger.debug("Selector-based fill failed; falling back to point typing.")

            await self._focus_and_type_by_point(x, y, text)
            return

        if action.action_type == "press":
            await self.page.mouse.click(x, y)
            key = str(params.get("key", "Enter"))
            await self.page.keyboard.press(key)
            return

        raise NotImplementedError(f"Unsupported visual action: {action.action_type}")

    async def _execute_dom_action(
        self,
        action: VisualActionIR,
        trace_entry: Dict[str, Any],
    ) -> None:
        selector = getattr(action.target, "value", None)
        if not selector:
            raise ValueError("DOM strategy requires selector target.value")

        selector = str(selector)
        trace_entry["stable_selector"] = selector
        locator = self.page.locator(selector).first
        params = action.params or {}

        if action.action_type == "click":
            await locator.click()
        elif action.action_type == "dblclick":
            await locator.dblclick()
        elif action.action_type == "hover":
            await locator.hover()
        elif action.action_type == "type":
            text = str(params.get("text", ""))
            if not text or text == "<needs_value>":
                raise ValueError("Type action missing concrete params.text")
            await locator.fill(text)
        elif action.action_type == "press":
            await locator.press(str(params.get("key", "Enter")))
        elif action.action_type == "wait":
            timeout_ms = int(params.get("timeout_ms") or params.get("timeout") or 5000)
            await locator.wait_for(state="visible", timeout=timeout_ms)
        elif action.action_type == "assert_visible":
            if await locator.count() < 1:
                raise AssertionError(f"Element not found: {selector}")
            if not await locator.is_visible():
                raise AssertionError(f"Element not visible: {selector}")
        elif action.action_type == "assert_text":
            expected = str(params.get("text") or params.get("expected") or "")
            actual = await locator.text_content() or ""
            if expected and expected not in actual:
                raise AssertionError(f"Expected text '{expected}' not found in '{actual}'")
        else:
            raise NotImplementedError(f"Unsupported DOM action: {action.action_type}")

    async def _execute_point_action(
        self,
        action: VisualActionIR,
        trace_entry: Dict[str, Any],
    ) -> None:
        target = action.target
        if target and target.bbox:
            x, y = self._center_from_bbox([float(v) for v in target.bbox])
        elif target and target.value and "," in str(target.value):
            raw_x, raw_y = str(target.value).split(",", 1)
            x, y = float(raw_x), float(raw_y)
        else:
            raise ValueError("Point strategy requires bbox or 'x,y' target.value")

        trace_entry["coords"] = {"x": x, "y": y}
        params = action.params or {}

        if action.action_type == "click":
            await self.page.mouse.click(x, y)
        elif action.action_type == "hover":
            await self.page.mouse.move(x, y)
        elif action.action_type == "type":
            text = str(params.get("text", ""))
            if not text or text == "<needs_value>":
                raise ValueError("Type action missing concrete params.text")
            await self._focus_and_type_by_point(x, y, text)
        else:
            raise NotImplementedError(f"Unsupported point action: {action.action_type}")

    async def _execute_global_action(self, action: VisualActionIR, trace_entry: Dict[str, Any]) -> None:
        params = action.params or {}
        if action.action_type == "navigate":
            url = params.get("url")
            if not url:
                raise ValueError("Navigate action missing params.url")
            await self.page.goto(str(url), wait_until="domcontentloaded", timeout=30000)
            trace_entry["url"] = str(url)
            return

        if action.action_type == "wait":
            timeout_ms = int(params.get("timeout_ms") or params.get("timeout") or 1000)
            await asyncio.sleep(max(timeout_ms, 0) / 1000.0)
            return

        if action.action_type == "scroll":
            delta_x = int(params.get("delta_x", 0))
            delta_y = int(params.get("delta_y", 500))
            await self.page.mouse.wheel(delta_x, delta_y)
            return

        if action.action_type == "screenshot":
            await self.page.screenshot(type="png")
            return

        if action.action_type == "abort":
            raise RuntimeError("Action aborted by planner")

        if action.action_type == "done":
            return

        raise NotImplementedError(f"Unsupported global action: {action.action_type}")

    async def execute(self, action: VisualActionIR, id_map: Optional[Dict[int, Dict[str, Any]]] = None) -> bool:
        """
        Execute a single UI action.

        Returns `True` on success and raises on execution failure.
        """
        if not action:
            raise ValueError("Action is required")

        trace_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "action_type": action.action_type,
            "target_strategy": getattr(action.target, "strategy", None),
        }

        try:
            target = action.target
            strategy = getattr(target, "strategy", None)

            if strategy == "visual":
                await self._execute_visual_action(action, id_map or {}, trace_entry)
            elif strategy == "dom":
                await self._execute_dom_action(action, trace_entry)
            elif strategy == "point":
                await self._execute_point_action(action, trace_entry)
            else:
                await self._execute_global_action(action, trace_entry)

            trace_entry["status"] = "success"
            self.trace_logs.append(trace_entry)
            return True
        except Exception as exc:
            trace_entry["status"] = "failed"
            trace_entry["error"] = str(exc)
            self.trace_logs.append(trace_entry)
            raise
