"""
调度器模块

拆分为：
- manager.py: SchedulerManager 核心类
- events.py: 事件处理
- tasks.py: 内置系统任务
- sync.py: 用户任务同步逻辑
- utils.py: 工具函数
"""
from app.core.scheduler.manager import scheduler_manager, SchedulerManager
from app.core.scheduler.tasks import (
    run_proxy_crawl_task,
    run_proxy_verify_task,
    run_node_check_task,
    clean_stale_executions,
)
from app.core.scheduler.sync import (
    sync_task_to_scheduler,
    sync_all_tasks,
    run_user_task,
    run_random_task,
)

def init_scheduler() -> None:
    """初始化调度器，注册定时任务"""
    # 1. 注册核心系统任务
    # 代理采集任务：每10分钟
    scheduler_manager.add_job(
        run_proxy_crawl_task,
        job_id="proxy_crawl",
        minutes=10
    )

    # 代理验证任务：每5分钟
    scheduler_manager.add_job(
        run_proxy_verify_task,
        job_id="proxy_verify",
        minutes=5
    )

    # 节点离线检测任务：每1分钟
    scheduler_manager.add_job(
        run_node_check_task,
        job_id="node_check",
        minutes=1
    )

    # 清理卡住的执行记录：每1分钟
    scheduler_manager.add_job(
        clean_stale_executions,
        job_id="clean_stale_executions",
        minutes=1
    )

    # 2. 同步用户定义的爬虫任务
    sync_all_tasks()

    # 启动调度器
    scheduler_manager.start()


__all__ = [
    "scheduler_manager",
    "SchedulerManager",
    "init_scheduler",
    "sync_task_to_scheduler",
    "sync_all_tasks",
    "run_user_task",
    "run_random_task",
]
