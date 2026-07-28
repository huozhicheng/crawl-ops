from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.schemas import UserResponse, UserListResponse, UserCreate, UserUpdate
from app.services import user_service


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


router = APIRouter()


@router.get("", response_model=UserListResponse)
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取用户列表"""
    items, total = user_service.get_list(db, page, page_size, keyword, status)
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=UserResponse)
async def create_user(data: UserCreate, db: Session = Depends(get_db)):
    """创建用户"""
    # 检查用户名是否存在
    if user_service.get_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = user_service.create(db, data.username, data.password, data.email)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """获取用户详情"""
    user = user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    """更新用户"""
    user = user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user = user_service.update(db, user, **data.model_dump(exclude_unset=True))
    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """删除用户"""
    user = user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user_service.delete(db, user)
    return {"message": "删除成功"}


@router.put("/{user_id}/password")
async def change_password(
    user_id: int,
    data: ChangePasswordRequest,
    db: Session = Depends(get_db)
):
    """修改密码"""
    user = user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 验证旧密码
    if not user_service.verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    # 更新密码
    user_service.change_password(db, user, data.new_password)
    return {"message": "密码修改成功"}
