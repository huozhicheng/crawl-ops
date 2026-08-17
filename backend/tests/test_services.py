"""
用户服务单元测试
"""

import pytest


class TestUserService:
    """用户服务测试"""

    def test_create_user(self, db):
        """测试创建用户"""
        from app.services.user_service import user_service

        user = user_service.create(
            db, username="testuser", password="testpass123", email="test@example.com"
        )

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.status == 1

    def test_authenticate_user(self, db, admin_user):
        """测试用户认证"""
        from app.services.user_service import user_service

        # 正确密码
        result = user_service.authenticate(db, "admin", "test-admin-password")
        assert result is not None
        assert result.username == "admin"

        # 错误密码
        result = user_service.authenticate(db, "admin", "wrongpassword")
        assert result is None

    def test_get_user_by_id(self, db, admin_user):
        """测试通过ID获取用户"""
        from app.services.user_service import user_service

        user = user_service.get_by_id(db, admin_user.id)
        assert user is not None
        assert user.username == "admin"

        # 不存在的用户
        user = user_service.get_by_id(db, 99999)
        assert user is None

    def test_update_password(self, db, admin_user):
        """测试修改密码"""
        from app.services.user_service import user_service

        updated_user = user_service.change_password(db, admin_user, "new-test-password")
        assert updated_user.id == admin_user.id

        # 使用新密码验证
        result = user_service.authenticate(db, "admin", "new-test-password")
        assert result is not None


class TestPasswordHashing:
    """验证升级后的 bcrypt 行为。"""

    def test_hash_and_verify_password(self):
        from app.core.security import get_password_hash, verify_password

        password_hash = get_password_hash("test-password")

        assert password_hash.startswith("$2")
        assert verify_password("test-password", password_hash)
        assert not verify_password("wrong-password", password_hash)

    def test_rejects_passwords_longer_than_bcrypt_limit(self):
        from app.core.security import get_password_hash, verify_password

        password = "a" * 73

        with pytest.raises(ValueError, match="72"):
            get_password_hash(password)
        assert not verify_password(password, "$2b$12$invalid")


class TestProjectService:
    """项目服务测试"""

    def test_create_project(self, db, admin_user):
        """测试创建项目"""
        from app.services.project_service import project_service

        project = project_service.create(
            db,
            user_id=admin_user.id,
            name="新项目",
            code="new_project",
            description="测试项目",
            type="python",
            source_type="upload",
        )

        assert project.id is not None
        assert project.name == "新项目"
        assert project.code == "new_project"

    def test_get_project_list(self, db, sample_project):
        """测试获取项目列表"""
        from app.services.project_service import project_service

        projects, total = project_service.get_list(db)

        assert total >= 1
        assert any(p.id == sample_project.id for p in projects)


class TestTaskService:
    """任务服务测试"""

    def test_create_task(self, db, sample_project):
        """测试创建任务"""
        from app.services.task_service import task_service

        task = task_service.create(
            db,
            user_id=sample_project.created_by,
            name="新任务",
            project_id=sample_project.id,
            schedule_type="manual",
            command="python run.py",
        )

        assert task.id is not None
        assert task.name == "新任务"
        assert task.project_id == sample_project.id

    def test_execute_task(self, db, sample_task, monkeypatch):
        """测试执行任务"""
        from app.services.task_service import task_service

        class FakeRedis:
            def lpush(self, *_args):
                return 1

        monkeypatch.setattr("redis.from_url", lambda *_args, **_kwargs: FakeRedis())

        execution = task_service.run(db, sample_task)

        assert execution.id is not None
        assert execution.task_id == sample_task.id
        assert execution.trigger_type == "manual"
        assert execution.status == "pending"
