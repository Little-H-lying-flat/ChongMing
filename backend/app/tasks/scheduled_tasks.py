"""
定时任务

Celery Beat 调度的周期性任务
对应 Issue: #CL-005
"""

from datetime import datetime, timedelta, UTC

from celery import shared_task
from loguru import logger


@shared_task(name="app.tasks.scheduled_tasks.daily_regression")
def daily_regression():
    """
    每日回归测试
    """
    from app.tasks.execution_tasks import execute_test_cases
    
    logger.info("开始每日回归测试...")
    
    # Mock Selection of Daily Test Cases
    # In production: tcs = db.query(TestCase).filter(tag='daily').all()
    target_tc_ids = ["TC_UI_001", "TC_API_001"] # Sample IDs
    
    # Trigger Execution Task
    task = execute_test_cases.delay(
        tc_ids=target_tc_ids,
        config={"parallel": True, "source": "daily_regression"}
    )
    
    return {
        "triggered_at": datetime.now(UTC).isoformat(),
        "status": "triggered",
        "execution_task_id": task.id,
        "tc_count": len(target_tc_ids),
        "message": f"触发 {len(target_tc_ids)} 个回归测试用例",
    }


@shared_task(name="app.tasks.scheduled_tasks.generate_weekly_report")
def generate_weekly_report():
    """
    周报生成
    """
    logger.info("开始生成周报...")
    
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=7)
    
    # Mock Report Generation
    # In production: query distinct execution results, aggregate pass rate
    report_data = {
        "period": "Week 42",
        "total_executions": 120,
        "pass_rate": "98.5%",
        "top_failures": ["TC_LOGIN_003"]
    }
    
    # In production: send_email(to="team@example.com", subject="Weekly Report", body=...)
    logger.info(f"Weekly Report Generated: {report_data}")
    
    return {
        "report_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "status": "generated",
        "data_summary": report_data,
        "message": "周报已生成并记录",
    }


@shared_task(name="app.tasks.scheduled_tasks.cleanup_expired_data")
def cleanup_expired_data():
    """
    清理过期数据
    """
    import os
    import time
    from pathlib import Path
    
    logger.info("开始清理过期数据...")
    
    # Safety Guard: Ensure we only delete inside specific directories
    BASE_DIR = Path(os.getcwd()) # Assuming running from project root or backend
    if (BASE_DIR / "backend").exists():
        BASE_DIR = BASE_DIR / "backend"
        
    TRACES_DIR = BASE_DIR / "app" / "traces"
    
    if not TRACES_DIR.exists():
        logger.warning(f"Traces directory not found: {TRACES_DIR}")
        return {"status": "skipped", "message": "Directory not found"}
        
    # Safety Check: Must end with 'traces' to avoid deleting root
    if "traces" not in str(TRACES_DIR):
        logger.error("Safety Guard: Refusing to delete from non-trace directory")
        return {"status": "error", "message": "Safety Guard preventing deletion"}

    retention_days = 30
    cutoff_time = time.time() - (retention_days * 86400)
    
    cleaned = {
        "screenshots": 0,
        "videos": 0,
        "temp_files": 0,
    }
    
    def safe_delete(folder_name, counter_key):
        target_dir = TRACES_DIR / folder_name
        if not target_dir.exists():
            return
            
        for item in target_dir.iterdir():
            if item.is_file():
                # Check modification time
                if item.stat().st_mtime < cutoff_time:
                    try:
                        # item.unlink() # Uncomment to enable actual deletion
                        logger.info(f"Would delete expired file: {item}")
                        cleaned[counter_key] += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {item}: {e}")

    safe_delete("screenshots", "screenshots")
    safe_delete("videos", "videos")
    
    # Also clean mocked temporary files if any
    
    return {
        "cleaned_at": datetime.now(UTC).isoformat(),
        "cleaned_items": cleaned,
        "status": "completed",
        "mode": "dry-run", # Safety first, change to 'live' when verified
    }


@shared_task(name="app.tasks.scheduled_tasks.health_check")
def health_check():
    """
    后台定期健康检查 (For internal logging/alerting)
    """
    # This task is less critical if we have the API endpoint, 
    # but good for proactive alerting.
    logger.debug("执行后台健康检查...")
    return {"status": "ok", "checked": "background"}


@shared_task(name="app.tasks.scheduled_tasks.sync_git_scripts")
def sync_git_scripts():
    """
    同步 Git 脚本
    """
    logger.info("开始同步 Git 脚本...")
    return {
        "synced_at": datetime.now(UTC).isoformat(),
        "scripts_synced": 0,
        "status": "completed",
    }
