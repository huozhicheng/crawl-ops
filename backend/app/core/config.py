from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "CrawlOps"
    API_V1_STR: str = "/api/v1"

    # Token 配置
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 数据库配置
    # 运行时由环境变量提供。公开仓库绝不包含可用的连接凭据。
    DATABASE_URL: Optional[str] = None

    # Redis配置
    REDIS_URL: Optional[str] = None

    # Worker 首次注册使用的共享令牌。请只通过受信任的私有网络分发。
    WORKER_REGISTRATION_TOKEN: Optional[str] = None

    # 外部免费代理源默认关闭，需在确认来源条款与业务合规后显式开启。
    PROXY_CRAWLING_ENABLED: bool = False

    # 路径配置
    DATA_DIR: str = "/app/data"
    PROJECTS_DIR: str = "/app/data/projects"
    LOGS_DIR: str = "/app/data/logs"
    VENVS_DIR: str = "/app/data/venvs"

    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # 任务调度配置
    PENDING_TIMEOUT_MINUTES: int = 5  # pending 状态超时时间（分钟）
    CALLBACK_MAX_RETRIES: int = 3  # 回调最大重试次数
    CALLBACK_BASE_DELAY: float = 2.0  # 回调重试基础延迟（秒）
    CALLBACK_MAX_AGE_HOURS: int = 24  # 失败回调文件最大保留时间（小时）
    CALLBACK_MAX_RETRY_COUNT: int = 10  # 失败回调最大重试次数

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
