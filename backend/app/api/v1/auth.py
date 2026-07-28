from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
    verify_password,
    revoke_access_token,
    revoke_refresh_token,
    refresh_access_token,
)
from app.models import User
from app.services.audit_service import audit_service

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """获取当前用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    # 支持 "Bearer token" 和直接 "token" 两种格式
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    token_data = verify_access_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="无效或过期的令牌")

    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return user


@router.post("/login", response_model=TokenResponse)
async def login(request_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == request_data.username).first()
    if not user or not verify_password(request_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if user.status != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    access_token = create_access_token(user.id, user.username)
    refresh_token = create_refresh_token(user.id, access_token)

    # Audit Log
    audit_service.log(
        db, user_id=user.id, username=user.username, action="login",
        resource_type="user", resource_id=user.id,
        detail={"message": "Login success"},
        ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=2 * 60 * 60,  # 2小时
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest):
    """刷新Token"""
    result = refresh_access_token(request.refresh_token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的刷新令牌",
        )

    new_access_token, expires_in = result

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=request.refresh_token,  # refresh token不变
        expires_in=expires_in,
    )


@router.post("/logout")
async def logout(request: Request, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """用户登出"""
    if authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = verify_access_token(token)
        if token_data:
            user = db.query(User).filter(User.id == token_data["user_id"]).first()
            if user:
                # Audit Log
                audit_service.log(
                    db, user_id=user.id, username=user.username, action="logout",
                    resource_type="user", resource_id=user.id,
                    detail={"message": "Logout success"},
                    ip=request.headers.get("X-Forwarded-For", request.client.host).split(",")[0]
                )
        revoke_access_token(token)

    return {"message": "登出成功"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "status": current_user.status,
    }
