from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.schemas import ProxyResponse, ProxyListResponse, ProxyCreate, ProxyImport
from app.services import proxy_service

router = APIRouter()


class FeedbackRequest(BaseModel):
    success: bool


@router.get("", response_model=ProxyListResponse)
async def get_proxies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    protocol: Optional[str] = None,
    status: Optional[int] = None,
    min_score: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取代理列表"""
    items, total = proxy_service.get_list(db, page, page_size, protocol, status, min_score)
    return ProxyListResponse(
        items=[ProxyResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/get")
async def get_available_proxy(
    protocol: Optional[str] = None,
    count: int = Query(1, ge=1, le=10),
    format: str = Query("json"),
    db: Session = Depends(get_db)
):
    """获取可用代理"""
    proxies = proxy_service.get_available(db, protocol, count)

    if not proxies:
        raise HTTPException(status_code=404, detail="没有可用代理")

    if format == "text":
        result = "\n".join([f"{p.ip}:{p.port}" for p in proxies])
        return PlainTextResponse(content=result)

    if count == 1:
        proxy = proxies[0]
        return {"proxy": f"{proxy.protocol}://{proxy.ip}:{proxy.port}"}

    return {"proxies": [f"{p.protocol}://{p.ip}:{p.port}" for p in proxies]}


@router.post("", response_model=ProxyResponse)
async def add_proxy(data: ProxyCreate, db: Session = Depends(get_db)):
    """添加代理"""
    proxy = proxy_service.create(db, **data.model_dump())
    return ProxyResponse.model_validate(proxy)


@router.post("/import")
async def import_proxies(data: ProxyImport, db: Session = Depends(get_db)):
    """批量导入代理"""
    count = proxy_service.bulk_create(db, data.proxies, data.protocol)
    return {"message": "导入成功", "count": count}


@router.delete("/{proxy_id}")
async def delete_proxy(proxy_id: int, db: Session = Depends(get_db)):
    """删除代理"""
    proxy = proxy_service.get_by_id(db, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")

    proxy_service.delete(db, proxy)
    return {"message": "删除成功"}


@router.post("/{proxy_id}/verify")
async def verify_proxy(proxy_id: int, db: Session = Depends(get_db)):
    """验证代理"""
    proxy = proxy_service.get_by_id(db, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")

    # 使用异步验证，避免阻塞事件循环
    result = await proxy_service.verify_async(proxy)
    proxy_service.update_proxy_after_verify(db, proxy, result)
    db.commit()

    return {"valid": result["valid"], "score": proxy.score}


@router.post("/verify-all")
async def verify_all_proxies(db: Session = Depends(get_db)):
    """批量验证代理"""
    # TODO: 实现异步批量验证
    return {"message": "验证任务已启动"}


@router.post("/{proxy_id}/feedback")
async def proxy_feedback(proxy_id: int, data: FeedbackRequest, db: Session = Depends(get_db)):
    """代理使用反馈"""
    proxy = proxy_service.get_by_id(db, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")

    proxy_service.update_score(db, proxy, data.success)
    return {"message": "反馈已记录", "new_score": proxy.score}


@router.post("/crawl")
async def trigger_crawl(db: Session = Depends(get_db)):
    """手动触发代理采集"""
    if not settings.PROXY_CRAWLING_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="代理源采集默认关闭；请确认来源条款与适用法律后设置 PROXY_CRAWLING_ENABLED=true",
        )
    from app.services.proxy_crawler import proxy_crawler_manager
    import asyncio

    # 异步执行采集
    proxies = await proxy_crawler_manager.crawl_all()

    if not proxies:
        return {"message": "未采集到任何代理", "count": 0}

    # 入库
    count = proxy_service.bulk_create(
        db,
        [f"{p.ip}:{p.port}" for p in proxies],
        protocol="http"
    )

    return {"message": "采集完成", "total": len(proxies), "new": count}
