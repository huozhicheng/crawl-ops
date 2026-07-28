from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.schemas import ProjectResponse, ProjectListResponse, ProjectCreate, ProjectUpdate
from app.services import project_service
from app.services.node_service import node_service
from app.services.audit_service import audit_service
from app.api.v1.auth import get_current_user
from app.models import User

router = APIRouter()
worker_router = APIRouter()


@router.get("", response_model=ProjectListResponse)
async def get_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取项目列表"""
    items, total = project_service.get_list(db, page, page_size, keyword, type, status)
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建项目"""
    # 检查代码是否存在
    if project_service.get_by_code(db, data.code):
        raise HTTPException(status_code=400, detail="项目代码已存在")

    project = project_service.create(db, user_id=current_user.id, **data.model_dump())

    # Audit Log
    audit_service.log(
        db, user_id=current_user.id, username=current_user.username, action="create_project",
        resource_type="project", resource_id=project.id,
        detail={"name": project.name, "code": project.code},
        ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
    )

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """获取项目详情"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    """更新项目"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project = project_service.update(db, project, **data.model_dump(exclude_unset=True))
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除项目"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_service.delete(db, project)

    # Audit Log
    audit_service.log(
        db, user_id=current_user.id, username=current_user.username, action="delete_project",
        resource_type="project", resource_id=project_id,
        detail={"name": project.name},
        ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
    )

    return {"message": "删除成功"}


@router.post("/{project_id}/sync")
async def sync_project(project_id: int, db: Session = Depends(get_db)):
    """同步项目代码（Git拉取/克隆）"""
    success = project_service.sync_project_code(db, project_id)
    if not success:
        raise HTTPException(status_code=500, detail="同步失败，请检查日志")
    return {"message": "同步成功"}


from fastapi.responses import FileResponse
import tempfile
import shutil
import os
from app.core.config import settings


@worker_router.get("/code/{project_code}/download")
async def download_project_code(
    project_code: str,
    x_node_token: str = Header(..., alias="X-Node-Token"),
    db: Session = Depends(get_db),
):
    """下载项目代码（供 Worker 节点使用）

    Worker 节点在执行 Upload 类型项目时，通过此接口下载项目代码 zip 包。
    Git 类型项目应该使用 git pull 同步，不需要调用此接口。
    """
    if not node_service.get_by_token(db, x_node_token):
        raise HTTPException(status_code=401, detail="无效的节点令牌")
    project = project_service.get_by_code(db, project_code)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_path = os.path.join(settings.PROJECTS_DIR, project_code)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目代码目录不存在")

    # 创建临时 zip 文件
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"{project_code}.zip")

    try:
        # 打包项目目录（排除常见的无用文件）
        shutil.make_archive(
            zip_path.replace('.zip', ''),
            'zip',
            root_dir=settings.PROJECTS_DIR,
            base_dir=project_code
        )

        return FileResponse(
            path=zip_path,
            filename=f"{project_code}.zip",
            media_type="application/zip",
            background=None  # 防止文件在发送前被删除
        )
    except Exception as e:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"打包项目失败: {str(e)}")
