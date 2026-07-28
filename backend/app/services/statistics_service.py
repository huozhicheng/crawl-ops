from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
from typing import List, Dict

from app.models import TaskExecution, Project, Task

class StatisticsService:
    """统计报表服务"""

    @staticmethod
    def get_execution_trend(db: Session, days: int = 7) -> Dict:
        """获取执行趋势"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)

        # 按日期聚合
        stats = db.query(
             func.date(TaskExecution.created_at).label('date'),
             func.sum(case((TaskExecution.status == 'success', 1), else_=0)).label('success'),
             func.sum(case((TaskExecution.status == 'failed', 1), else_=0)).label('failed'),
             func.count(TaskExecution.id).label('total')
        ).filter(
            TaskExecution.created_at >= start_date
        ).group_by(
            func.date(TaskExecution.created_at)
        ).all()

        # 补全日期
        date_map = {stat.date: stat for stat in stats}
        dates = []
        success_data = []
        failed_data = []

        for i in range(days):
            date = start_date + timedelta(days=i)
            dates.append(date.isoformat())
            if date in date_map:
                success_data.append(int(date_map[date].success or 0))
                failed_data.append(int(date_map[date].failed or 0))
            else:
                success_data.append(0)
                failed_data.append(0)

        return {
            "dates": dates,
            "success": success_data,
            "failed": failed_data
        }

    @staticmethod
    def get_project_ranking(db: Session, limit: int = 10) -> List[Dict]:
        """获取项目活跃度排行"""
        stats = db.query(
            Project.name,
            func.count(TaskExecution.id).label('count')
        ).join(
            Task, Task.project_id == Project.id
        ).join(
            TaskExecution, TaskExecution.task_id == Task.id
        ).group_by(
            Project.id
        ).order_by(
            func.count(TaskExecution.id).desc()
        ).limit(limit).all()

        return [{"name": s.name, "count": s.count} for s in stats]

    @staticmethod
    def get_status_distribution(db: Session) -> List[Dict]:
        """获取任务状态分布"""
        stats = db.query(
            TaskExecution.status,
            func.count(TaskExecution.id).label('count')
        ).group_by(
            TaskExecution.status
        ).all()

        return [{"name": s.status, "value": s.count} for s in stats]

statistics_service = StatisticsService()
