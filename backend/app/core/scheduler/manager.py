"""
调度器管理器

负责 APScheduler 的初始化、任务添加、启动和关闭。
"""
from datetime import datetime
from typing import Callable
from loguru import logger

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger


class SchedulerManager:
    """调度器管理器"""

    def __init__(self):
        # 配置 APScheduler 默认行为
        # - misfire_grace_time: 任务错过执行后的容错时间（秒），在此时间内仍会执行
        # - coalesce: 当多次执行被错过时，合并为一次执行
        # - max_instances: 同一任务同时运行的最大实例数
        job_defaults = {
            'misfire_grace_time': 3600,  # 1小时容错期
            'coalesce': True,             # 合并错过的执行
            'max_instances': 1            # 默认单实例运行
        }
        self.scheduler = AsyncIOScheduler(
            timezone="Asia/Shanghai",
            job_defaults=job_defaults
        )
        self._started = False

    def add_job(
        self,
        func: Callable,
        job_id: str,
        trigger: str = "interval",
        **kwargs
    ) -> None:
        """添加定时任务

        Args:
            func: 任务函数
            job_id: 任务ID
            trigger: 触发器类型 (interval/cron/once)
            max_instances: 最大并行实例数（从 kwargs 提取）
            **kwargs: 其他参数
        """
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # 提取 max_instances 参数，用于控制并行执行
        max_instances = kwargs.pop("max_instances", None)
        next_run_time = kwargs.pop("next_run_time", None)  # 从数据库恢复的下次运行时间
        job_kwargs = {}
        if max_instances is not None:
            job_kwargs['max_instances'] = max_instances

        if trigger == "interval":
            minutes = kwargs.pop("minutes", 10)
            # 如果有数据库中的 next_run_time，使用它来保持重启后时间连续
            if next_run_time:
                job_kwargs['next_run_time'] = next_run_time
                logger.info(f"使用数据库时间恢复任务 {job_id}: {next_run_time}")
            self.scheduler.add_job(
                func,
                trigger=IntervalTrigger(minutes=minutes),
                id=job_id,
                replace_existing=True,
                **job_kwargs,
                **kwargs
            )
            logger.info(f"添加间隔任务: {job_id}, 间隔: {minutes}分钟, max_instances: {max_instances or 'default'}")
        elif trigger == "cron":
            expression = kwargs.pop("expression", None)
            if not expression:
                logger.error(f"Cron任务 {job_id} 缺少表达式")
                return
            self.scheduler.add_job(
                func,
                trigger=CronTrigger.from_crontab(expression),
                id=job_id,
                replace_existing=True,
                **job_kwargs,
                **kwargs
            )
            logger.info(f"添加Cron任务: {job_id}, 表达式: {expression}, max_instances: {max_instances or 'default'}")
        elif trigger == "once":
            run_date = kwargs.pop("run_date", None)
            if not run_date:
                logger.error(f"一次性任务 {job_id} 缺少运行时间")
                return
            self.scheduler.add_job(
                func,
                trigger=DateTrigger(run_date=run_date),
                id=job_id,
                replace_existing=True,
                **job_kwargs,
                **kwargs
            )
            logger.info(f"添加一次性任务: {job_id}, 时间: {run_date}")

    def remove_job(self, job_id: str) -> None:
        """移除定时任务"""
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"移除定时任务: {job_id}")

    def start(self) -> None:
        """启动调度器"""
        if not self._started:
            # 注册事件监听器
            from app.core.scheduler.events import on_job_executed, on_job_missed
            from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
            self.scheduler.add_listener(on_job_executed, EVENT_JOB_EXECUTED)
            self.scheduler.add_listener(on_job_missed, EVENT_JOB_MISSED)
            self.scheduler.start()
            self._started = True
            logger.info("调度器已启动")

    def shutdown(self) -> None:
        """关闭调度器"""
        if self._started:
            self.scheduler.shutdown()
            self._started = False
            logger.info("调度器已关闭")


# 单例
scheduler_manager = SchedulerManager()
