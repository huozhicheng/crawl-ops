"""
任务依赖模型
"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class TaskDependency(Base):
    """任务依赖关系表"""

    __tablename__ = "task_dependencies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id"), nullable=False, comment="当前任务ID")
    depends_on_task_id = Column(
        BigInteger, ForeignKey("tasks.id"), nullable=False, comment="依赖的任务ID"
    )
    condition_type = Column(String(20), default="success", comment="success/complete/any")
    created_at = Column(DateTime, default=datetime.now)
