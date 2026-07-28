from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
import random

from app.models import Proxy


class ProxyService:
    """代理池服务"""

    @staticmethod
    def get_by_id(db: Session, proxy_id: int) -> Optional[Proxy]:
        """根据ID获取代理"""
        return db.query(Proxy).filter(Proxy.id == proxy_id).first()

    @staticmethod
    def get_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        protocol: Optional[str] = None,
        status: Optional[int] = None,
        min_score: Optional[int] = None
    ) -> Tuple[list, int]:
        """获取代理列表"""
        query = db.query(Proxy)

        if protocol:
            query = query.filter(Proxy.protocol == protocol)
        if status is not None:
            query = query.filter(Proxy.status == status)
        if min_score is not None:
            query = query.filter(Proxy.score >= min_score)

        total = query.count()
        items = query.order_by(Proxy.score.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    @staticmethod
    def get_available(
        db: Session,
        protocol: Optional[str] = None,
        count: int = 1
    ) -> list:
        """获取可用代理"""
        query = db.query(Proxy).filter(
            and_(Proxy.status == 1, Proxy.score >= 30)
        )

        if protocol:
            query = query.filter(Proxy.protocol == protocol)

        proxies = query.order_by(Proxy.score.desc()).limit(count * 3).all()

        if len(proxies) > count:
            proxies = random.sample(proxies, count)

        return proxies

    @staticmethod
    def create(db: Session, **kwargs) -> Proxy:
        """创建代理"""
        proxy = Proxy(score=50, status=1, **kwargs)
        db.add(proxy)
        db.commit()
        db.refresh(proxy)
        return proxy

    @staticmethod
    def bulk_create(db: Session, proxies: list, protocol: str = "http") -> int:
        """批量创建代理"""
        count = 0
        for proxy_str in proxies:
            try:
                parts = proxy_str.strip().split(":")
                if len(parts) >= 2:
                    ip, port = parts[0], int(parts[1])
                    # 检查是否存在
                    exists = db.query(Proxy).filter(
                        and_(Proxy.ip == ip, Proxy.port == port)
                    ).first()
                    if not exists:
                        proxy = Proxy(ip=ip, port=port, protocol=protocol, score=50, status=1)
                        db.add(proxy)
                        count += 1
            except:
                continue
        db.commit()
        return count

    @staticmethod
    def delete(db: Session, proxy: Proxy) -> None:
        """删除代理"""
        db.delete(proxy)
        db.commit()

    @staticmethod
    def update_score(db: Session, proxy: Proxy, success: bool) -> Proxy:
        """更新代理评分"""
        if success:
            proxy.score = min(100, proxy.score + 5)
            proxy.success_count += 1
        else:
            proxy.score = max(0, proxy.score - 10)
            proxy.fail_count += 1

            # 评分过低则标记为不可用
            if proxy.score <= 0:
                proxy.status = 0

        db.commit()
        db.refresh(proxy)
        return proxy

    @staticmethod
    def verify(db: Session, proxy: Proxy) -> bool:
        """验证代理可用性（同步版本，可能阻塞）"""
        import httpx

        proxy_url = f"{proxy.protocol}://{proxy.ip}:{proxy.port}"
        try:
            with httpx.Client(proxies={"all://": proxy_url}, timeout=10) as client:
                start = datetime.now()
                response = client.get("http://httpbin.org/ip")
                end = datetime.now()

                if response.status_code == 200:
                    proxy.response_time = int((end - start).total_seconds() * 1000)
                    proxy.last_check_time = datetime.now()
                    proxy.score = min(100, proxy.score + 10)
                    proxy.status = 1
                    db.commit()
                    return True
        except:
            pass

        proxy.score = max(0, proxy.score - 20)
        proxy.last_check_time = datetime.now()
        if proxy.score <= 0:
            proxy.status = 0
        db.commit()
        return False

    @staticmethod
    async def verify_async(proxy: Proxy) -> dict:
        """异步验证代理可用性（不阻塞事件循环）"""
        import httpx

        proxy_url = f"{proxy.protocol}://{proxy.ip}:{proxy.port}"
        try:
            async with httpx.AsyncClient(proxies={"all://": proxy_url}, timeout=10) as client:
                start = datetime.now()
                response = await client.get("http://httpbin.org/ip")
                end = datetime.now()

                if response.status_code == 200:
                    return {
                        "valid": True,
                        "response_time": int((end - start).total_seconds() * 1000)
                    }
        except:
            pass

        return {"valid": False, "response_time": None}

    @staticmethod
    def update_proxy_after_verify(db: Session, proxy: Proxy, result: dict) -> None:
        """根据验证结果更新代理状态"""
        if result["valid"]:
            proxy.response_time = result["response_time"]
            proxy.last_check_time = datetime.now()
            proxy.score = min(100, proxy.score + 10)
            proxy.status = 1
        else:
            proxy.score = max(0, proxy.score - 20)
            proxy.last_check_time = datetime.now()
            if proxy.score <= 0:
                proxy.status = 0
        # 注意：不在这里 commit，由调用方统一 commit

    @staticmethod
    def count_available(db: Session) -> int:
        """统计可用代理数量"""
        return db.query(Proxy).filter(
            and_(Proxy.status == 1, Proxy.score >= 30)
        ).count()


proxy_service = ProxyService()
