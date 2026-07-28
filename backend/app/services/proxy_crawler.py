"""
代理采集器模块

从多个免费代理源采集代理IP，支持异步采集和验证。

默认采集频率：
- 采集任务：每10分钟执行一次
- 验证任务：每5分钟执行一次
"""
import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

import httpx
from loguru import logger


@dataclass
class ProxyItem:
    """代理项数据类"""

    ip: str
    port: int
    protocol: str = "http"
    source: str = ""


class BaseProxyCrawler(ABC):
    """代理采集器基类"""

    name: str = "base"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    @abstractmethod
    async def crawl(self) -> List[ProxyItem]:
        """采集代理，子类必须实现"""
        pass

    async def fetch(self, url: str) -> Optional[str]:
        """通用HTTP请求方法"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.text
        except Exception as e:
            logger.warning(f"[{self.name}] 请求失败: {url}, 错误: {e}")
        return None


class IP66Crawler(BaseProxyCrawler):
    """66免费代理采集器"""

    name = "66ip"
    urls = [
        "http://www.66ip.cn/mo.php?sxb=&tqsl=100&port=&export=&ktip=&sxa=&submit=%CC%E1++%C8%A1&textarea=",
    ]

    async def crawl(self) -> List[ProxyItem]:
        proxies = []
        for url in self.urls:
            content = await self.fetch(url)
            if content:
                pattern = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)"
                matches = re.findall(pattern, content)
                for ip, port in matches:
                    proxies.append(ProxyItem(ip=ip, port=int(port), source=self.name))
        logger.info(f"[{self.name}] 采集到 {len(proxies)} 个代理")
        return proxies


class KuaiDaiLiCrawler(BaseProxyCrawler):
    """快代理采集器"""

    name = "kuaidaili"
    urls = [
        "https://www.kuaidaili.com/free/inha/",
        "https://www.kuaidaili.com/free/intr/",
    ]

    async def crawl(self) -> List[ProxyItem]:
        proxies = []
        for url in self.urls:
            content = await self.fetch(url)
            if content:
                # 解析HTML中的代理
                ip_pattern = r'<td data-title="IP">(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td>'
                port_pattern = r'<td data-title="PORT">(\d+)</td>'
                ips = re.findall(ip_pattern, content)
                ports = re.findall(port_pattern, content)
                for ip, port in zip(ips, ports):
                    proxies.append(ProxyItem(ip=ip, port=int(port), source=self.name))
            # 避免请求过快被封
            await asyncio.sleep(1)
        logger.info(f"[{self.name}] 采集到 {len(proxies)} 个代理")
        return proxies


class IP3366Crawler(BaseProxyCrawler):
    """云代理采集器"""

    name = "ip3366"
    urls = [
        "http://www.ip3366.net/free/?stype=1",
        "http://www.ip3366.net/free/?stype=2",
    ]

    async def crawl(self) -> List[ProxyItem]:
        proxies = []
        for url in self.urls:
            content = await self.fetch(url)
            if content:
                pattern = r"<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td>\s*<td>(\d+)</td>"
                matches = re.findall(pattern, content)
                for ip, port in matches:
                    proxies.append(ProxyItem(ip=ip, port=int(port), source=self.name))
            await asyncio.sleep(1)
        logger.info(f"[{self.name}] 采集到 {len(proxies)} 个代理")
        return proxies


class ProxyCrawlerManager:
    """代理采集管理器"""

    def __init__(self):
        self.crawlers: List[BaseProxyCrawler] = [
            IP66Crawler(),
            KuaiDaiLiCrawler(),
            IP3366Crawler(),
        ]

    async def crawl_all(self) -> List[ProxyItem]:
        """执行所有采集器"""
        all_proxies: List[ProxyItem] = []

        # 并发执行所有采集器
        tasks = [crawler.crawl() for crawler in self.crawlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_proxies.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"采集器异常: {result}")

        # 去重
        seen = set()
        unique_proxies = []
        for proxy in all_proxies:
            key = f"{proxy.ip}:{proxy.port}"
            if key not in seen:
                seen.add(key)
                unique_proxies.append(proxy)

        logger.info(f"采集完成，共 {len(unique_proxies)} 个唯一代理")
        return unique_proxies


# 单例
proxy_crawler_manager = ProxyCrawlerManager()
