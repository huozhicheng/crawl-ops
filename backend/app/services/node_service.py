"""
节点服务模块

提供节点管理、心跳处理、状态监控功能。
"""

import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from loguru import logger
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.redis_client import publish_stop_signals_batch
from app.models import Node, TaskExecution


class NodeService:
    """节点服务"""

    # 心跳超时时间（秒），超过此时间无心跳则标记为离线
    HEARTBEAT_TIMEOUT = 60

    @staticmethod
    def get_by_id(db: Session, node_id: int, include_deleted: bool = False) -> Optional[Node]:
        """根据ID获取节点"""
        query = db.query(Node).filter(Node.id == node_id)
        if not include_deleted:
            query = query.filter(Node.deleted == 0)
        return query.first()

    @staticmethod
    def get_by_token(db: Session, token: str) -> Optional[Node]:
        """根据Token获取节点"""
        return db.query(Node).filter(Node.token == token).first()

    @staticmethod
    def get_list(
        db: Session, page: int = 1, page_size: int = 20, status: Optional[str] = None
    ) -> Tuple[List[Node], int]:
        """获取节点列表"""
        query = db.query(Node)

        if status:
            query = query.filter(Node.status == status)

        # 过滤已删除的节点
        query = query.filter(Node.deleted == 0)

        total = query.count()
        items = query.order_by(Node.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def create(db: Session, name: str, host: str, port: int = 8080, **kwargs) -> Node:
        """创建节点"""
        # 生成唯一Token
        token = secrets.token_urlsafe(32)

        node = Node(name=name, host=host, port=port, token=token, status="offline", **kwargs)
        db.add(node)
        db.commit()
        db.refresh(node)

        logger.info(f"创建节点: {name} ({host}:{port})")
        return node

    @staticmethod
    def update(db: Session, node: Node, **kwargs) -> Node:
        """更新节点"""
        for key, value in kwargs.items():
            if value is not None and hasattr(node, key):
                setattr(node, key, value)
        db.commit()
        db.refresh(node)
        return node

    @staticmethod
    def delete(db: Session, node: Node) -> None:
        """删除节点 (软删除)"""
        logger.info(f"删除节点: {node.name}")
        node.deleted = 1
        node.status = "offline"
        db.commit()

    @staticmethod
    def heartbeat(
        db: Session,
        node: Node,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None,
        disk_usage: Optional[float] = None,
        os_type: Optional[str] = None,
    ) -> Node:
        """
        处理节点心跳

        节点定期发送心跳，上报资源使用情况
        """
        node.last_heartbeat = datetime.now()
        node.status = "online"

        if cpu_usage is not None:
            node.cpu_usage = cpu_usage
        if memory_usage is not None:
            node.memory_usage = memory_usage
        if disk_usage is not None:
            node.disk_usage = disk_usage
        if os_type is not None:
            node.os_type = os_type

        db.commit()
        db.refresh(node)

        logger.debug(f"节点心跳: {node.name}, CPU: {cpu_usage}%, MEM: {memory_usage}%")
        return node

    @staticmethod
    def check_offline_nodes(db: Session) -> int:
        """
        检查并标记离线节点

        超过HEARTBEAT_TIMEOUT秒无心跳的节点标记为离线
        同时处理该节点上正在运行的任务
        返回新标记为离线的节点数量
        """
        timeout_threshold = datetime.now() - timedelta(seconds=NodeService.HEARTBEAT_TIMEOUT)

        # 查找超时的在线节点
        offline_nodes = (
            db.query(Node)
            .filter(
                and_(
                    Node.status == "online",
                    Node.deleted == 0,
                    Node.last_heartbeat < timeout_threshold,
                )
            )
            .all()
        )

        if not offline_nodes:
            return 0

        # 收集离线节点 ID
        offline_node_ids = [node.id for node in offline_nodes]
        node_name_map = {node.id: node.name for node in offline_nodes}

        # 标记节点离线
        for node in offline_nodes:
            node.status = "offline"
            logger.warning(f"节点离线: {node.name}")

        # 修复 #6: 使用 IN 查询一次获取所有关联的 running 任务（避免 N+1）
        running_executions = (
            db.query(TaskExecution)
            .filter(TaskExecution.node_id.in_(offline_node_ids), TaskExecution.status == "running")
            .all()
        )

        # 处理关联任务
        failed_execution_ids = NodeService._fail_executions_by_node_offline(
            db, running_executions, node_name_map
        )

        db.commit()
        logger.info(
            f"标记 {len(offline_nodes)} 个节点为离线，{len(failed_execution_ids)} 个任务为失败"
        )

        # 发送停止信号
        if failed_execution_ids:
            publish_stop_signals_batch(failed_execution_ids, "NODE_OFFLINE")

        return len(offline_nodes)

    @staticmethod
    def _fail_executions_by_node_offline(
        db: Session, executions: list, node_name_map: dict
    ) -> List[int]:
        """
        将执行记录标记为失败（节点离线导致）

        Args:
            db: 数据库会话
            executions: 执行记录列表
            node_name_map: 节点ID到名称的映射

        Returns:
            失败的执行ID列表
        """
        failed_ids = []
        now = datetime.now()

        for execution in executions:
            node_name = node_name_map.get(execution.node_id, "Unknown")
            execution.status = "failed"
            execution.error_message = f"Worker 节点 {node_name} 离线"
            execution.end_time = now
            if execution.start_time:
                execution.duration = int((now - execution.start_time).total_seconds())
            failed_ids.append(execution.id)
            logger.warning(f"节点 {node_name} 离线，标记执行 {execution.id} 为 failed")

        return failed_ids

    @staticmethod
    def count_online(db: Session) -> int:
        """统计在线节点数量"""
        return db.query(Node).filter(Node.status == "online", Node.deleted == 0).count()

    @staticmethod
    def get_available_node(db: Session) -> Optional[Node]:
        """
        获取可用节点（用于任务分发）

        选择在线且负载最低的节点
        """
        nodes = db.query(Node).filter(Node.status == "online", Node.deleted == 0).all()

        if not nodes:
            return None

        # 按CPU使用率排序，选择负载最低的
        nodes.sort(key=lambda n: n.cpu_usage or 100)
        return nodes[0]


node_service = NodeService()
