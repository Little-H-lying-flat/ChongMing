"""
任务进度追踪端点

SSE 实时推送任务执行进度
对应 Issue: #CL-004
"""

import asyncio
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from app.core.config import settings

router = APIRouter()


async def progress_event_generator(
    task_id: str,
    poll_interval: float = 1.0,
) -> AsyncGenerator[dict, None]:
    """
    任务进度事件生成器
    
    轮询 Celery 任务状态并生成 SSE 事件
    """
    from celery.result import AsyncResult
    from app.worker import celery
    
    result = AsyncResult(task_id, app=celery)
    last_state = None
    heartbeat_count = 0
    
    import time
    start_time = time.time()
    MAX_DURATION = 60 * 5 # 5 Minutes max connection
    
    while True:
        if time.time() - start_time > MAX_DURATION:
            yield {
                "event": "timeout",
                "data": {"message": "Connection timeout, please reconnect"}
            }
            return

        try:
            state = result.state
            info = result.info
            
            # 状态变化时发送事件
            if state != last_state:
                last_state = state
                
                if state == "PENDING":
                    yield {
                        "event": "pending",
                        "data": {"task_id": task_id, "status": "pending"},
                    }
                    
                elif state == "STARTED":
                    yield {
                        "event": "started",
                        "data": {"task_id": task_id, "status": "started"},
                    }
                    
                elif state == "PROGRESS":
                    yield {
                        "event": "progress",
                        "data": {
                            "task_id": task_id,
                            "status": "progress",
                            "current": info.get("current", 0),
                            "total": info.get("total", 0),
                            "progress": info.get("progress", 0),
                            "message": info.get("message", ""),
                        },
                    }
                    
                elif state == "SUCCESS":
                    yield {
                        "event": "complete",
                        "data": {
                            "task_id": task_id,
                            "status": "success",
                            "result": info,
                        },
                    }
                    return  # 任务完成，结束 SSE
                    
                elif state == "FAILURE":
                    yield {
                        "event": "error",
                        "data": {
                            "task_id": task_id,
                            "status": "failed",
                            "error": str(info),
                        },
                    }
                    return  # 任务失败，结束 SSE
                    
                elif state == "REVOKED":
                    yield {
                        "event": "cancelled",
                        "data": {"task_id": task_id, "status": "cancelled"},
                    }
                    return
            
            # 进度更新 (即使状态相同)
            elif state == "PROGRESS":
                yield {
                    "event": "progress",
                    "data": {
                        "task_id": task_id,
                        "status": "progress",
                        "current": info.get("current", 0),
                        "total": info.get("total", 0),
                        "progress": info.get("progress", 0),
                        "message": info.get("message", ""),
                    },
                }
            
            # 心跳 (每 30 秒)
            heartbeat_count += 1
            if heartbeat_count >= 30:
                heartbeat_count = 0
                yield {"event": "heartbeat", "data": {"task_id": task_id}}
            
            await asyncio.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"进度追踪错误: {e}")
            yield {
                "event": "error",
                "data": {"task_id": task_id, "error": str(e)},
            }
            return


@router.get("/tasks/{task_id}/progress")
async def get_task_progress_sse(
    task_id: str,
    poll_interval: float = Query(1.0, ge=0.5, le=5.0, description="轮询间隔 (秒)"),
):
    """
    任务进度 SSE 端点
    
    实时推送任务执行进度
    
    事件类型:
    - pending: 任务排队中
    - started: 任务开始执行
    - progress: 进度更新
    - complete: 任务完成
    - error: 任务失败
    - cancelled: 任务取消
    - heartbeat: 心跳
    
    使用示例:
    ```javascript
    const eventSource = new EventSource('/api/v1/tasks/{task_id}/progress');
    
    eventSource.addEventListener('progress', (event) => {
        const data = JSON.parse(event.data);
        console.log(`进度: ${data.progress}%`);
    });
    
    eventSource.addEventListener('complete', (event) => {
        eventSource.close();
    });
    ```
    """
    return EventSourceResponse(
        progress_event_generator(task_id, poll_interval)
    )


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    获取任务状态 (非 SSE)
    
    一次性获取任务当前状态
    """
    from celery.result import AsyncResult
    from app.worker import celery
    
    result = AsyncResult(task_id, app=celery)
    
    return {
        "task_id": task_id,
        "state": result.state,
        "info": result.info if result.info else None,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
    }


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """
    取消任务
    """
    from celery.result import AsyncResult
    from app.worker import celery
    
    result = AsyncResult(task_id, app=celery)
    result.revoke(terminate=True)
    
    logger.info(f"任务 {task_id} 已取消")
    
    return {
        "task_id": task_id,
        "status": "cancelled",
        "message": "取消请求已发送",
    }
