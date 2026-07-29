"""
用户任务同步模块

负责将用户定义的任务同步到调度器，包括 cron、interval、once、random 类型。
"""

from datetime import datetime

from loguru import logger

from app.core.scheduler.manager import scheduler_manager
from app.core.scheduler.utils import get_job_next_run_time, get_next_random_time


def _get_task_max_instances(task) -> int:
    """
    根据任务配置获取最大并行实例数

    - 如果 allow_parallel=0，则返回 1（不允许并行）
    - 如果 allow_parallel=1，则返回 task.max_instances（默认为1）
    """
    if not getattr(task, "allow_parallel", 0):
        return 1
    return getattr(task, "max_instances", 1) or 1


def _acquire_task_lock(task_id: int, ttl_seconds: int = 3600) -> bool:
    """
    获取任务执行的分布式锁

    使用 Redis SETNX 实现，防止多节点重复调度同一任务

    Args:
        task_id: 任务ID
        ttl_seconds: 锁的过期时间（秒），默认1小时

    Returns:
        True if lock acquired, False if already locked
    """
    import redis

    from app.core.config import settings

    try:
        r = redis.from_url(settings.REDIS_URL)
        lock_key = f"crawlops:task:lock:{task_id}"
        # SETNX + EXPIRE 原子操作
        acquired = r.set(lock_key, "1", nx=True, ex=ttl_seconds)
        if acquired:
            logger.debug(f"获取任务 {task_id} 分布式锁成功")
        else:
            logger.debug(f"任务 {task_id} 已被其他节点锁定")
        return bool(acquired)
    except Exception as e:
        logger.warning(f"获取分布式锁失败: {e}，继续执行（退化为无锁模式）")
        return True  # 锁服务不可用时，退化为允许执行


def _release_task_lock(task_id: int) -> None:
    """释放任务执行的分布式锁"""
    import redis

    from app.core.config import settings

    try:
        r = redis.from_url(settings.REDIS_URL)
        lock_key = f"crawlops:task:lock:{task_id}"
        r.delete(lock_key)
        logger.debug(f"释放任务 {task_id} 分布式锁")
    except Exception as e:
        logger.warning(f"释放分布式锁失败: {e}")


def _check_parallel_allowed(db, task) -> bool:
    """
    检查是否允许执行任务（基于并行策略）

    根据 allow_parallel 和 max_instances 检查当前运行中的实例数

    Returns:
        True if execution allowed, False if should skip
    """
    from app.models import TaskExecution

    # 如果允许并行且 max_instances > 1，检查当前运行数
    max_instances = _get_task_max_instances(task)

    # 查询当前运行中的实例数
    running_count = (
        db.query(TaskExecution)
        .filter(TaskExecution.task_id == task.id, TaskExecution.status.in_(["pending", "running"]))
        .count()
    )

    if running_count >= max_instances:
        logger.warning(
            f"任务 {task.id} 已有 {running_count} 个运行中的实例，"
            f"超过最大并行数 {max_instances}，跳过本次调度"
        )
        return False

    return True


def run_user_task(task_id: int):
    """运行用户任务（带分布式锁和并行检查）"""
    from app.core.database import SessionLocal
    from app.services.task_service import task_service

    db = SessionLocal()
    lock_acquired = False
    try:
        task = task_service.get_by_id(db, task_id)
        if not task:
            logger.error(f"调度任务 {task_id} 不存在")
            return
        if task.status != 1:
            logger.warning(f"调度任务 {task_id} 已禁用，停止调度")
            scheduler_manager.remove_job(f"task_{task_id}")
            return

        # 尝试获取分布式锁（短期锁，仅用于防止调度时重复推送）
        # 锁 TTL 设置为60秒，因为只需要防止并发调度，不需要持续整个执行期间
        if not _acquire_task_lock(task_id, ttl_seconds=60):
            logger.warning(f"任务 {task_id} 正在被其他节点调度，跳过本次")
            return
        lock_acquired = True

        # 检查并行策略（基于数据库中的运行实例数）
        if not _check_parallel_allowed(db, task):
            return

        logger.info(f"自动调度执行任务: {task.name} (ID: {task_id})")
        task_service.run(db, task, trigger_type="schedule")
    except Exception as e:
        logger.error(f"调度执行任务 {task_id} 异常: {e}")
    finally:
        # 任务推送到队列后，立即释放锁
        if lock_acquired:
            _release_task_lock(task_id)
        db.close()


def run_random_task(task_id: int):
    """运行随机调度任务并重新调度下一次（带分布式锁和并行检查）"""
    from app.core.database import SessionLocal
    from app.services.task_service import task_service

    db = SessionLocal()
    lock_acquired = False
    try:
        task = task_service.get_by_id(db, task_id)
        if not task:
            logger.error(f"随机调度任务 {task_id} 不存在")
            return
        if task.status != 1:
            logger.warning(f"随机调度任务 {task_id} 已禁用")
            return

        # 尝试获取分布式锁（短期锁）
        if not _acquire_task_lock(task_id, ttl_seconds=60):
            logger.warning(f"随机任务 {task_id} 正在被其他节点调度，跳过")
            return
        lock_acquired = True

        # 检查并行策略
        if not _check_parallel_allowed(db, task):
            return

        # 执行任务
        logger.info(f"执行随机调度任务: {task.name} (ID: {task_id})")
        task_service.run(db, task, trigger_type="schedule")

        # 重新调度下一次
        sync_task_to_scheduler(task)
    except Exception as e:
        logger.error(f"随机调度任务 {task_id} 执行异常: {e}")
    finally:
        # 立即释放锁
        if lock_acquired:
            _release_task_lock(task_id)
        db.close()


def sync_task_to_scheduler(task):
    """同步单个任务到调度器"""
    from sqlalchemy.orm import object_session

    job_id = f"task_{task.id}"
    if task.status != 1:
        scheduler_manager.remove_job(job_id)
        return

    next_run_time = None
    max_instances = _get_task_max_instances(task)

    if task.schedule_type == "cron" and task.cron_expression:
        scheduler_manager.add_job(
            run_user_task,
            job_id=job_id,
            trigger="cron",
            expression=task.cron_expression,
            max_instances=max_instances,
            args=[task.id],
        )
        # 获取下一次运行时间
        job = scheduler_manager.scheduler.get_job(job_id)
        if job:
            next_run_time = get_job_next_run_time(job)

    elif task.schedule_type == "interval" and task.interval_seconds:
        # 如果数据库中有 scheduled_time 且在未来，使用它来恢复调度
        # 这样重启后不会重置计时
        db_next_run = None
        if task.scheduled_time and task.scheduled_time > datetime.now():
            db_next_run = task.scheduled_time

        scheduler_manager.add_job(
            run_user_task,
            job_id=job_id,
            trigger="interval",
            minutes=task.interval_seconds // 60 if task.interval_seconds >= 60 else 1,
            max_instances=max_instances,
            next_run_time=db_next_run,  # 传入数据库保存的时间
            args=[task.id],
        )
        # 获取下一次运行时间（可能是传入的或新计算的）
        job = scheduler_manager.scheduler.get_job(job_id)
        if job:
            next_run_time = get_job_next_run_time(job)

    elif task.schedule_type == "once" and task.scheduled_time:
        if task.scheduled_time > datetime.now():
            scheduler_manager.add_job(
                run_user_task,
                job_id=job_id,
                trigger="once",
                run_date=task.scheduled_time,
                max_instances=max_instances,
                args=[task.id],
            )
            next_run_time = task.scheduled_time

    elif (
        task.schedule_type == "random"
        and task.random_start_hour is not None
        and task.random_end_hour is not None
    ):
        # 随机调度：计算下一个随机执行时间
        try:
            next_run = get_next_random_time(task.random_start_hour, task.random_end_hour)
            scheduler_manager.add_job(
                run_random_task,
                job_id=job_id,
                trigger="once",
                run_date=next_run,
                max_instances=max_instances,
                args=[task.id],
            )
            logger.info(f"随机调度任务 {task.id} 下次执行时间: {next_run}")
            next_run_time = next_run
        except ValueError as e:
            logger.error(f"随机调度任务 {task.id} 配置错误: {e}")
            return

    # 更新任务的下次运行时间到数据库
    if next_run_time:
        db = object_session(task)
        if db:
            if task.scheduled_time != next_run_time:
                task.scheduled_time = next_run_time
                db.add(task)
                db.commit()


def sync_all_tasks():
    """同步所有已启用的任务到调度器"""
    from app.core.database import SessionLocal
    from app.models import Task

    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.status == 1).all()
        logger.info(f"正在同步 {len(tasks)} 个任务到调度器...")
        for task in tasks:
            sync_task_to_scheduler(task)
    finally:
        db.close()
