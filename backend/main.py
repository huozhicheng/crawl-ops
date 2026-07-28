"""CrawlOps 后端服务入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1 import api_router
from app.core.config import settings
from app.core.scheduler import init_scheduler, scheduler_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")
    init_scheduler()
    logger.info("调度器已初始化")

    yield

    # 关闭时
    logger.info("应用关闭中...")
    scheduler_manager.shutdown()
    logger.info("调度器已关闭")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="分布式采集任务控制与运维平台 API",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
