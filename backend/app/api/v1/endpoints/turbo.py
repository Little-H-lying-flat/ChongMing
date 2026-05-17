from typing import Dict, Optional
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.turbo import TurboRunConfig, TurboTestStats
from app.engines.turbo.engine import TurboEngine
from app.services.test_case_service import TestCaseService
from app.schemas.api_ir import APIIR
import uuid

router = APIRouter(tags=["Flow 5: Turbo Engine (性能压测)"])

turbo_engine: TurboEngine | None = None


def get_turbo_engine() -> TurboEngine:
    global turbo_engine
    if turbo_engine is None:
        turbo_engine = TurboEngine()
    return turbo_engine

@router.post(
    "/run", 
    response_model=Dict[str, str],
    summary="启动压测 (Start Load Test)",
    description="""
    **Flow 5 核心接口**: 启动高性能压测任务 (基于 Locust)。
    
    - **流程**:
        1. **数据合成**: 根据 API-IR 和 `data_count` 自动生成测试数据 (CSV)。
        2. **编译压测脚本**: 动态生成 `locustfile.py`。
        3. **启动引擎**: 启动 Locust Master/Worker 进程。
    - **返回**: `test_id` 用于控制和监控。
    """
)
async def start_turbo_test(config: TurboRunConfig, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Start a Turbo Load Test
    """
    if not config.test_id:
        config.test_id = f"test_{uuid.uuid4().hex[:8]}"
        
    # Handle API TestCase integration
    if config.test_case_id:
        tc_service = TestCaseService(db)
        tc_model = await tc_service.get(config.test_case_id)
        if not tc_model:
            raise HTTPException(status_code=404, detail=f"Test case {config.test_case_id} not found")
        
        # Parse test case steps into APIIR chain
        config.api_ir_chain = []
        for step in tc_model.steps:
            req = step.get("request", step)
            api_ir = APIIR(
                method=req.get("method", "GET"),
                url=req.get("url", req.get("target", "/")),
                headers=req.get("headers", {}),
                body=req.get("body"),
            )
            config.api_ir_chain.append(api_ir)
            
        # Optional: set target_host to the first URL origin if not set
        if not config.target_host and config.api_ir_chain:
            first_url = config.api_ir_chain[0].url
            from urllib.parse import urlparse
            parsed = urlparse(first_url)
            if parsed.scheme and parsed.netloc:
                config.target_host = f"{parsed.scheme}://{parsed.netloc}"
        
    # Check if already running
    # The runner check is inside run_test, but we can check here too or catch exception
    try:
        # We run the test start logic. 
        # Note: run_test involves synthesis (potentially slow) and then starting the process.
        # If synthesis is slow, we should probably run it in background?
        # But for MVP let's await it to return immediate errors if data gen fails.
        # However, if data gen takes > 30s, HTTP request might timeout.
        # For Day 1, we assume data gen is fast (<10s) or users accept wait.
        # To be safe, we can use background task if we want async behavior.
        # But `run_test` returns `test_id`. We need that.
        
        # Let's await it.
        test_id = await get_turbo_engine().run_test(config)
        return {"test_id": test_id, "status": "started"}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/stop/{test_id}", 
    response_model=Dict[str, str],
    summary="停止压测 (Stop Test)",
    description="强制终止指定 ID 的压测任务及相关进程。",
)
def stop_turbo_test(test_id: str):
    """
    Stop a running Turbo Load Test
    """
    get_turbo_engine().stop_test(test_id)
    return {"test_id": test_id, "status": "stopped"}

@router.get(
    "/stats/{test_id}", 
    response_model=Optional[TurboTestStats],
    summary="获取压测统计 (Get Stats)",
    description="""
    **Flow 5 核心接口**: 获取实时压测指标。
    
    - **指标包含**: RPS, 失败率, P95 响应时间, 并发用户数等。
    - **来源**: Locust CSV 报告流或内存统计。
    """
)
def get_turbo_stats(test_id: str):
    """
    Get real-time stats for a test
    """
    stats = get_turbo_engine().get_stats(test_id)
    if not stats:
        # If stats are None, maybe it's not running or ID is wrong.
        # For now, return None or 404? 
        # Returning None with 200 OK means "no stats available right now" or "finished".
        return None
    return stats
