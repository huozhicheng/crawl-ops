"""
角色管理API

提供角色CRUD和用户角色分配功能。
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import ROLE_PERMISSIONS, RoleCode
from app.models import Role, UserRole

router = APIRouter()


# ===== 请求/响应模型 =====


class RoleCreate(BaseModel):
    """创建角色请求"""

    name: str
    code: str
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    """更新角色请求"""

    name: Optional[str] = None
    description: Optional[str] = None


class AssignRoleRequest(BaseModel):
    """分配角色请求"""

    user_id: int
    role_ids: List[int]


# ===== API端点 =====


@router.get("")
async def get_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取角色列表"""
    query = db.query(Role)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "code": r.code,
                "description": r.description,
                "permissions": list(ROLE_PERMISSIONS.get(r.code, set())),
            }
            for r in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
async def create_role(data: RoleCreate, db: Session = Depends(get_db)):
    """创建角色"""
    # 检查code是否已存在
    existing = db.query(Role).filter(Role.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="角色代码已存在")

    role = Role(name=data.name, code=data.code, description=data.description)
    db.add(role)
    db.commit()
    db.refresh(role)

    return {"message": "创建成功", "id": role.id}


@router.get("/{role_id}")
async def get_role(role_id: int, db: Session = Depends(get_db)):
    """获取角色详情"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "description": role.description,
        "permissions": list(ROLE_PERMISSIONS.get(role.code, set())),
    }


@router.put("/{role_id}")
async def update_role(role_id: int, data: RoleUpdate, db: Session = Depends(get_db)):
    """更新角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if data.name:
        role.name = data.name
    if data.description is not None:
        role.description = data.description

    db.commit()
    return {"message": "更新成功"}


@router.delete("/{role_id}")
async def delete_role(role_id: int, db: Session = Depends(get_db)):
    """删除角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 不允许删除系统内置角色
    if role.code in [r.value for r in RoleCode]:
        raise HTTPException(status_code=400, detail="不能删除系统内置角色")

    # 删除用户角色关联
    db.query(UserRole).filter(UserRole.role_id == role_id).delete()
    db.delete(role)
    db.commit()

    return {"message": "删除成功"}


@router.post("/assign")
async def assign_roles(data: AssignRoleRequest, db: Session = Depends(get_db)):
    """为用户分配角色"""
    # 删除用户现有角色
    db.query(UserRole).filter(UserRole.user_id == data.user_id).delete()

    # 添加新角色
    for role_id in data.role_ids:
        user_role = UserRole(user_id=data.user_id, role_id=role_id)
        db.add(user_role)

    db.commit()
    return {"message": "分配成功"}


@router.get("/user/{user_id}")
async def get_user_roles(user_id: int, db: Session = Depends(get_db)):
    """获取用户的角色"""
    user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    role_ids = [ur.role_id for ur in user_roles]

    if not role_ids:
        return {"roles": []}

    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()

    return {
        "roles": [
            {
                "id": r.id,
                "name": r.name,
                "code": r.code,
            }
            for r in roles
        ]
    }


@router.get("/permissions/all")
async def get_all_permissions():
    """获取所有权限列表"""
    from app.core.permissions import Permission

    return {"permissions": [{"value": p.value, "label": p.value} for p in Permission]}
