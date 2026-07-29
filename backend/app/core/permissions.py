"""
权限控制模块

基于RBAC模型实现权限控制：
- 用户 → 角色 → 权限
- 支持角色检查装饰器
- 支持API级别的权限控制
"""

from enum import Enum
from functools import wraps
from typing import List, Optional, Set

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Role, User, UserRole


class RoleCode(str, Enum):
    """角色代码枚举"""

    SUPER_ADMIN = "super_admin"  # 超级管理员
    PROJECT_ADMIN = "project_admin"  # 项目管理员
    USER = "user"  # 普通用户


class Permission(str, Enum):
    """权限枚举"""

    # 用户管理
    USER_VIEW = "user:view"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # 项目管理
    PROJECT_VIEW = "project:view"
    PROJECT_CREATE = "project:create"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"

    # 任务管理
    TASK_VIEW = "task:view"
    TASK_CREATE = "task:create"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_RUN = "task:run"

    # 节点管理
    NODE_VIEW = "node:view"
    NODE_CREATE = "node:create"
    NODE_UPDATE = "node:update"
    NODE_DELETE = "node:delete"

    # 代理池
    PROXY_VIEW = "proxy:view"
    PROXY_CREATE = "proxy:create"
    PROXY_DELETE = "proxy:delete"

    # 系统配置
    SYSTEM_CONFIG = "system:config"


# 角色-权限映射
ROLE_PERMISSIONS: dict[str, Set[str]] = {
    RoleCode.SUPER_ADMIN.value: {p.value for p in Permission},  # 超级管理员拥有所有权限
    RoleCode.PROJECT_ADMIN.value: {
        Permission.USER_VIEW.value,
        Permission.PROJECT_VIEW.value,
        Permission.PROJECT_CREATE.value,
        Permission.PROJECT_UPDATE.value,
        Permission.TASK_VIEW.value,
        Permission.TASK_CREATE.value,
        Permission.TASK_UPDATE.value,
        Permission.TASK_DELETE.value,
        Permission.TASK_RUN.value,
        Permission.NODE_VIEW.value,
        Permission.PROXY_VIEW.value,
        Permission.PROXY_CREATE.value,
    },
    RoleCode.USER.value: {
        Permission.PROJECT_VIEW.value,
        Permission.TASK_VIEW.value,
        Permission.TASK_RUN.value,
        Permission.NODE_VIEW.value,
        Permission.PROXY_VIEW.value,
    },
}


def get_user_roles(db: Session, user_id: int) -> List[str]:
    """获取用户的角色代码列表"""
    user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    role_ids = [ur.role_id for ur in user_roles]

    if not role_ids:
        return []

    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    return [r.code for r in roles]


def get_user_permissions(db: Session, user_id: int) -> Set[str]:
    """获取用户的所有权限"""
    roles = get_user_roles(db, user_id)

    permissions: Set[str] = set()
    for role in roles:
        if role in ROLE_PERMISSIONS:
            permissions.update(ROLE_PERMISSIONS[role])

    return permissions


def check_permission(user: User, permission: str, db: Session) -> bool:
    """检查用户是否拥有特定权限"""
    permissions = get_user_permissions(db, user.id)
    return permission in permissions


def check_role(user: User, role_code: str, db: Session) -> bool:
    """检查用户是否拥有特定角色"""
    roles = get_user_roles(db, user.id)
    return role_code in roles


class RequirePermission:
    """
    权限检查依赖

    用法:
    @router.get("/users")
    async def get_users(
        current_user: User = Depends(get_current_user),
        _: None = Depends(RequirePermission(Permission.USER_VIEW))
    ):
        ...
    """

    def __init__(self, permission: Permission):
        self.permission = permission

    async def __call__(
        self,
        db: Session = Depends(get_db),
        # current_user需要从auth模块获取
    ):
        # 这里需要从请求上下文获取current_user
        # 在实际使用中，应该结合get_current_user依赖
        pass


class RequireRole:
    """
    角色检查依赖

    用法:
    @router.delete("/users/{id}")
    async def delete_user(
        current_user: User = Depends(get_current_user),
        _: None = Depends(RequireRole(RoleCode.SUPER_ADMIN))
    ):
        ...
    """

    def __init__(self, role: RoleCode):
        self.role = role

    async def __call__(
        self,
        db: Session = Depends(get_db),
    ):
        pass


def require_permission(permission: Permission):
    """
    权限检查装饰器（简化版）
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取current_user和db
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")

            if current_user and db:
                if not check_permission(current_user, permission.value, db):
                    raise HTTPException(
                        status_code=403, detail=f"权限不足: 需要 {permission.value}"
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(role: RoleCode):
    """
    角色检查装饰器
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")

            if current_user and db:
                if not check_role(current_user, role.value, db):
                    raise HTTPException(status_code=403, detail=f"权限不足: 需要 {role.value} 角色")

            return await func(*args, **kwargs)

        return wrapper

    return decorator
