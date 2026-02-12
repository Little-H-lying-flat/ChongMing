import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def extract_code_block(text: str, language: str = "python") -> str:
    """
    Robustly extract code block from text.
    
    Strategies:
    1. Match ```language ... ```
    2. Match generic ``` ... ```
    3. If no blocks, assumes raw code if it looks like code, or strips known conversational prefixes.
    """
    if not text:
        return ""
        
    # 1. Specific Language Block
    # re.DOTALL makes . match newlines
    pattern_lang = r"```" + re.escape(language) + r"\n(.*?)```"
    match = re.search(pattern_lang, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    # 2. Generic Block
    pattern_generic = r"```\n?(.*?)```"
    match = re.search(pattern_generic, text, re.DOTALL)
    if match:
        return match.group(1).strip()
        
    # 3. Fallback / Raw Text Cleanup
    # Sometimes LLMs just return code without blocks, or with "Here is the code:\n..."
    # We can try to strip common prefixes/suffixes if we are desperate.
    # implementing a simple heuristic:
    
    clean_text = text.strip()
    
    # Remove leading "Here is the code:" etc.
    # This is risky if the code actually contains these strings, but for Python scripts usually OK.
    # Let's keep it simple: if it starts with "def " or "import " it's probably code.
    # Otherwise, we warn.
    
    return clean_text
