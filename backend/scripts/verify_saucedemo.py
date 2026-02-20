import asyncio
import sys
import os
import logging
from loguru import logger as loguru_logger

# Setup logging
logging.basicConfig(level=logging.INFO)
loguru_logger.add(sys.stderr, level="INFO")

# Fix path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest
from app.engines.dispatcher import Dispatcher
from app.engines.right_pupil import RightPupilEngine
from app.engines.left_pupil import LeftPupilEngine
from app.schemas.execution import TCIR, ExecutionMode
from app.core.config import settings

USER_REQUIREMENT = """
目标网址：https://www.saucedemo.com/
测试账号：standard_user / secret_sauce
场景验收步骤
1. 用户登录
操作： 使用测试账号的凭证登录系统。
视觉预期： 成功进入商品大厅页面，左上角显示系统 Logo（Swag Labs），右上角显示购物车图标。
2. 添加商品
操作： 在商品列表中浏览，将一件名为 “Sauce Labs Backpack” 的背包加入购物车。
视觉预期： 商品卡片上的加购按钮状态发生改变（变为移除状态），且右上角购物车图标出现带有数字“1”的视觉提示。
3. 查看购物车
操作： 打开购物车页面，检查已选商品。
视觉预期： 购物车列表中存在刚才添加的 “Sauce Labs Backpack”。
4. 填写结账信息
操作： 进入结算流程，在个人信息表单中填写必要的配送信息（如姓名、邮编），并进入下一步。
视觉预期： 页面进入订单概览（Overview）状态，显示商品列表和最终的计费总额。
5. 确认并完成订单
操作： 确认订单金额无误后，提交并完成订单。
视觉预期： 页面展示结账完成状态，正中央出现醒目的感谢提示语 “Thank you for your order!”。
"""

async def main():
    loguru_logger.info("🚀 Starting SauceDemo E2E Verification")
    
    # 1. Initialize Services
    service = DesignService()
    loguru_logger.info("✅ DesignService Initialized")
    
    # 2. Design Analysis (Schema & Prompt Verification)
    req = DesignRequest(
        project_id="saucedemo_e2e",
        requirement_text=USER_REQUIREMENT,
        target_type="UI"
    )
    
    loguru_logger.info("🧠 Analyizng Requirement (Generating Scenarios)...")
    scenarios = await service.analyze_requirement(req)
    
    if not scenarios:
        loguru_logger.error("❌ No scenarios generated!")
        return

    scenario = scenarios[0]
    loguru_logger.info(f"📋 Scenario Generated: {scenario.get('name')}")
    
    # 3. Test Case Generation
    loguru_logger.info("✍️  Generating Test Case (Refining)...")
    refined_case = await service.generate_test_case(scenario, "saucedemo_e2e")
    
    # --- VERIFY GOTO RULE ---
    first_step = refined_case.steps[0]
    loguru_logger.info(f"🧐 First Step Verification: Type={first_step.step_type}, Action={getattr(first_step, 'action', 'N/A')}")
    
    if first_step.step_type == "UI" and getattr(first_step, "action") == "goto":
        loguru_logger.success(f"✅ GOTO Rule Verified! Target URL: {first_step.value}")
    else:
        loguru_logger.error(f"❌ GOTO Rule Failed! First step is {first_step}")
    
    # 4. Execution (OmniParser Verification)
    loguru_logger.info("🏃 Starting Execution Engine...")
    
    # Construct TCIR
    tcir = TCIR(
        id=refined_case.id,
        name=refined_case.name,
        mode=ExecutionMode.UI,
        steps=[s.model_dump() for s in refined_case.steps], # Convert Pydantic to Dict
        priority="P1"
    )
    
    # Initialize Engine
    right_pupil = RightPupilEngine()
    left_pupil = LeftPupilEngine()
    dispatcher = Dispatcher()
    dispatcher.attach_engines(right_pupil, left_pupil)
    
    try:
        loguru_logger.info("🖥️  Booting UI Engine (Headless)...")
        await right_pupil.start_session(headless=True)
        
        loguru_logger.info("▶️  Executing Test Case...")
        result = await dispatcher.execute(tcir)
        
        # 5. Report Results
        loguru_logger.info("="*50)
        loguru_logger.info(f"🏁 Execution Finished. Status: {result.status}")
        loguru_logger.info(f"⏱️  Duration: {result.total_duration_ms}ms")
        
        for i, step_res in enumerate(result.step_results):
            status_icon = "✅" if step_res.success else "❌"
            loguru_logger.info(f"Step {i+1}: {status_icon} {step_res.description or 'No Desc'}")
            if not step_res.success:
                 loguru_logger.error(f"   Error: {step_res.error}")
        
        loguru_logger.info("="*50)

    except Exception as e:
        loguru_logger.exception(f"❌ Execution Crash: {e}")
    finally:
        await right_pupil.stop_session()

if __name__ == "__main__":
    asyncio.run(main())
