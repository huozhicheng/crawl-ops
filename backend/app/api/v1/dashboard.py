from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from loguru import logger

from app.core.database import get_db
from app.schemas import DashboardOverview, ExecutionResponse
from app.services import project_service, task_service, proxy_service, node_service
from app.services.task_service import execution_service
from app.models import Node

router = APIRouter()


@router.get("/overview")
async def get_overview(db: Session = Depends(get_db)):
    """系统概览 - 增强版"""
    from app.models import Task, TaskExecution, Venv
    from sqlalchemy import func

    # 计算节点平均资源使用率
    online_nodes = db.query(Node).filter(Node.status == "online").all()
    avg_cpu = 0
    avg_mem = 0
    avg_disk = 0
    if online_nodes:
        total_cpu = sum([float(n.cpu_usage or 0) for n in online_nodes])
        total_mem = sum([float(n.memory_usage or 0) for n in online_nodes])
        total_disk = sum([float(n.disk_usage or 0) for n in online_nodes])
        avg_cpu = round(total_cpu / len(online_nodes), 1)
        avg_mem = round(total_mem / len(online_nodes), 1)
        avg_disk = round(total_disk / len(online_nodes), 1)

    # 活跃任务数 (status=1)
    active_tasks = db.query(Task).filter(Task.status == 1).count()

    # 虚拟环境数
    total_venvs = db.query(Venv).count()

    # 执行统计
    total_executions = db.query(TaskExecution).count()
    success_count = db.query(TaskExecution).filter(TaskExecution.status == 'success').count()
    failed_count = db.query(TaskExecution).filter(TaskExecution.status == 'failed').count()

    # 平均执行时长
    avg_duration_result = db.query(func.avg(TaskExecution.duration)).filter(
        TaskExecution.duration.isnot(None)
    ).scalar()
    avg_duration = round(float(avg_duration_result or 0), 1)

    return {
        "total_projects": project_service.count(db),
        "total_tasks": task_service.count(db),
        "active_tasks": active_tasks,
        "total_venvs": total_venvs,
        "today_executions": execution_service.count_today(db),
        "success_rate": execution_service.success_rate(db),
        "online_nodes": len(online_nodes),
        "available_proxies": proxy_service.count_available(db),
        "total_executions": total_executions,
        "success_count": success_count,
        "failed_count": failed_count,
        "avg_duration": avg_duration,
        "avg_cpu": avg_cpu,
        "avg_mem": avg_mem,
        "avg_disk": avg_disk,
    }


@router.get("/trend")
async def get_trend(days: int = 7, db: Session = Depends(get_db)):
    """任务执行趋势"""
    from app.services.statistics_service import statistics_service
    return statistics_service.get_execution_trend(db, days)


@router.get("/recent-executions")
async def get_recent_executions(limit: int = 10, db: Session = Depends(get_db)):
    """最近执行列表"""
    items = execution_service.get_recent(db, limit)
    return {"items": [ExecutionResponse.model_validate(e) for e in items]}


@router.get("/failures")
async def get_failures(limit: int = 5, db: Session = Depends(get_db)):
    """最近失败任务"""
    items, _ = execution_service.get_list(db, page=1, page_size=limit, status="failed")
    return {"items": [ExecutionResponse.model_validate(e) for e in items]}


@router.get("/nodes-monitor")
async def get_nodes_monitor(db: Session = Depends(get_db)):
    """节点资源监控"""
    items, _ = node_service.get_list(db, page=1, page_size=100, status="online")
    return {
        "items": [
            {
                "id": n.id,
                "name": n.name,
                "cpu_usage": float(n.cpu_usage or 0),
                "memory_usage": float(n.memory_usage or 0),
                "disk_usage": float(n.disk_usage or 0),
                "last_heartbeat": n.last_heartbeat
            }
            for n in items
        ]
    }


@router.get("/node-history")
async def get_node_history(
    node_id: int = Query(...),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """获取节点性能历史"""
    from app.models import NodeMetric

    metrics = db.query(NodeMetric).filter(
        NodeMetric.node_id == node_id
    ).order_by(
        NodeMetric.created_at.desc()
    ).limit(limit).all()

    # 反转顺序，使时间从早到晚
    metrics = list(reversed(metrics))

    return {
        "items": [
            {
                "cpu_usage": float(m.cpu_usage or 0),
                "memory_usage": float(m.memory_usage or 0),
                "disk_usage": float(m.disk_usage or 0),
                "network_sent": m.network_sent or 0,
                "network_recv": m.network_recv or 0,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in metrics
        ]
    }


@router.get("/risks")
async def get_risks(db: Session = Depends(get_db)):
    """风险中心数据"""
    from app.models import Proxy

    # 1. 最近失败任务 (Top 5)
    failures, _ = execution_service.get_list(db, page=1, page_size=5, status="failed")

    # 2. 离线节点
    offline_nodes = db.query(Node).filter(Node.status == "offline").all()

    # 3. 亚健康代理 (分数<60)
    risky_proxies_count = db.query(Proxy).filter(Proxy.status == 1, Proxy.score < 60).count()

    return {
        "failures": [ExecutionResponse.model_validate(e) for e in failures],
        "offline_nodes": [
            {"id": n.id, "name": n.name, "last_heartbeat": n.last_heartbeat}
            for n in offline_nodes
        ],
        "risky_proxies_count": risky_proxies_count
    }


@router.get("/upcoming")
async def get_upcoming(limit: int = 5, db: Session = Depends(get_db)):
    """未来调度任务"""
    from datetime import datetime
    from app.models import Task

    # 直接查询 scheduled_time
    tasks = db.query(Task).filter(
        Task.status == 1,
        Task.scheduled_time.isnot(None),
        Task.scheduled_time > datetime.now()
    ).order_by(Task.scheduled_time.asc()).limit(limit).all()

    upcoming = []
    for task in tasks:
        upcoming.append({
            "task_id": task.id,
            "task_name": task.name,
            "schedule_type": task.schedule_type,
            "cron": task.cron_expression if task.schedule_type == "cron" else f"{task.interval_seconds}s",
            "next_run": task.scheduled_time
        })

    return {"items": upcoming}
