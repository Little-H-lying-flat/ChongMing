"""
Celery 任务基类

提供通用的重试策略、进度追踪、错误处理
对应 Issue: #CL-003, #CL-004
"""

from abc import ABC
from typing import Any, Dict, Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from loguru import logger


class BaseTask(Task, ABC):
    """
    任务基类
    
    提供:
    - 自动重试 (指数退避)
    - 进度更新
    - 结构化日志
    - 错误处理
    """
    
    # === 默认配置 ===
    autoretry_for = (Exception,)  # 自动重试的异常类型
    retry_backoff = True           # 启用指数退避
    retry_backoff_max = 600        # 最大退避时间 (秒)
    retry_jitter = True            # 添加随机抖动
    max_retries = 3                # 最大重试次数
    
    # 不重试的异常
    dont_autoretry_for = (
        ValueError,
        KeyError,
        TypeError,
    )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """重试时调用"""
        logger.warning(
            f"任务 {self.name}[{task_id}] 重试中 "
            f"(retry {self.request.retries}/{self.max_retries}): {exc}"
        )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """失败时调用"""
        logger.error(
            f"任务 {self.name}[{task_id}] 失败: {exc}",
            exc_info=einfo,
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """成功时调用"""
        logger.info(f"任务 {self.name}[{task_id}] 完成")
    
    def update_progress(
        self,
        current: int,
        total: int,
        message: str = "",
        extra: Dict[str, Any] = None,
    ):
        """
        更新任务进度
        
        Args:
            current: 当前进度
            total: 总数
            message: 进度消息
            extra: 额外数据
        """
        progress = (current / total * 100) if total > 0 else 0
        
        meta = {
            "current": current,
            "total": total,
            "progress": progress,
            "message": message,
            **(extra or {}),
        }
        
        self.update_state(state="PROGRESS", meta=meta)
        
        logger.debug(
            f"任务进度: {self.request.id} - {progress:.1f}% ({current}/{total}) - {message}"
        )


class UITestTask(BaseTask):
    """
    UI 测试任务基类
    
    针对 UI 自动化测试的特殊配置
    """
    
    # UI 测试可能需要更长时间
    soft_time_limit = 1800  # 30 分钟软超时
    time_limit = 2000       # ~33 分钟硬超时
    
    # 浏览器相关异常需要重试
    autoretry_for = (
        Exception,
        TimeoutError,
        ConnectionError,
    )
    
    # 业务逻辑错误不重试
    dont_autoretry_for = (
        ValueError,
        AssertionError,  # 断言失败不重试
    )


class APITestTask(BaseTask):
    """
    API 测试任务基类
    
    针对 API 测试的特殊配置
    """
    
    # API 测试通常较快
    soft_time_limit = 300  # 5 分钟软超时
    time_limit = 360       # 6 分钟硬超时
    
    # 网络异常需要重试
    autoretry_for = (
        Exception,
        TimeoutError,
        ConnectionError,
    )


class DesignGenTask(BaseTask):
    """
    设计生成任务基类
    
    针对 LLM 调用的特殊配置
    """
    
    # LLM 调用可能较慢
    soft_time_limit = 600  # 10 分钟软超时
    time_limit = 720       # 12 分钟硬超时
    
    # LLM API 异常需要重试
    autoretry_for = (
        Exception,
        TimeoutError,
    )
    
    # 限制重试次数 (LLM 调用成本较高)
    max_retries = 2


class CompileTask(BaseTask):
    """
    编译任务基类
    
    针对代码生成的特殊配置
    """
    
    # 编译通常较快
    soft_time_limit = 180  # 3 分钟软超时
    time_limit = 240       # 4 分钟硬超时
    
    max_retries = 2


class TurboTask(BaseTask):
    """
    涡轮任务基类
    
    针对并行执行的特殊配置
    """
    
    # 并行任务需要更长时间
    soft_time_limit = 3600  # 1 小时软超时
    time_limit = 3900       # 65 分钟硬超时
    
    # 并行任务失败不自动重试 (由调度器处理)
    max_retries = 0
