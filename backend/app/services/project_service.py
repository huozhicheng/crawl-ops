import os
import shutil
import subprocess
from typing import Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Project


class ProjectService:
    """项目服务"""

    @staticmethod
    def get_by_id(db: Session, project_id: int) -> Optional[Project]:
        """根据ID获取项目"""
        return db.query(Project).filter(Project.id == project_id).first()

    @staticmethod
    def get_by_code(db: Session, code: str) -> Optional[Project]:
        """根据代码获取项目"""
        return db.query(Project).filter(Project.code == code).first()

    @staticmethod
    def get_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        project_type: Optional[str] = None,
        status: Optional[int] = None,
    ) -> Tuple[list, int]:
        """获取项目列表"""
        query = db.query(Project)

        if keyword:
            query = query.filter(Project.name.like(f"%{keyword}%"))
        if project_type:
            query = query.filter(Project.type == project_type)
        if status is not None:
            query = query.filter(Project.status == status)

        total = query.count()
        items = (
            query.order_by(Project.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        )

        return items, total

    @staticmethod
    def create(db: Session, user_id: int, **kwargs) -> Project:
        """创建项目"""
        project = Project(created_by=user_id, status=1, **kwargs)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def update(db: Session, project: Project, **kwargs) -> Project:
        """更新项目"""
        for key, value in kwargs.items():
            if value is not None and hasattr(project, key):
                setattr(project, key, value)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def delete(db: Session, project: Project) -> None:
        """删除项目"""
        db.delete(project)
        db.commit()

    @staticmethod
    def count(db: Session) -> int:
        """统计项目数量"""
        return db.query(Project).filter(Project.status == 1).count()

    @staticmethod
    def sync_project_code(db: Session, project_id: int) -> bool:
        """同步项目代码"""
        project = ProjectService.get_by_id(db, project_id)
        if not project:
            logger.error(f"Project not found: {project_id}")
            return False

        project_path = os.path.join(settings.PROJECTS_DIR, project.code)

        try:
            if project.source_type == "git":
                if not project.git_url:
                    logger.error(f"Git URL is empty for project: {project.name}")
                    return False

                if os.path.exists(os.path.join(project_path, ".git")):
                    # Git pull
                    logger.info(f"Git pulling project: {project.name}")
                    subprocess.run(
                        ["git", "pull"],
                        cwd=project_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                else:
                    # Git clone
                    if os.path.exists(project_path):
                        # 如果目录存在但不是git仓库，清理掉
                        shutil.rmtree(project_path)

                    logger.info(f"Git cloning project: {project.name}")
                    os.makedirs(project_path, exist_ok=True)
                    subprocess.run(
                        ["git", "clone", project.git_url, "."],
                        cwd=project_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                return True

            elif project.source_type == "upload":
                # 对于上传类型，只需确保目录存在
                if not os.path.exists(project_path):
                    os.makedirs(project_path, exist_ok=True)
                return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Git sync failed for project {project.name}: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Sync failed for project {project.name}: {e}")
            return False

        return True


project_service = ProjectService()
