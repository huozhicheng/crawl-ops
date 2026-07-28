"""
调度器工具函数
"""
from datetime import datetime, timedelta
from typing import Optional
import random

from loguru import logger


def get_job_next_run_time(job, scheduler_timezone=None) -> Optional[datetime]:
    """
    获取任务的下次运行时间

    统一从 job 对象中提取下次运行时间，支持多种 trigger 类型。
    使用 naive datetime 统一处理。
    """
    import pytz

    # 优先使用 job.next_run_time
    next_run_time = getattr(job, 'next_run_time', None)

    # 如果没有，尝试从 trigger 计算
    if not next_run_time and hasattr(job, 'trigger'):
        try:
            # 使用带时区的 now 避免 offset-naive/aware 比较错误
            tz = scheduler_timezone or pytz.timezone('Asia/Shanghai')
            now = datetime.now(tz)
            next_run_time = job.trigger.get_next_fire_time(None, now)
        except Exception as e:
            logger.warning(f"Failed to calculate next run time: {e}")

    # 转换为 naive datetime (移除时区信息)
    if next_run_time and hasattr(next_run_time, 'replace'):
        if next_run_time.tzinfo is not None:
            next_run_time = next_run_time.replace(tzinfo=None)

    return next_run_time


def get_next_random_time(start_hour: int, end_hour: int) -> datetime:
    """
    计算下一个随机执行时间

    Args:
        start_hour: 开始小时 (0-22)
        end_hour: 结束小时 (1-23)，必须大于 start_hour

    Returns:
        下次随机执行的 datetime

    Raises:
        ValueError: 参数校验失败
    """
    # 参数边界校验
    if not isinstance(start_hour, int) or not isinstance(end_hour, int):
        raise ValueError("开始小时和结束小时必须是整数")

    if start_hour < 0 or start_hour > 22:
        raise ValueError(f"开始小时必须在 0-22 范围内，当前值: {start_hour}")

    if end_hour < 1 or end_hour > 23:
        raise ValueError(f"结束小时必须在 1-23 范围内，当前值: {end_hour}")

    if start_hour >= end_hour:
        raise ValueError(f"开始时间必须小于结束时间: start_hour={start_hour}, end_hour={end_hour}")

    now = datetime.now()

    # 如果当前时间在范围内，使用明天；否则判断是之前还是之后
    if now.hour < start_hour:
        target_date = now
    elif now.hour >= end_hour:
        target_date = now + timedelta(days=1)
    else:
        # 当前在范围内，下一次在明天
        target_date = now + timedelta(days=1)

    random_hour = random.randint(start_hour, end_hour - 1)
    random_minute = random.randint(0, 59)

    return target_date.replace(hour=random_hour, minute=random_minute, second=0, microsecond=0)
