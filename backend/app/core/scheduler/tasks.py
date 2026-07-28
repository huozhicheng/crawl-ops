"""
内置系统任务

包含代理采集、代理验证、节点检测等系统级定时任务。
"""
from datetime import datetime, timedelta

from loguru import logger

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis_client import publish_stop_signals_batch
from app.models import Task, TaskExecution


async def run_proxy_crawl_task() -> None:
    """代理采集定时任务"""
    if not settings.PROXY_CRAWLING_ENABLED:
        logger.info("外部代理源采集未启用，跳过本次任务")
        return

    from app.core.database import SessionLocal
    from app.services.proxy_crawler import proxy_crawler_manager
    from app.services.proxy_service import proxy_service

    logger.info("开始执行代理采集任务...")

    try:
        # 采集代理
        proxies = await proxy_crawler_manager.crawl_all()

        if not proxies:
            logger.warning("未采集到任何代理")
            return

        # 入库
        db = SessionLocal()
        try:
            count = proxy_service.bulk_create(
                db, [f"{p.ip}:{p.port}" for p in proxies], protocol="http"
            )
            logger.info(f"代理采集任务完成，新增 {count} 个代理")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"代理采集任务异常: {e}")


async def run_proxy_verify_task() -> None:
    """代理验证定时任务（并发验证，不阻塞）"""
    import asyncio

    from app.core.database import SessionLocal
    from app.models import Proxy
    from app.services.proxy_service import proxy_service

    logger.info("开始执行代理验证任务...")

    db = SessionLocal()
    try:
        # 获取需要验证的代理（评分低于80或超过1小时未验证）
        proxies, _ = proxy_service.get_list(db, page=1, page_size=50, status=1)

        if not proxies:
            logger.info("没有需要验证的代理")
            return

        # 并发验证所有代理（不阻塞事件循环）
        async def verify_one(proxy):
            result = await proxy_service.verify_async(proxy)
            return (proxy, result)

        results = await asyncio.gather(*[verify_one(p) for p in proxies], return_exceptions=True)

        # 统一更新数据库
        verified_count = 0
        for item in results:
            if isinstance(item, Exception):
                logger.warning(f"验证代理失败: {item}")
                continue
            proxy, result = item
            proxy_service.update_proxy_after_verify(db, proxy, result)
            if result["valid"]:
                verified_count += 1

        db.commit()
        logger.info(f"代理验证任务完成，验证 {len(proxies)} 个，有效 {verified_count} 个")
    except Exception as e:
        logger.error(f"代理验证任务异常: {e}")
    finally:
        db.close()


async def run_node_check_task() -> None:
    """节点离线检测定时任务"""
    from app.core.database import SessionLocal
    from app.services.node_service import node_service

    logger.debug("检查节点在线状态...")

    db = SessionLocal()
    try:
        count = node_service.check_offline_nodes(db)
        if count > 0:
            logger.info(f"检测到 {count} 个节点离线")
    except Exception as e:
        logger.error(f"节点检查任务异常: {e}")
    finally:
        db.close()


async def clean_stale_executions() -> None:
    """
    清理卡住的执行记录

    - pending 超过 5 分钟 → failed (调度失败)
    - running 超过 task.timeout_seconds → timeout，并发送停止信号到 Worker
    """
    logger.debug("检查卡住的执行记录...")

    db = SessionLocal()
    try:
        now = datetime.now()
        pending_timeout = timedelta(minutes=settings.PENDING_TIMEOUT_MINUTES)

        # 1. 清理卡住的 pending 执行（超过5分钟）
        stale_pending = (
            db.query(TaskExecution)
            .filter(
                TaskExecution.status == "pending", TaskExecution.start_time < now - pending_timeout
            )
            .all()
        )

        for execution in stale_pending:
            execution.status = "failed"
            execution.error_message = "调度超时：任务未被 Worker 接收"
            execution.end_time = now
            if execution.start_time:
                execution.duration = int((now - execution.start_time).total_seconds())
            logger.warning(f"执行 {execution.id} 调度超时 (pending > 5分钟)，标记为 failed")

        # 2. 清理卡住的 running 执行（超过任务配置的 timeout_seconds）
        stale_running = (
            db.query(TaskExecution)
            .join(Task)
            .filter(
                TaskExecution.status == "running",
                TaskExecution.start_time < now - timedelta(seconds=1),  # 至少运行1秒
            )
            .all()
        )

        # 收集需要发送停止信号的执行 ID
        timeout_execution_ids = []

        for execution in stale_running:
            task = execution.task
            timeout_seconds = task.timeout_seconds if task else 3600

            if (
                execution.start_time
                and (now - execution.start_time).total_seconds() > timeout_seconds
            ):
                execution.status = "timeout"
                execution.error_message = f"执行超时：超过 {timeout_seconds} 秒"
                execution.end_time = now
                execution.duration = int((now - execution.start_time).total_seconds())
                timeout_execution_ids.append(execution.id)
                logger.warning(f"执行 {execution.id} 执行超时 (>{timeout_seconds}秒)，标记为 timeout")

        if stale_pending or timeout_execution_ids:
            db.commit()
            logger.info(
                f"清理卡住的执行记录：{len(stale_pending)} 个 pending，{len(timeout_execution_ids)} 个 timeout"
            )

        # 发送停止信号到 Worker，确保进程被终止
        if timeout_execution_ids:
            publish_stop_signals_batch(timeout_execution_ids, "TIMEOUT")

    except Exception as e:
        logger.error(f"清理执行记录任务异常: {e}")
        db.rollback()
    finally:
        db.close()
