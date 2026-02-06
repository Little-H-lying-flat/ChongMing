"""
日志配置模块

使用 Loguru 提供结构化日志
"""

import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging():
    """配置日志系统"""
    # 移除默认处理器
    logger.remove()
    
    # 控制台输出
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
    )
    
    # 文件输出
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    
    # 应用日志
    logger.add(
        log_dir / "chongming_{time:YYYY-MM-DD}.log",
        level=settings.LOG_LEVEL,
        rotation="00:00",  # 每天轮转
        retention="30 days",  # 保留 30 天
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    )
    
    # 错误日志单独存放
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        compression="zip",
    )
    
    logger.info("日志系统初始化完成")
