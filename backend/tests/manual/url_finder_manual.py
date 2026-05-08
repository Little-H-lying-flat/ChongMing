import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, r"d:\project\ChongMing\backend")

from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest

async def main():
    # A PRD that explicitly mentions a target URL
    req_text = """
    项目：校园健康管理系统首页测试
    目标系统URL: http://192.168.1.100:8080/home
    
    1. 用户访问首页，确保页面主标题可见。
    2. 点击登录按钮，使用admin/123456进行登录。
    3. 登录后断言个人中心图标可见。
    """
    
    print("Sending requirement for analysis (UI TARGET)...")
    try:
        service = DesignService()
        req = DesignRequest(
            project_id="test_project_1",
            requirement_text=req_text,
            target_type="UI"
        )
        result = await service.analyze_requirement(req)
        print("--- Result received ---")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Verify if url is in the steps
        scenarios = result.get("scenarios", [])
        url_found = False
        for s in scenarios:
            for step in s.get("steps", []):
                if step.get("url"):
                    print(f"✅ Found URL in step: {step['url']}")
                    url_found = True
                    break
        
        if not url_found:
            print("❌ No 'url' property found in the generated steps!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
