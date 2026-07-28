from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.audit_service import audit_service

router = APIRouter()


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[int]
    detail: Optional[str]
    ip: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int


@router.get("", response_model=AuditListResponse)
async def list_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """查询审计日志"""
    items, total = audit_service.get_list(
        db, page, page_size, username, action, resource_type, start_time, end_time
    )
    return {"items": items, "total": total}
