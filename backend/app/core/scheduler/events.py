"""
调度器事件处理

处理 APScheduler 的任务执行事件，同步下次运行时间到数据库。
"""

from datetime import datetime

from loguru import logger

from app.core.scheduler.utils import get_job_next_run_time


def _update_task_next_run_time(job_id: str):
    """
    更新任务的下次运行时间到数据库
    供 on_job_executed 和 on_job_missed 共同调用
    """
    from app.core.scheduler.manager import scheduler_manager

    if not job_id.startswith("task_"):
        return

    try:
        task_id = int(job_id.split("_")[1])
        job = scheduler_manager.scheduler.get_job(job_id)
        if not job:
            return

        # 使用通用函数获取下次运行时间
        next_run_time = get_job_next_run_time(job)

        if next_run_time:
            from app.core.database import SessionLocal
            from app.models import Task

            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task and task.scheduled_time != next_run_time:
                    task.scheduled_time = next_run_time
                    db.add(task)
                    db.commit()
                    logger.info(f"Updated task {task_id} scheduled_time to {next_run_time}")
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Failed to sync scheduled_time for job {job_id}: {e}")


def on_job_executed(event):
    """
    任务执行完成事件处理
    同步下次运行时间到数据库
    """
    _update_task_next_run_time(event.job_id)


def on_job_missed(event):
    """
    任务错过执行事件处理
    当任务因系统休眠等原因被 miss 时，也更新下次运行时间到数据库
    这样任务列表显示的下次执行时间会保持准确
    """
    job_id = event.job_id
    if job_id.startswith("task_"):
        logger.warning(f"任务 {job_id} 错过了执行时间，更新下次执行时间")
    _update_task_next_run_time(job_id)
