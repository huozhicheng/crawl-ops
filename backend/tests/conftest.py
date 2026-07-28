"""
测试配置

提供测试用的数据库会话和fixtures。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base


# 使用内存数据库进行测试
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """每个测试函数使用独立的数据库会话"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_user(db):
    """创建管理员用户"""
    from app.models import User
    from app.core.security import get_password_hash

    user = User(
        username="admin",
        password_hash=get_password_hash("test-admin-password"),
        email="admin@example.com",
        status=1
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_project(db, admin_user):
    """创建示例项目"""
    from app.models import Project

    project = Project(
        name="测试项目",
        code="test_project",
        description="测试用项目",
        type="python",
        source_type="upload",
        created_by=admin_user.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@pytest.fixture
def sample_task(db, sample_project):
    """创建示例任务"""
    from app.models import Task

    task = Task(
        name="测试任务",
        project_id=sample_project.id,
        description="测试用任务",
        schedule_type="manual",
        command="python main.py"
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
