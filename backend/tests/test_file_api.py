"""
文件管理API测试
"""

import os
import shutil
import tempfile
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.auth import get_current_user
from app.core.database import Base, get_db
from app.models import Project, User
from main import app

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def override_get_current_user():
    """文件 API 测试不依赖 Redis 中的真实访问令牌。"""
    return User(id=1, username="testuser", password_hash="test", status=1)


app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)


def setup_test_project():
    """创建测试项目和测试文件"""
    db = TestingSessionLocal()
    suffix = uuid4().hex
    test_id = uuid4().int & ((1 << 63) - 1)
    username = f"testuser_{suffix}"
    project_code = f"test_project_{suffix}"

    # 创建测试用户
    user = User(
        id=test_id, username=username, password_hash="test", email=f"{username}@example.com"
    )
    db.add(user)
    db.commit()

    # 创建测试项目
    project = Project(
        id=test_id,
        name="测试项目",
        code=project_code,
        description="测试项目",
        type="python",
        source_type="upload",
        created_by=user.id,
    )
    db.add(project)
    db.commit()

    # 创建测试文件目录
    test_dir = tempfile.mkdtemp()
    project_dir = os.path.join(test_dir, project_code)
    os.makedirs(project_dir, exist_ok=True)

    # 创建测试文件
    with open(os.path.join(project_dir, "main.py"), "w") as f:
        f.write("print('Hello World')")

    with open(os.path.join(project_dir, "README.md"), "w") as f:
        f.write("# Test Project")

    # 创建子目录
    os.makedirs(os.path.join(project_dir, "src"), exist_ok=True)
    with open(os.path.join(project_dir, "src", "utils.py"), "w") as f:
        f.write("def hello():\n    return 'hello'")

    project_id = project.id
    db.close()
    return project_id, test_dir


def test_list_files():
    """测试列出文件"""
    project_id, test_dir = setup_test_project()

    # 临时修改PROJECTS_DIR
    from app.core import config

    original_dir = config.settings.PROJECTS_DIR
    config.settings.PROJECTS_DIR = test_dir

    try:
        response = client.get(f"/api/v1/files/project/{project_id}/list")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) > 0

        # 检查文件列表
        file_names = [f["name"] for f in data["files"]]
        assert "main.py" in file_names
        assert "README.md" in file_names
        assert "src" in file_names

    finally:
        config.settings.PROJECTS_DIR = original_dir
        shutil.rmtree(test_dir)


def test_view_file():
    """测试预览文件"""
    project_id, test_dir = setup_test_project()

    from app.core import config

    original_dir = config.settings.PROJECTS_DIR
    config.settings.PROJECTS_DIR = test_dir

    try:
        response = client.get(
            f"/api/v1/files/project/{project_id}/view", params={"path": "main.py"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "Hello World" in data["content"]

    finally:
        config.settings.PROJECTS_DIR = original_dir
        shutil.rmtree(test_dir)


def test_search_files():
    """测试搜索文件"""
    project_id, test_dir = setup_test_project()

    from app.core import config

    original_dir = config.settings.PROJECTS_DIR
    config.settings.PROJECTS_DIR = test_dir

    try:
        response = client.get(
            f"/api/v1/files/project/{project_id}/search", params={"keyword": "main"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0
        assert data["results"][0]["name"] == "main.py"

    finally:
        config.settings.PROJECTS_DIR = original_dir
        shutil.rmtree(test_dir)


def test_path_traversal_protection():
    """测试路径穿越攻击防护"""
    project_id, test_dir = setup_test_project()

    from app.core import config

    original_dir = config.settings.PROJECTS_DIR
    config.settings.PROJECTS_DIR = test_dir

    try:
        # 尝试访问上级目录
        response = client.get(f"/api/v1/files/project/{project_id}/list", params={"path": "../"})
        assert response.status_code == 400
        assert "非法路径" in response.json()["detail"]

    finally:
        config.settings.PROJECTS_DIR = original_dir
        shutil.rmtree(test_dir)


def test_upload_rejects_path_in_filename():
    """上传文件名不能携带路径，以免写到项目目录之外。"""
    project_id, test_dir = setup_test_project()

    from app.core import config

    original_dir = config.settings.PROJECTS_DIR
    config.settings.PROJECTS_DIR = test_dir

    try:
        response = client.post(
            f"/api/v1/files/project/{project_id}/upload-file",
            files={"file": ("../outside.py", b"print('unsafe')", "text/x-python")},
        )
        assert response.status_code == 400
        assert "文件名不能包含路径" in response.json()["detail"]
        assert not os.path.exists(os.path.join(test_dir, "outside.py"))
    finally:
        config.settings.PROJECTS_DIR = original_dir
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    print("运行文件管理API测试...")

    print("\n1. 测试列出文件...")
    test_list_files()
    print("✓ 通过")

    print("\n2. 测试预览文件...")
    test_view_file()
    print("✓ 通过")

    print("\n3. 测试搜索文件...")
    test_search_files()
    print("✓ 通过")

    print("\n4. 测试路径穿越防护...")
    test_path_traversal_protection()
    print("✓ 通过")

    print("\n✅ 所有测试通过！")
