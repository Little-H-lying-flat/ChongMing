"""
Celery 应用配置

启动 Worker:
    celery -A app.worker:celery worker -l INFO -Q high,normal,low,execution,design,phoenix
    
启动 Beat (定时任务):
    celery -A app.worker:celery beat -l INFO
    
启动 Flower 监控:
    celery -A app.worker:celery flower --port=5555 --basic_auth=admin:admin
    
对应 Issue: #CL-001, #CL-002, #CL-005, #CL-006
"""

from datetime import timedelta
import asyncio

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_ready
from kombu import Queue, Exchange
from loguru import logger

from app.core.config import settings


# ═══════════════════════════════════════════════════════════════════════════════
# Celery 应用实例 (#CL-001)
# ═══════════════════════════════════════════════════════════════════════════════

celery = Celery(
    "chongming",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.execution_tasks",
        "app.tasks.design_tasks",
        "app.tasks.phoenix_tasks",
        "app.tasks.scheduled_tasks",
    ],
)

_ai_manager_initialized = False


def _initialize_ai_manager_for_worker() -> None:
    global _ai_manager_initialized
    if _ai_manager_initialized:
        return

    from app.core.ai_client import init_ai_manager
    from app.services.smart_ops.ai_config_provider_impl import AIConfigProviderImpl
    from app.services.smart_ops.ai_config_service import AIConfigService

    try:
        asyncio.run(AIConfigService.ensure_schema_ready())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(AIConfigService.ensure_schema_ready())
        finally:
            loop.close()

    init_ai_manager(AIConfigProviderImpl())
    _ai_manager_initialized = True
    logger.info("AI Client Manager initialized for Celery worker")


@worker_process_init.connect
@worker_ready.connect
def initialize_worker_ai_manager(**_: object) -> None:
    _initialize_ai_manager_for_worker()


# ═══════════════════════════════════════════════════════════════════════════════
# 队列定义 (#CL-002)
# ═══════════════════════════════════════════════════════════════════════════════

# 交换器
default_exchange = Exchange("chongming", type="direct")

# 队列配置
CELERY_QUEUES = (
    # 优先级队列
    Queue("high", default_exchange, routing_key="high", queue_arguments={"x-max-priority": 10}),
    Queue("normal", default_exchange, routing_key="normal", queue_arguments={"x-max-priority": 5}),
    Queue("low", default_exchange, routing_key="low", queue_arguments={"x-max-priority": 1}),
    
    # 功能队列
    Queue("execution", default_exchange, routing_key="execution"),   # UI/API 测试执行
    Queue("design", default_exchange, routing_key="design"),         # 神经设计层
    Queue("phoenix", default_exchange, routing_key="phoenix"),       # 凤凰涅槃编译
    Queue("turbo", default_exchange, routing_key="turbo"),           # 涡轮引擎 (并行)
)


# ═══════════════════════════════════════════════════════════════════════════════
# Celery 配置
# ═══════════════════════════════════════════════════════════════════════════════

celery.conf.update(
    # === 序列化配置 (#CL-001) ===
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    event_serializer="json",
    
    # === Local Testing ===
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    
    # === 时区 ===
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # === 任务追踪 ===
    task_track_started=True,
    task_send_sent_event=True,
    
    # === 超时与限制 ===
    task_time_limit=3600,          # 1 小时硬超时
    task_soft_time_limit=3300,     # 55 分钟软超时
    task_acks_late=True,           # 任务完成后确认 (防止丢失)
    task_reject_on_worker_lost=True,
    
    # === 结果存储 ===
    result_expires=86400,          # 1 天过期
    result_extended=True,          # 扩展结果 (包含任务名称等)
    
    # === 重试策略 ===
    task_default_retry_delay=60,   # 默认重试延迟 60 秒
    task_max_retries=3,            # 默认最大重试 3 次
    
    # === 并发配置 ===
    worker_concurrency=4,          # 并发 Worker 数
    worker_prefetch_multiplier=1,  # 预取倍数 (1=公平调度)
    worker_max_tasks_per_child=100, # 子进程最大任务数后重启
    
    # === 队列配置 (#CL-002) ===
    task_queues=CELERY_QUEUES,
    task_default_queue="normal",
    task_default_routing_key="normal",
    
    # === 任务路由 ===
    task_routes={
        # 执行任务 -> execution 队列
        "app.tasks.execution_tasks.*": {"queue": "execution", "routing_key": "execution"},
        
        # 设计任务 -> design 队列
        "app.tasks.design_tasks.*": {"queue": "design", "routing_key": "design"},
        
        # 编译任务 -> phoenix 队列
        "app.tasks.phoenix_tasks.*": {"queue": "phoenix", "routing_key": "phoenix"},
        
        # 定时任务 -> normal 队列
        "app.tasks.scheduled_tasks.*": {"queue": "normal", "routing_key": "normal"},
    },
    
    # === Beat 定时任务 (#CL-005) ===
    beat_schedule={
        # 每日回归测试 (每天凌晨 2 点)
        "daily-regression": {
            "task": "app.tasks.scheduled_tasks.daily_regression",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "execution"},
        },
        
        # 周报生成 (每周一上午 9 点)
        "weekly-report": {
            "task": "app.tasks.scheduled_tasks.generate_weekly_report",
            "schedule": crontab(hour=9, minute=0, day_of_week=1),
            "options": {"queue": "low"},
        },
        
        # 清理过期数据 (每天凌晨 4 点)
        "cleanup-expired": {
            "task": "app.tasks.scheduled_tasks.cleanup_expired_data",
            "schedule": crontab(hour=4, minute=0),
            "options": {"queue": "low"},
        },
        
        # 健康检查 (每 5 分钟)
        "health-check": {
            "task": "app.tasks.scheduled_tasks.health_check",
            "schedule": timedelta(minutes=5),
            "options": {"queue": "high"},
        },
    },
    
    # === 任务结果压缩 ===
    result_compression="gzip",
    
    # === Flower 监控 (#CL-006) ===
    # Flower 通过命令行参数配置: --basic_auth, --port
)


# ═══════════════════════════════════════════════════════════════════════════════
# 任务重试策略
# ═══════════════════════════════════════════════════════════════════════════════

# 指数退避重试配置
RETRY_BACKOFF = True
RETRY_BACKOFF_MAX = 600  # 最大 10 分钟
RETRY_JITTER = True       # 添加随机抖动


def main():
    """命令行入口"""
    celery.start()


if __name__ == "__main__":
    main()

