from typing import List, Optional
import json
from pathlib import Path
from app.schemas.execution import TCIR, ExecutionMode
from app.core.config import settings

class TestCaseLoader:
    """
    Test Case Loader
    Loads test cases from JSON files in backend/test_cases/ or mocks.
    """
    
    @staticmethod
    def load(tc_id: str) -> Optional[TCIR]:
        # 1. Try loading from file
        base_path = Path(__file__).parent.parent.parent.parent / "test_cases"
        file_path = base_path / f"{tc_id}.json"
        
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert 'mode' string to Enum if needed
                    if "mode" in data and isinstance(data["mode"], str):
                        data["mode"] = ExecutionMode(data["mode"])
                    return TCIR(**data)
            except Exception as e:
                print(f"Error loading test case {tc_id} from file: {e}")
                return None

        # 2. Hardcoded / Mock Data Logic (Fallback)
        if tc_id.startswith("TC_UI_GOOGLE"):
             return TCIR(
                id=tc_id,
                name="Google Search Test",
                mode=ExecutionMode.UI,
                steps=[
                    {
                        "type": "UI",
                        "action": "navigate", 
                        "params": {"url": "https://www.google.com"}
                    },
                    {
                        "type": "UI",
                        "action": "type",
                        "target": {"strategy": "dom", "value": "textarea[title='Search']"},
                        "params": {"text": "Playwright Python"}
                    },
                    {
                         "type": "UI",
                         "action": "wait",
                         "params": {"seconds": 2}
                    }
                ]
            )
            
        elif tc_id.startswith("TC_API_"):
            return TCIR(
                id=tc_id,
                name="Health Check Test",
                mode=ExecutionMode.API,
                steps=[
                    {
                        "type": "API",
                        "method": "GET",
                        "url": f"http://localhost:8000{settings.API_V1_STR}/health",
                        "assertions": [
                            {"type": "status_code", "expected": 200},
                            {"type": "contains", "expected": "ok"}
                        ]
                    }
                ]
            )
            
        elif tc_id == "TC_DEMO":
             # Mixed Mode? No, just UI for now
             return TCIR(
                id=tc_id,
                name="Demo Test",
                mode=ExecutionMode.UI,
                steps=[
                    {"type": "UI", "action": "navigate", "params": {"url": "http://example.com"}},
                ]
             )
             
        return None
