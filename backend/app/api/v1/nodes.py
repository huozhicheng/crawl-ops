"""
节点管理API

提供节点CRUD、心跳、注册、状态检测接口。
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.node_service import node_service

router = APIRouter()
worker_router = APIRouter()


# ===== 请求/响应模型 =====


class NodeCreate(BaseModel):
    """创建节点请求"""

    name: str
    host: str
    port: int = 8080


class NodeUpdate(BaseModel):
    """更新节点请求"""

    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None


class HeartbeatRequest(BaseModel):
    """心跳请求"""

    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    os_type: Optional[str] = None
    network_sent: Optional[int] = None
    network_recv: Optional[int] = None


class NodeRegisterRequest(BaseModel):
    """节点注册请求"""

    name: str
    host: str
    port: int = 8080
    os_type: Optional[str] = None


# ===== API端点 =====


@router.get("")
async def get_nodes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取节点列表"""
    items, total = node_service.get_list(db, page, page_size, status)
    return {
        "items": [
            {
                "id": n.id,
                "name": n.name,
                "host": n.host,
                "port": n.port,
                "status": n.status,
                "os_type": n.os_type,
                "cpu_usage": float(n.cpu_usage) if n.cpu_usage else None,
                "memory_usage": float(n.memory_usage) if n.memory_usage else None,
                "disk_usage": float(n.disk_usage) if n.disk_usage else None,
                "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
            }
            for n in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
async def create_node(data: NodeCreate, db: Session = Depends(get_db)):
    """添加节点"""
    node = node_service.create(db, **data.model_dump())
    return {"message": "添加成功", "id": node.id, "token": node.token}  # 返回Token供节点使用


@router.get("/{node_id}")
async def get_node(node_id: int, db: Session = Depends(get_db)):
    """获取节点详情"""
    node = node_service.get_by_id(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    return {
        "id": node.id,
        "name": node.name,
        "host": node.host,
        "port": node.port,
        "token": node.token,
        "status": node.status,
        "os_type": node.os_type,
        "cpu_usage": float(node.cpu_usage) if node.cpu_usage else None,
        "memory_usage": float(node.memory_usage) if node.memory_usage else None,
        "disk_usage": float(node.disk_usage) if node.disk_usage else None,
        "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None,
        "created_at": node.created_at.isoformat() if node.created_at else None,
    }


@router.put("/{node_id}")
async def update_node(node_id: int, data: NodeUpdate, db: Session = Depends(get_db)):
    """更新节点"""
    node = node_service.get_by_id(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    node_service.update(db, node, **data.model_dump(exclude_unset=True))
    return {"message": "更新成功"}


@router.delete("/{node_id}")
async def delete_node(node_id: int, db: Session = Depends(get_db)):
    """删除节点"""
    node = node_service.get_by_id(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    if node.status == "online":
        raise HTTPException(status_code=400, detail="无法删除在线节点，请先停止节点")

    node_service.delete(db, node)
    return {"message": "删除成功"}


@worker_router.post("/heartbeat")
async def node_heartbeat(
    data: HeartbeatRequest,
    x_node_token: str = Header(..., alias="X-Node-Token"),
    db: Session = Depends(get_db),
):
    """
    节点心跳

    节点定期调用此接口上报状态，需在Header中携带X-Node-Token
    """
    from app.models import NodeMetric

    node = node_service.get_by_token(db, x_node_token)
    if not node:
        raise HTTPException(status_code=401, detail="无效的节点Token")

    # 更新节点状态
    node_service.heartbeat(
        db,
        node,
        cpu_usage=data.cpu_usage,
        memory_usage=data.memory_usage,
        disk_usage=data.disk_usage,
        os_type=data.os_type,
    )

    # 存储历史记录
    metric = NodeMetric(
        node_id=node.id,
        cpu_usage=data.cpu_usage,
        memory_usage=data.memory_usage,
        disk_usage=data.disk_usage,
        network_sent=data.network_sent,
        network_recv=data.network_recv,
    )
    db.add(metric)
    db.commit()

    return {"message": "心跳成功", "node_id": node.id}


@worker_router.post("/register")
async def node_register(
    data: NodeRegisterRequest,
    x_worker_registration_token: str = Header(..., alias="X-Worker-Registration-Token"),
    db: Session = Depends(get_db),
):
    """
    节点注册

    新节点首次连接时调用，使用部署时分发的注册令牌验证身份。
    """
    expected_token = settings.WORKER_REGISTRATION_TOKEN
    if not expected_token or not secrets.compare_digest(
        x_worker_registration_token, expected_token
    ):
        raise HTTPException(status_code=401, detail="无效的 Worker 注册令牌")

    node = node_service.create(
        db, name=data.name, host=data.host, port=data.port, os_type=data.os_type
    )

    return {"message": "注册成功", "node_id": node.id, "token": node.token}


@router.post("/{node_id}/ping")
async def ping_node(node_id: int, db: Session = Depends(get_db)):
    """
    检测节点状态

    主动向节点发送请求检测其可用性
    """
    node = node_service.get_by_id(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # TODO: 实际向节点发送HTTP请求检测
    # 这里简化处理，直接返回当前状态
    return {
        "node_id": node.id,
        "status": node.status,
        "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None,
    }
