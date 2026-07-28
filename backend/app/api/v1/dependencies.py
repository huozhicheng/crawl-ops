"""
任务依赖API

提供任务依赖关系管理功能。
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Task
from app.services.dependency_service import dependency_service

router = APIRouter()


# ===== 请求模型 =====


class DependencyCreate(BaseModel):
    """创建依赖请求"""

    depends_on_task_id: int
    condition_type: str = "success"


class DependencyList(BaseModel):
    """批量设置依赖请求"""

    dependencies: List[DependencyCreate]


# ===== API端点 =====


@router.get("/{task_id}/dependencies")
async def get_task_dependencies(task_id: int, db: Session = Depends(get_db)):
    """获取任务的依赖列表"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    dependencies = dependency_service.get_dependencies(db, task_id)

    # 获取依赖任务的名称
    result = []
    for dep in dependencies:
        dep_task = db.query(Task).filter(Task.id == dep.depends_on_task_id).first()
        result.append(
            {
                "id": dep.id,
                "depends_on_task_id": dep.depends_on_task_id,
                "depends_on_task_name": dep_task.name if dep_task else "未知",
                "condition_type": dep.condition_type,
            }
        )

    return {"dependencies": result}


@router.post("/{task_id}/dependencies")
async def add_task_dependency(task_id: int, data: DependencyCreate, db: Session = Depends(get_db)):
    """添加任务依赖"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    dep_task = db.query(Task).filter(Task.id == data.depends_on_task_id).first()
    if not dep_task:
        raise HTTPException(status_code=400, detail="依赖的任务不存在")

    try:
        dep = dependency_service.add_dependency(
            db, task_id, data.depends_on_task_id, data.condition_type
        )
        return {"message": "添加成功", "id": dep.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{task_id}/dependencies/{depends_on_task_id}")
async def remove_task_dependency(
    task_id: int, depends_on_task_id: int, db: Session = Depends(get_db)
):
    """移除任务依赖"""
    success = dependency_service.remove_dependency(db, task_id, depends_on_task_id)
    if not success:
        raise HTTPException(status_code=404, detail="依赖关系不存在")

    return {"message": "移除成功"}


@router.get("/{task_id}/dependents")
async def get_task_dependents(task_id: int, db: Session = Depends(get_db)):
    """获取依赖此任务的任务列表"""
    dependents = dependency_service.get_dependents(db, task_id)

    result = []
    for dep in dependents:
        task = db.query(Task).filter(Task.id == dep.task_id).first()
        result.append(
            {
                "task_id": dep.task_id,
                "task_name": task.name if task else "未知",
                "condition_type": dep.condition_type,
            }
        )

    return {"dependents": result}


@router.get("/{task_id}/check-dependencies")
async def check_task_dependencies(task_id: int, db: Session = Depends(get_db)):
    """检查任务依赖是否满足"""
    satisfied = dependency_service.check_dependencies_satisfied(db, task_id)
    return {"satisfied": satisfied}


@router.post("/topological-sort")
async def topological_sort_tasks(task_ids: List[int], db: Session = Depends(get_db)):
    """对任务进行拓扑排序"""
    try:
        sorted_ids = dependency_service.topological_sort(db, task_ids)

        # 获取任务名称
        result = []
        for tid in sorted_ids:
            task = db.query(Task).filter(Task.id == tid).first()
            result.append(
                {
                    "id": tid,
                    "name": task.name if task else "未知",
                }
            )

        return {"sorted_tasks": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
