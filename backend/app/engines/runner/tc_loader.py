from typing import List, Optional
from app.schemas.execution import TCIR, ExecutionMode
from app.core.config import settings

class TestCaseLoader:
    """
    Mock Loader for Test Cases
    (Replaces DB until implemented)
    """
    
    @staticmethod
    def load(tc_id: str) -> Optional[TCIR]:
        # Mock Data Logic
        if tc_id.startswith("TC_UI_"):
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
                    # Just a simple check, we won't actually click search to keep it fast/safe?
                    # Or we can just wait.
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
