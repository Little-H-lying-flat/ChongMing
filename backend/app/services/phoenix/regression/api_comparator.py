
from typing import Dict, Any, List, Optional
from deepdiff import DeepDiff
from loguru import logger

class APIComparator:
    """
    API 比较器 (API Regression)
    
    1. Schema Diff: 比较 JSON 结构。
    2. Content Diff: 比较关键字段值。
    3. Ignore Dynamic: 自动忽略 time, date, id 等动态字段。
    """
    
    DEFAULT_IGNORE_PATHS = [
        "root['id']",
        "root['created_at']",
        "root['updated_at']",
        "root['timestamp']",
        "root['trace_id']"
    ]
    
    def compare(self, 
                baseline: Dict[str, Any], 
                current: Dict[str, Any], 
                ignore_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Compare two JSON objects.
        
        Returns:
            Dict: DeepDiff result. Empty dict means match.
        """
        excludes = set(self.DEFAULT_IGNORE_PATHS)
        if ignore_paths:
            excludes.update(ignore_paths)
            
        # exclude_regex_paths for dynamic IDs in lists?
        # e.g. root['items'][\d+]['id']
        exclude_regex = [r"root\['.*'\]\['id'\]", r"root\['.*'\]\['created_at'\]"]

        diff = DeepDiff(
            baseline, 
            current, 
            ignore_order=True,
            exclude_paths=list(excludes),
            exclude_regex_paths=exclude_regex
        )
        
        if diff:
            logger.warning(f"API Regression Failed: {diff}")
        else:
            logger.info("API Regression Passed")
            
        return diff
