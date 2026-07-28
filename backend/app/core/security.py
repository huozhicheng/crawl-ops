import json
import secrets
from typing import Optional

import redis
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token有效期（秒）
ACCESS_TOKEN_EXPIRE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_TOKEN_EXPIRE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def get_redis_client() -> redis.Redis:
    """按需创建 Redis 客户端，避免导入阶段读取缺失的运行时配置。"""
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL 未配置，无法执行认证操作")
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def generate_token() -> str:
    """生成随机Token"""
    return secrets.token_urlsafe(32)


def create_access_token(user_id: int, username: str) -> str:
    """创建访问令牌"""
    token = generate_token()
    token_data = json.dumps({"user_id": user_id, "username": username})
    get_redis_client().setex(f"token:{token}", ACCESS_TOKEN_EXPIRE, token_data)
    return token


def create_refresh_token(user_id: int, access_token: str) -> str:
    """创建刷新令牌"""
    token = generate_token()
    token_data = json.dumps({"user_id": user_id, "access_token": access_token})
    get_redis_client().setex(f"refresh:{token}", REFRESH_TOKEN_EXPIRE, token_data)
    return token


def verify_access_token(token: str) -> Optional[dict]:
    """验证访问令牌"""
    token_data = get_redis_client().get(f"token:{token}")
    if token_data:
        return json.loads(token_data)
    return None


def verify_refresh_token(token: str) -> Optional[dict]:
    """验证刷新令牌"""
    token_data = get_redis_client().get(f"refresh:{token}")
    if token_data:
        return json.loads(token_data)
    return None


def revoke_access_token(token: str) -> None:
    """撤销访问令牌"""
    get_redis_client().delete(f"token:{token}")


def revoke_refresh_token(token: str) -> None:
    """撤销刷新令牌"""
    get_redis_client().delete(f"refresh:{token}")


def revoke_all_user_tokens(user_id: int) -> None:
    """撤销用户所有令牌（用于强制登出）"""
    # 扫描并删除所有该用户的token
    redis_client = get_redis_client()
    for key in redis_client.scan_iter("token:*"):
        token_data = redis_client.get(key)
        if token_data:
            data = json.loads(token_data)
            if data.get("user_id") == user_id:
                redis_client.delete(key)

    for key in redis_client.scan_iter("refresh:*"):
        token_data = redis_client.get(key)
        if token_data:
            data = json.loads(token_data)
            if data.get("user_id") == user_id:
                redis_client.delete(key)


def refresh_access_token(refresh_token: str) -> Optional[tuple]:
    """使用刷新令牌获取新的访问令牌"""
    refresh_data = verify_refresh_token(refresh_token)
    if not refresh_data:
        return None

    user_id = refresh_data.get("user_id")
    old_access_token = refresh_data.get("access_token")

    # 撤销旧的access token
    if old_access_token:
        revoke_access_token(old_access_token)

    # 从Redis获取用户名（需要从数据库查询，这里简化处理）
    # 实际应该通过user_id查数据库获取username
    new_access_token = generate_token()
    token_data = json.dumps({"user_id": user_id, "username": refresh_data.get("username", "user")})
    redis_client = get_redis_client()
    redis_client.setex(f"token:{new_access_token}", ACCESS_TOKEN_EXPIRE, token_data)

    # 更新refresh token中的access_token引用
    refresh_data["access_token"] = new_access_token
    redis_client.setex(f"refresh:{refresh_token}", REFRESH_TOKEN_EXPIRE, json.dumps(refresh_data))

    return new_access_token, ACCESS_TOKEN_EXPIRE


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)
