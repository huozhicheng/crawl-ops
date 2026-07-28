from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models import User


class UserService:
    """用户服务"""

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
    ) -> Tuple[list, int]:
        """获取用户列表"""
        query = db.query(User)

        if keyword:
            query = query.filter(User.username.like(f"%{keyword}%"))
        if status is not None:
            query = query.filter(User.status == status)

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    @staticmethod
    def create(db: Session, username: str, password: str, email: Optional[str] = None) -> User:
        """创建用户"""
        user = User(
            username=username, password_hash=get_password_hash(password), email=email, status=1
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update(db: Session, user: User, **kwargs) -> User:
        """更新用户"""
        for key, value in kwargs.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete(db: Session, user: User) -> None:
        """删除用户"""
        db.delete(user)
        db.commit()

    @staticmethod
    def change_password(db: Session, user: User, new_password: str) -> User:
        """修改密码"""
        user.password_hash = get_password_hash(new_password)
        db.commit()
        return user

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return verify_password(plain_password, hashed_password)

    @staticmethod
    def authenticate(db: Session, username: str, password: str) -> Optional[User]:
        """验证用户"""
        user = UserService.get_by_username(db, username)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user


user_service = UserService()
