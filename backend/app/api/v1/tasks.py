from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.schemas import TaskResponse, TaskListResponse, TaskCreate, TaskUpdate
from app.services import task_service
from app.services.audit_service import audit_service
from app.api.v1.auth import get_current_user
from app.models import User

router = APIRouter()


@router.get("", response_model=TaskListResponse)
async def get_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[int] = None,
    schedule_type: Optional[str] = None,
    status: Optional[int] = None,
    name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    items, total = task_service.get_list(db, page, page_size, project_id, schedule_type, status, name)
    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=TaskResponse)
async def create_task(
    data: TaskCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建任务"""
    task = task_service.create(db, user_id=current_user.id, **data.model_dump())

    # Audit Log
    audit_service.log(
        db, user_id=current_user.id, username=current_user.username, action="create_task",
        resource_type="task", resource_id=task.id,
        detail={"name": task.name, "project_id": task.project_id},
        ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
    )

    return TaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """获取任务详情"""
    task = task_service.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskResponse.model_validate(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新任务"""
    task = task_service.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = task_service.update(db, task, **data.model_dump(exclude_unset=True))

    # Audit Log
    audit_service.log(
        db, user_id=current_user.id, username=current_user.username, action="update_task",
        resource_type="task", resource_id=task_id,
        detail={"name": task.name},
        ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
    )
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除任务"""
    task = task_service.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task_service.delete(db, task)

    # Audit Log
    audit_service.log(
        db, user_id=current_user.id, username=current_user.username, action="delete_task",
        resource_type="task", resource_id=task_id,
        detail={"name": task.name},
        ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
    )

    return {"message": "删除成功"}


@router.put("/{task_id}/status")
async def update_task_status(
    task_id: int,
    request: Request,
    status: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """启用/禁用任务"""
    task = task_service.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = task_service.update(db, task, status=status)

    # Audit Log
    audit_service.log(
        db, user_id=current_user.id, username=current_user.username, action="update_task_status",
        resource_type="task", resource_id=task_id,
        detail={"status": status},
        ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
    )
    return {"message": "状态更新成功"}


@router.post("/{task_id}/run")
async def run_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动执行任务"""
    task = task_service.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    execution = task_service.run(db, task, trigger_type="manual")

    # Audit Log
    audit_service.log(
        db, user_id=current_user.id, username=current_user.username, action="run_task",
        resource_type="execution", resource_id=execution.id,
        detail={"task_id": task.id, "name": task.name},
        ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
    )

    return {"message": "任务已触发", "execution_id": execution.id}
