import re
import json
from typing import Any, Dict, List, Union
from loguru import logger
from jsonpath_ng import parse

def render_string(template: str, context_pool: Dict[str, Any]) -> str:
    """
    Replaces {{VAR_NAME}} and ${VAR_NAME} in the template string with values from context_pool.
    """
    if not template or not isinstance(template, str):
        return template
        
    def replace_match(match):
        var_name = match.group(1).strip()
        # Find exactly in context_pool, fallback to original if not found (or we could raise Error)
        return str(context_pool.get(var_name, match.group(0)))
        
    # Matches {{var}}
    pattern1 = re.compile(r"\{\{(.*?)\}\}")
    template = pattern1.sub(replace_match, template)
    
    # Matches ${var}
    pattern2 = re.compile(r"\$\{(.*?)\}")
    template = pattern2.sub(replace_match, template)
    
    return template
    

def render_context(data: Union[str, Dict, List, Any], context_pool: Dict[str, Any]) -> Union[str, Dict, List, Any]:
    """
    Recursively renders context variables inside dictionaries, lists, or strings.
    """
    if not context_pool:
        return data
        
    if isinstance(data, str):
        return render_string(data, context_pool)
    elif isinstance(data, dict):
        return {k: render_context(v, context_pool) for k, v in data.items()}
    elif isinstance(data, list):
        return [render_context(item, context_pool) for item in data]
    else:
        return data


def extract_values(response_json: Union[Dict, List, Any], extract_rules: Dict[str, str]) -> Dict[str, Any]:
    """
    Extracts values from a JSON response based on a dictionary of variable_names -> JSONPath rules.
    Returns the extracted key-value pairs.
    """
    extracted = {}
    if not extract_rules or not isinstance(response_json, (dict, list)):
        return extracted
        
    for var_name, json_path_expr in extract_rules.items():
        try:
            jsonpath_parsed = parse(json_path_expr)
            match = jsonpath_parsed.find(response_json)
            if match:
                # If multiple matches, we could return a list, but usually we just want the first.
                val = match[0].value
                extracted[var_name] = val
                logger.debug(f"Extracted {{{var_name}}} = {val} using path: {json_path_expr}")
            else:
                logger.warning(f"Could not find match for extraction rule '{json_path_expr}' in response")
        except Exception as e:
            logger.error(f"Failed to extract variable '{var_name}' with rule '{json_path_expr}': {e}")
            
    return extracted
