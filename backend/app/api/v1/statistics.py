from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Any

from app.core.database import get_db
from app.services.statistics_service import statistics_service

router = APIRouter()

@router.get("/trend")
async def get_trend(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """获取执行趋势"""
    return statistics_service.get_execution_trend(db, days)

@router.get("/ranking")
async def get_ranking(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """获取项目活跃度排行"""
    return statistics_service.get_project_ranking(db, limit)

@router.get("/distribution")
async def get_distribution(db: Session = Depends(get_db)):
    """获取任务状态分布"""
    return statistics_service.get_status_distribution(db)
