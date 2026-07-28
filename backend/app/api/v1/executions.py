from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.task_service import execution_service

router = APIRouter()


@router.get("")
async def get_executions(
    page: int = 1,
    page_size: int = 20,
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取执行记录列表"""
    from datetime import datetime

    st = None
    if start_time and start_time.strip():
        try:
            st = datetime.fromisoformat(start_time)
        except ValueError:
            pass

    et = None
    if end_time and end_time.strip():
        try:
            et = datetime.fromisoformat(end_time)
        except ValueError:
            pass

    items, total = execution_service.get_list(
        db=db,
        page=page,
        page_size=page_size,
        task_id=task_id,
        status=status,
        start_time=st,
        end_time=et,
    )
    return {
        "items": [
            {
                "id": item.id,
                "task_id": item.task_id,
                "task_name": item.task.name if item.task else "Unknown",
                "trigger_type": item.trigger_type,
                "status": item.status,
                "start_time": item.start_time.isoformat() if item.start_time else None,
                "end_time": item.end_time.isoformat() if item.end_time else None,
                "duration": item.duration,
                "exit_code": item.exit_code,
                "error_message": item.error_message,
            }
            for item in items
        ],
        "total": total,
    }


@router.get("/{execution_id}")
async def get_execution(execution_id: int, db: Session = Depends(get_db)):
    """获取执行详情"""
    item = execution_service.get_by_id(db, execution_id)
    if not item:
        return {"error": "执行记录不存在"}
    return {
        "id": item.id,
        "task_id": item.task_id,
        "trigger_type": item.trigger_type,
        "status": item.status,
        "start_time": item.start_time.isoformat() if item.start_time else None,
        "end_time": item.end_time.isoformat() if item.end_time else None,
        "duration": item.duration,
        "exit_code": item.exit_code,
        "error_message": item.error_message,
    }


@router.get("/{execution_id}/logs")
async def get_execution_logs(
    execution_id: int,
    lines: int = 200,
    offset: int = 0,
    after_line: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    获取执行日志内容

    Args:
        execution_id: 执行记录ID
        lines: 返回行数（默认200）
        offset: 从文件末尾偏移行数（用于加载更多历史日志）
        after_line: 增量获取，只返回该行号之后的新内容（用于 tail -f 效果）
    """
    import os

    from app.core.config import settings

    log_path = os.path.join(settings.LOGS_DIR, "executions", f"{execution_id}.log")
    if not os.path.exists(log_path):
        return {"content": "", "total_lines": 0, "loaded_lines": 0, "has_more": False}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)

        # 增量模式：只返回新行（用于 tail -f 效果）
        if after_line is not None:
            if after_line >= total_lines:
                return {
                    "content": "",
                    "total_lines": total_lines,
                    "loaded_lines": 0,
                    "start_line": after_line + 1,
                    "has_more": False,
                }
            new_lines = all_lines[after_line:]
            return {
                "content": "".join(new_lines),
                "total_lines": total_lines,
                "loaded_lines": len(new_lines),
                "start_line": after_line + 1,
                "has_more": False,
            }

        # 分页模式：返回最后 N 行
        end_idx = total_lines - offset
        if end_idx <= 0:
            return {"content": "", "total_lines": total_lines, "loaded_lines": 0, "has_more": False}

        start_idx = max(0, end_idx - lines)
        selected_lines = all_lines[start_idx:end_idx]

        return {
            "content": "".join(selected_lines),
            "total_lines": total_lines,
            "loaded_lines": len(selected_lines),
            "start_line": start_idx + 1,
            "has_more": start_idx > 0,
        }
    except Exception as e:
        return {
            "content": f"读取日志失败: {str(e)}",
            "total_lines": 0,
            "loaded_lines": 0,
            "has_more": False,
        }


@router.post("/{execution_id}/stop")
async def stop_execution(execution_id: int, db: Session = Depends(get_db)):
    """
    停止执行
    如果 Worker 在线，发送停止信号；如果 Worker 已离线，直接标记为 stopped
    """
    from datetime import datetime

    from loguru import logger

    from app.core.redis_client import publish_stop_signal
    from app.models import Node

    logger.info(f"收到停止执行请求: execution_id={execution_id}")

    item = execution_service.get_by_id(db, execution_id)
    if not item:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    if item.status != "running":
        raise HTTPException(status_code=400, detail="只能停止运行中的任务")

    # P2: 检查执行任务的 Worker 节点是否在线
    if item.node_id:
        node = db.query(Node).filter(Node.id == item.node_id).first()
        if node and node.status == "offline":
            # Worker 已离线，直接标记任务为 stopped
            item.status = "stopped"
            item.error_message = f"Worker 节点 {node.name} 已离线，任务已停止"
            item.end_time = datetime.now()
            if item.start_time:
                item.duration = int((item.end_time - item.start_time).total_seconds())
            db.commit()
            logger.info(f"节点已离线，直接标记执行 {execution_id} 为 stopped")
            return {"message": "Worker 节点已离线，任务已停止"}

    # 发布停止信号到 Redis Pub/Sub，Worker 会监听并处理
    if not publish_stop_signal(execution_id, "STOP"):
        raise HTTPException(status_code=500, detail="发送停止信号失败")

    return {"message": "停止信号已发送"}


@router.post("/{execution_id}/start")
async def start_execution(
    execution_id: int, node_id: Optional[int] = None, db: Session = Depends(get_db)
):
    """
    Worker 回调接口 - 标记执行开始
    将状态从 pending 更新为 running，并记录执行节点
    """
    from loguru import logger

    logger.info(f"收到执行开始通知: execution_id={execution_id}, node_id={node_id}")

    item = execution_service.get_by_id(db, execution_id)
    if not item:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    # 只有 pending 状态才能转为 running
    if item.status == "pending":
        item.status = "running"
        if node_id:
            item.node_id = node_id  # 记录执行该任务的 Worker 节点
        db.commit()
        logger.info(f"执行 {execution_id} 状态更新为 running, node_id={node_id}")
    else:
        logger.warning(f"执行 {execution_id} 当前状态为 {item.status}，跳过 start 更新")

    return {"message": "ok"}


from pydantic import BaseModel


class ExecutionCallback(BaseModel):
    status: str
    exit_code: int
    error_message: Optional[str] = None


@router.post("/{execution_id}/callback")
async def execution_callback(
    execution_id: int, data: ExecutionCallback, db: Session = Depends(get_db)
):
    """
    Worker 回调接口 - 更新执行状态
    如果任务失败且有重试配置，自动调度重试
    """
    from datetime import datetime, timedelta

    from loguru import logger

    item = execution_service.get_by_id(db, execution_id)
    if not item:
        raise HTTPException(status_code=404, detail="Execution not found")

    # 如果已经是终态（stopped/timeout），不允许被覆盖
    if item.status in ("stopped", "timeout"):
        logger.info(f"执行 {execution_id} 状态已是 {item.status}，忽略 callback")
        return {"message": f"Already {item.status}, ignored"}

    # 获取关联的任务，检查重试配置
    task = item.task

    execution_service.update(
        db, item, status=data.status, exit_code=data.exit_code, error_message=data.error_message
    )
    # Update end_time
    item.end_time = datetime.now()
    # Recalculate duration
    if item.start_time:
        item.duration = int((item.end_time - item.start_time).total_seconds())

    db.commit()

    # 检查是否需要重试
    should_retry = (
        data.status in ("failed", "timeout")
        and task
        and task.retry_count > 0
        and (item.retry_attempt or 0) < task.retry_count
    )

    if should_retry:
        retry_attempt = (item.retry_attempt or 0) + 1
        retry_delay = task.retry_interval or 60
        retry_time = datetime.now() + timedelta(seconds=retry_delay)

        logger.info(
            f"任务 {task.id} 执行失败，将在 {retry_delay}秒后进行第 {retry_attempt}/{task.retry_count} 次重试"
        )

        # 使用调度器在指定时间后执行重试
        from app.core.scheduler import scheduler_manager

        def schedule_retry():
            """延迟执行重试任务"""
            from app.core.database import SessionLocal
            from app.models import TaskExecution
            from app.services.task_service import task_service

            retry_db = SessionLocal()
            try:
                # 创建新的执行记录
                retry_execution = TaskExecution(
                    task_id=task.id,
                    trigger_type="retry",
                    status="pending",
                    retry_attempt=retry_attempt,
                    start_time=datetime.now(),
                )
                retry_db.add(retry_execution)
                retry_db.commit()
                retry_db.refresh(retry_execution)

                # 重新获取任务
                retry_task = task_service.get_by_id(retry_db, task.id)
                if retry_task:
                    # 推送到 Redis 队列
                    import json

                    import redis

                    from app.core.config import settings

                    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
                    # 获取虚拟环境路径
                    venv_path = None
                    if retry_task.venv_id and retry_task.venv:
                        venv_path = retry_task.venv.path

                    task_payload = {
                        "execution_id": retry_execution.id,
                        "task_id": retry_task.id,
                        "project_id": retry_task.project_id,
                        "project_code": retry_task.project.code,
                        "command": retry_task.command,
                        "arguments": retry_task.arguments,
                        "env_vars": retry_task.env_vars,
                        "venv_id": retry_task.venv_id,
                        "venv_path": venv_path,  # 传递虚拟环境路径供 Worker 使用
                        "timeout": retry_task.timeout_seconds,
                    }
                    r.lpush("crawlops:task:queue", json.dumps(task_payload))
                    logger.info(f"重试任务已推送: execution_id={retry_execution.id}")
            except Exception as e:
                logger.error(f"调度重试任务失败: {e}")
            finally:
                retry_db.close()

        # 添加一次性定时任务来执行重试
        scheduler_manager.add_job(
            schedule_retry,
            job_id=f"retry_{execution_id}_{retry_attempt}",
            trigger="once",
            run_date=retry_time,
        )

        return {"message": "Callback received, retry scheduled", "retry_at": retry_time.isoformat()}

    return {"message": "Callback received"}
