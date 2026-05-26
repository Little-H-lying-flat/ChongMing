"""
DOM Sensing Service (In-Browser Sensing)
Visual UI 端内感知服务

负责与 Playwright 页面进行交互，执行 JS 脚本以获取简化的 DOM 结构和元素选择器。
"""

import json
import logging
from typing import Dict, Any, Optional, List
from playwright.async_api import Page, ElementHandle

logger = logging.getLogger(__name__)

# DOM 剪枝脚本
# 功能：遍历 DOM，过滤不可见元素，提取关键交互节点
_PRUNE_SCRIPT = """
() => {
    function isVisible(element) {
        if (!element) return false;
        const style = window.getComputedStyle(element);
        return style.display !== 'none' && 
               style.visibility !== 'hidden' && 
               style.opacity !== '0' &&
               element.getBoundingClientRect().width > 0 &&
               element.getBoundingClientRect().height > 0;
    }

    function isInteractive(element) {
        const tag = element.tagName.toLowerCase();
        if (['button', 'a', 'input', 'select', 'textarea', 'iframe'].includes(tag)) return true;
        if (element.getAttribute('role') === 'button') return true;
        if (element.onclick || element.getAttribute('onclick')) return true;
        return false;
    }
    
    function getAttributes(element) {
        const attrs = {};
        for (let i = 0; i < element.attributes.length; i++) {
            const attr = element.attributes[i];
            if (['id', 'name', 'class', 'type', 'placeholder', 'aria-label', 'role', 'data-testid'].includes(attr.name)) {
                attrs[attr.name] = attr.value;
            }
        }
        return attrs;
    }

    function traverse(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            const text = node.textContent.trim();
            if (text.length > 0) {
                return { type: 'text', content: text };
            }
            return null;
        }

        if (node.nodeType !== Node.ELEMENT_NODE) return null;
        
        const element = node;
        if (!isVisible(element)) return null;

        const rect = element.getBoundingClientRect();
        const nodeData = {
            tag: element.tagName.toLowerCase(),
            attrs: getAttributes(element),
            rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
            children: []
        };
        
        // 关键：对于非交互容器，尝试简化
        // 如果是交互元素，或者是包含文本的容器，保留
        
        let hasContent = false;
        for (let child of element.childNodes) {
            const childData = traverse(child);
            if (childData) {
                nodeData.children.push(childData);
                hasContent = true;
            }
        }
        
        // 如果节点既不是交互元素，也没有有意义的子节点，且没有 ID/TestID，可能可以剪枝
        // 这里简化策略：保留所有可见结构，但在 Python 端进一步处理
        return nodeData;
    }
    
    return traverse(document.body);
}
"""

# 选择器嗅探脚本
# 功能：根据坐标生成最佳 CSS Selector
_SNIFF_SCRIPT = """
(args) => {
    const { x, y } = args;
    const element = document.elementFromPoint(x, y);
    if (!element) return null;

    function generateSelector(el) {
        if (el.id) return `#${CSS.escape(el.id)}`;
        
        if (el.getAttribute('data-testid')) {
            return `[data-testid="${CSS.escape(el.getAttribute('data-testid'))}"]`;
        }
        
        if (el.name) {
            return `[name="${CSS.escape(el.name)}"]`;
        }
        
        // 尝试 tag + class
        const tag = el.tagName.toLowerCase();
        if (el.classList.length > 0) {
            for (let cls of el.classList) {
                // 忽略动态生成的 class (包含数字或过长)
                if (/\\d/.test(cls) || cls.length > 30) continue;
                // 简单组合
                return `${tag}.${CSS.escape(cls)}`; // 只需要一个稳健的 class
            }
        }
        
        // 如果是特定元素
        if (['button', 'input', 'a'].includes(tag)) {
             // 尝试通过 text content 定位 (XPath) - 这里只返回 CSS
             // 如果不行，返回层级结构 (简单版)
             let path = [];
             let current = el;
             while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.body) {
                 let selector = current.tagName.toLowerCase();
                 if (current.id) {
                     selector += `#${CSS.escape(current.id)}`;
                     path.unshift(selector);
                     break; 
                 }
                 else {
                     // 计算 nth-of-type
                     let sibling = current;
                     let nth = 1;
                     while (sibling = sibling.previousElementSibling) {
                         if (sibling.tagName === current.tagName) nth++;
                     }
                     if (nth > 1) selector += `:nth-of-type(${nth})`;
                 }
                 path.unshift(selector);
                 current = current.parentNode;
             }
             return path.join(" > ");
        }

        return tag; // 兜底

        return tag; // 兜底
    }
    
    return generateSelector(element);
}
"""

class DomService:
    """
    DOM 感知服务
    """
    
    async def get_simplified_dom(self, page: Page) -> Dict[str, Any]:
        """
        获取简化的 DOM 树
        """
        try:
            return await page.evaluate(_PRUNE_SCRIPT)
        except Exception as e:
            logger.error(f"DOM 剪枝失败: {e}")
            return {}

    async def sniff_selector(self, page: Page, x: float, y: float) -> Optional[str]:
        """
        根据坐标嗅探元素选择器
        """
        try:
            return await page.evaluate(_SNIFF_SCRIPT, {"x": x, "y": y})
        except Exception as e:
            logger.error(f"选择器嗅探失败 ({x}, {y}): {e}")
            return None

    async def get_dom_hints_from_points(self, page: Page, points: List[Dict[str, float]]) -> List[Dict[str, Any]]:
        """
        【Visual UI Hybrid Perception】
        根据传入的坐标列表，批量获取元素的极简语义特征 (tag, placeholder, aria-label, innerText)。
        Args:
            points: [{"x": 100.0, "y": 200.0}, ...]
        Returns:
            [{"tag": "input", "placeholder": "Search", ...}, None, ...]
        """
        script = """
        (points) => {
            return points.map(p => {
                try {
                    const el = document.elementFromPoint(p.x, p.y);
                    if (!el) return null;
                    
                    // 向上回溯寻找有意义的交互标签 (最多3层)
                    let target = el;
                    let depth = 0;
                    while (target && depth < 3) {
                        const tag = target.tagName.toLowerCase();
                        if (['button', 'a', 'input', 'select', 'textarea'].includes(tag) || target.getAttribute('role') === 'button') {
                            break;
                        }
                        target = target.parentElement;
                        depth++;
                    }
                    if (!target || target === document.body) {
                        target = el; // 回退
                    }
                    
                    const tag = target.tagName.toLowerCase();
                    const hint = { tag: tag };
                    
                    if (target.placeholder) hint.placeholder = target.placeholder;
                    if (target.getAttribute('aria-label')) hint['aria-label'] = target.getAttribute('aria-label');
                    if (target.getAttribute('name')) hint['name'] = target.getAttribute('name');
                    if (target.getAttribute('type')) hint['type'] = target.getAttribute('type');
                    
                    // 获取计算样式以提取颜色信息
                    const computedStyle = window.getComputedStyle(target);
                    if (computedStyle.color && computedStyle.color !== 'rgba(0, 0, 0, 0)') {
                        hint.color = computedStyle.color;
                    }
                    if (computedStyle.backgroundColor && computedStyle.backgroundColor !== 'rgba(0, 0, 0, 0)') {
                        hint.bgcolor = computedStyle.backgroundColor;
                    }
                    
                    // 如果是非常短的纯文本，作为辅助信息 (防超长文本)
                    const text = target.innerText || target.textContent;
                    if (text && text.trim().length > 0 && text.trim().length <= 50) {
                        hint.text = text.trim();
                    }
                    return hint;
                } catch(e) {
                    return null;
                }
            });
        }
        """
        try:
            return await page.evaluate(script, points)
        except Exception as e:
            logger.error(f"批量提取 DOM hints 失败: {e}")
            return [None] * len(points)
