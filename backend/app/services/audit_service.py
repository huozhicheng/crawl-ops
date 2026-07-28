import json
from typing import Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditService:
    """审计日志服务"""

    @staticmethod
    def log(
        db: Session,
        user_id: int,
        username: str,
        action: str,
        resource_type: str,
        resource_id: Optional[int],
        detail: Optional[dict] = None,
        ip: str = "unknown",
    ) -> AuditLog:
        """记录审计日志"""
        try:
            log_entry = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=json.dumps(detail, ensure_ascii=False) if detail else None,
                ip=ip,
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            logger.info(f"Audit log created: {username} {action} {resource_type}:{resource_id}")
            return log_entry
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            db.rollback()
            return None

    @staticmethod
    def get_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Tuple[list, int]:
        """查询审计日志"""
        query = db.query(AuditLog)

        if username:
            query = query.filter(AuditLog.username.like(f"%{username}%"))
        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if start_time:
            query = query.filter(AuditLog.created_at >= start_time)
        if end_time:
            query = query.filter(AuditLog.created_at <= end_time)

        total = query.count()
        items = (
            query.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        )
        return items, total


audit_service = AuditService()
