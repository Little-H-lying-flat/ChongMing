import json
import re
import logging
from typing import Any, Dict, Union, List

logger = logging.getLogger(__name__)

def repair_json(text: str) -> Union[Dict[str, Any], List[Any]]:
    """
    尝试修复并解析不规范的 JSON 字符串
    
    Strategies:
    1. Strip Markdown code blocks
    2. Remove comments (//...)
    3. Fix trailing commas
    4. Balance braces (simple)
    """
    if not text:
        raise ValueError("Empty JSON text")
        
    # 1. Strip Markdown
    clean_text = text.strip()
    if clean_text.startswith("```"):
        # Match ```json ... ``` or just ``` ... ```
        match = re.search(r"```(?:\w+)?\n(.*?)```", clean_text, re.DOTALL)
        if match:
            clean_text = match.group(1).strip()
        else:
            # Fallback for unclosed code blocks or simple start
            clean_text = clean_text.lstrip("`").strip()
            if clean_text.startswith("json\n"):
                clean_text = clean_text[5:]
    
    # 2. Try Standard Load
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass
        
    # 3. Aggressive Repair
    logger.debug("Standard JSON load failed, attempting aggressive repair...")
    
    # Remove single line comments // ...
    clean_text = re.sub(r"//.*", "", clean_text)
    
    # Find the outermost JSON object or array
    # This helps if there is extra text around the JSON
    match_obj = re.search(r"(\{.*\})", clean_text, re.DOTALL)
    match_arr = re.search(r"(\[.*\])", clean_text, re.DOTALL)
    
    candidate = clean_text
    if match_obj and match_arr:
        # Pick the one that starts earlier or looks larger?
        # Usually we expect one main object
        if len(match_obj.group(1)) > len(match_arr.group(1)):
            candidate = match_obj.group(1)
        else:
            candidate = match_arr.group(1)
    elif match_obj:
        candidate = match_obj.group(1)
    elif match_arr:
        candidate = match_arr.group(1)
        
    # Fix trailing commas: , } -> } and , ] -> ]
    candidate = re.sub(r",\s*\}", "}", candidate)
    candidate = re.sub(r",\s*\]", "]", candidate)
    
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        logger.error(f"JSON Repair failed: {e}")
        raise ValueError(f"Failed to parse JSON even after repair: {e}") from e
