from datetime import datetime

from sqlalchemy import DECIMAL, BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True)
    phone = Column(String(20))
    avatar = Column(String(255))
    status = Column(Integer, default=1, comment="0禁用 1正常")
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Role(Base):
    """角色表"""

    __tablename__ = "roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)


class UserRole(Base):
    """用户角色关联表"""

    __tablename__ = "user_roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    role_id = Column(BigInteger, ForeignKey("roles.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class Project(Base):
    """项目表"""

    __tablename__ = "projects"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    type = Column(String(20), default="python")
    source_type = Column(String(20), nullable=False, comment="upload/git")
    git_url = Column(String(500))
    git_branch = Column(String(100), default="main")
    entry_file = Column(String(255))
    python_version = Column(String(20), default="3.10")
    status = Column(Integer, default=1)
    created_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    tasks = relationship("Task", back_populates="project")


class Task(Base):
    """任务表"""

    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=False)
    description = Column(Text)
    schedule_type = Column(String(20), nullable=False, comment="once/cron/interval/random")
    cron_expression = Column(String(100))
    interval_seconds = Column(Integer)
    scheduled_time = Column(DateTime)
    random_start_hour = Column(Integer, comment="随机调度开始小时 (0-23)")
    random_end_hour = Column(Integer, comment="随机调度结束小时 (0-23)")
    timeout_seconds = Column(Integer, default=3600)
    retry_count = Column(Integer, default=0)
    retry_interval = Column(Integer, default=60)
    node_id = Column(BigInteger)
    venv_id = Column(BigInteger, ForeignKey("venvs.id"))
    command = Column(String(500))
    arguments = Column(Text)
    env_vars = Column(Text)
    use_proxy = Column(Integer, default=0)
    proxy_policy = Column(String(20), default="direct", comment="fail/direct/wait")
    allow_parallel = Column(Integer, default=0, comment="是否允许并行执行")
    max_instances = Column(Integer, default=1, comment="最大并行实例数")
    status = Column(Integer, default=1)
    created_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    project = relationship("Project", back_populates="tasks")
    executions = relationship("TaskExecution", back_populates="task")
    venv = relationship("Venv", back_populates="tasks")


class TaskExecution(Base):
    """任务执行记录表"""

    __tablename__ = "task_executions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id"), nullable=False)
    node_id = Column(BigInteger)
    trigger_type = Column(String(20), nullable=False, comment="schedule/manual")
    status = Column(String(20), nullable=False, comment="pending/running/success/failed/timeout")
    retry_attempt = Column(Integer, default=0, comment="当前重试次数 (0=首次执行)")
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration = Column(Integer)
    exit_code = Column(Integer)
    error_message = Column(Text)
    result_data = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    task = relationship("Task", back_populates="executions")


class Node(Base):
    """节点表"""

    __tablename__ = "nodes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=8080)
    token = Column(String(255))
    os_type = Column(String(20))
    status = Column(String(20), default="offline")
    cpu_usage = Column(DECIMAL(5, 2))
    memory_usage = Column(DECIMAL(5, 2))
    disk_usage = Column(DECIMAL(5, 2))
    last_heartbeat = Column(DateTime)
    deleted = Column(Integer, default=0, comment="0:Active, 1:Deleted")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Proxy(Base):
    """代理表"""

    __tablename__ = "proxies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ip = Column(String(50), nullable=False)
    port = Column(Integer, nullable=False)
    protocol = Column(String(10), default="http")
    username = Column(String(100))
    password = Column(String(100))
    country = Column(String(50))
    region = Column(String(50))
    source = Column(String(50))
    score = Column(Integer, default=50)
    response_time = Column(Integer)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    last_check_time = Column(DateTime)
    status = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)


class Venv(Base):
    """Python虚拟环境表"""

    __tablename__ = "venvs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    path = Column(String(255), nullable=False)
    python_version = Column(String(20))
    description = Column(String(255))
    status = Column(Integer, default=1, comment="0禁用 1正常")
    install_status = Column(String(20), default="idle", comment="idle/installing 安装状态")
    install_message = Column(String(500), comment="当前安装进度信息")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    tasks = relationship("Task", back_populates="venv")


class SystemConfig(Base):
    """系统配置表"""

    __tablename__ = "system_configs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False)
    config_value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class NotificationConfig(Base):
    """通知配置表"""

    __tablename__ = "notification_configs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    config = Column(Text, nullable=False)
    is_default = Column(Integer, default=0)
    status = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)


class NodeMetric(Base):
    """节点性能指标历史表"""

    __tablename__ = "node_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    node_id = Column(BigInteger, ForeignKey("nodes.id"), nullable=False, index=True)
    cpu_usage = Column(DECIMAL(5, 2))
    memory_usage = Column(DECIMAL(5, 2))
    disk_usage = Column(DECIMAL(5, 2))
    network_sent = Column(BigInteger, comment="累计发送字节数")
    network_recv = Column(BigInteger, comment="累计接收字节数")
    created_at = Column(DateTime, default=datetime.now, index=True)

    node = relationship("Node", backref="metrics")
