"""
审计日志模型
"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String, Text

from app.core.database import Base


class AuditLog(Base):
    """审计日志表"""

    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    username = Column(String(50))
    action = Column(String(50), nullable=False, comment="create/update/delete/login/logout")
    resource_type = Column(String(50), comment="project/task/user/node/proxy")
    resource_id = Column(BigInteger)
    resource_name = Column(String(100))
    detail = Column(Text)
    ip = Column(String(50))
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)
