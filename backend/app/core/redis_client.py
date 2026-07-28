"""
Redis 连接管理模块

提供 Redis 连接池单例，避免重复创建连接。
"""
import redis

from app.core.config import settings

# Redis 连接池单例
_redis_client = None


def get_redis_client() -> redis.Redis:
    """
    获取 Redis 客户端单例

    使用连接池管理连接，避免每次操作都创建新连接。
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL, decode_responses=True, max_connections=10
        )
    return _redis_client


def publish_stop_signal(execution_id: int, reason: str = "STOP") -> bool:
    """
    发布停止信号

    Args:
        execution_id: 执行记录 ID
        reason: 停止原因 (STOP/TIMEOUT/NODE_OFFLINE)

    Returns:
        True if published successfully
    """
    from loguru import logger

    try:
        r = get_redis_client()
        r.publish(f"stop:execution:{execution_id}", reason)
        logger.info(f"已发布停止信号: execution_id={execution_id}, reason={reason}")
        return True
    except Exception as e:
        logger.error(f"发布停止信号失败: {e}")
        return False


def publish_stop_signals_batch(execution_ids: list, reason: str = "STOP") -> int:
    """
    批量发布停止信号（使用 pipeline 优化）

    Args:
        execution_ids: 执行记录 ID 列表
        reason: 停止原因

    Returns:
        成功发布的数量
    """
    from loguru import logger

    if not execution_ids:
        return 0

    try:
        r = get_redis_client()
        pipe = r.pipeline()
        for exec_id in execution_ids:
            pipe.publish(f"stop:execution:{exec_id}", reason)
        pipe.execute()
        logger.info(f"批量发布停止信号: {len(execution_ids)} 个, reason={reason}")
        return len(execution_ids)
    except Exception as e:
        logger.error(f"批量发布停止信号失败: {e}")
        return 0
