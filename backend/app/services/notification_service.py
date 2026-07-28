"""
通知服务模块

支持多渠道消息通知：
- 飞书（Feishu）
- 钉钉（DingTalk）
- 企业微信（WeCom）

所有渠道均通过Webhook方式发送。
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from loguru import logger


class NotificationType(str, Enum):
    """通知渠道类型"""

    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECOM = "wecom"


@dataclass
class NotificationResult:
    """通知发送结果"""

    success: bool
    message: str
    raw_response: Optional[Dict[str, Any]] = None


class BaseNotifier(ABC):
    """通知器基类"""

    type: NotificationType

    def __init__(self, webhook_url: str, secret: Optional[str] = None, timeout: int = 10):
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = timeout

    @abstractmethod
    def build_payload(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        """构建请求体，子类必须实现"""
        pass

    async def send(self, title: str, content: str, **kwargs) -> NotificationResult:
        """发送通知"""
        try:
            payload = self.build_payload(title, content, **kwargs)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url, json=payload, headers={"Content-Type": "application/json"}
                )

                result = response.json()

                # 检查各平台的成功标识
                if self._is_success(result):
                    logger.info(f"[{self.type.value}] 通知发送成功: {title}")
                    return NotificationResult(success=True, message="发送成功", raw_response=result)
                else:
                    error_msg = self._get_error_message(result)
                    logger.warning(f"[{self.type.value}] 通知发送失败: {error_msg}")
                    return NotificationResult(success=False, message=error_msg, raw_response=result)
        except Exception as e:
            logger.error(f"[{self.type.value}] 通知发送异常: {e}")
            return NotificationResult(success=False, message=str(e))

    @abstractmethod
    def _is_success(self, response: Dict[str, Any]) -> bool:
        """判断是否成功"""
        pass

    @abstractmethod
    def _get_error_message(self, response: Dict[str, Any]) -> str:
        """获取错误信息"""
        pass


class FeishuNotifier(BaseNotifier):
    """
    飞书通知器

    文档: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
    """

    type = NotificationType.FEISHU

    def build_payload(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": kwargs.get("color", "blue"),
                },
                "elements": [{"tag": "markdown", "content": content}],
            },
        }

        # 处理签名
        if self.secret:
            import base64
            import hashlib
            import hmac
            import time

            timestamp = int(time.time())
            # 官方文档逻辑：string_to_sign = timestamp + "\n" + secret
            string_to_sign = f"{timestamp}\n{self.secret}"

            # 使用 string_to_sign 作为 key，对空字符串进行 hmac-sha256
            hmac_code = hmac.new(
                string_to_sign.encode("utf-8"), "".encode("utf-8"), digestmod=hashlib.sha256
            ).digest()
            sign = base64.b64encode(hmac_code).decode("utf-8")

            payload["timestamp"] = str(timestamp)
            payload["sign"] = sign

        return payload

    def _is_success(self, response: Dict[str, Any]) -> bool:
        return response.get("code") == 0 or response.get("StatusCode") == 0

    def _get_error_message(self, response: Dict[str, Any]) -> str:
        return response.get("msg") or response.get("StatusMessage") or "未知错误"


class DingTalkNotifier(BaseNotifier):
    """
    钉钉通知器

    文档: https://open.dingtalk.com/document/robots/custom-robot-access
    """

    type = NotificationType.DINGTALK

    def build_payload(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        return {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": f"## {title}\n\n{content}"},
            "at": {"isAtAll": kwargs.get("at_all", False)},
        }

    def _is_success(self, response: Dict[str, Any]) -> bool:
        return response.get("errcode") == 0

    def _get_error_message(self, response: Dict[str, Any]) -> str:
        return response.get("errmsg") or "未知错误"


class WeComNotifier(BaseNotifier):
    """
    企业微信通知器

    文档: https://developer.work.weixin.qq.com/document/path/91770
    """

    type = NotificationType.WECOM

    def build_payload(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        return {"msgtype": "markdown", "markdown": {"content": f"## {title}\n\n{content}"}}

    def _is_success(self, response: Dict[str, Any]) -> bool:
        return response.get("errcode") == 0

    def _get_error_message(self, response: Dict[str, Any]) -> str:
        return response.get("errmsg") or "未知错误"


class NotificationService:
    """通知服务"""

    @staticmethod
    def get_notifier(
        notify_type: str, webhook_url: str, secret: Optional[str] = None
    ) -> Optional[BaseNotifier]:
        """根据类型获取通知器实例"""
        notifiers = {
            NotificationType.FEISHU.value: FeishuNotifier,
            NotificationType.DINGTALK.value: DingTalkNotifier,
            NotificationType.WECOM.value: WeComNotifier,
        }

        notifier_class = notifiers.get(notify_type)
        if notifier_class:
            return notifier_class(webhook_url, secret)
        return None

    @staticmethod
    async def send_notification(
        notify_type: str,
        webhook_url: str,
        secret: Optional[str] = None,
        title: str = "",
        content: str = "",
        **kwargs,
    ) -> NotificationResult:
        """发送通知"""
        notifier = NotificationService.get_notifier(notify_type, webhook_url, secret)
        if not notifier:
            return NotificationResult(success=False, message=f"不支持的通知类型: {notify_type}")

        return await notifier.send(title, content, **kwargs)

    @staticmethod
    async def send_task_alert(
        notify_type: str,
        webhook_url: str,
        secret: Optional[str] = None,
        task_name: str = "",
        status: str = "",
        error_message: Optional[str] = None,
    ) -> NotificationResult:
        """发送任务告警通知"""
        title = f"⚠️ 任务告警: {task_name}"

        if status == "failed":
            content = f"**状态**: 执行失败\n\n**错误信息**: {error_message or '未知错误'}"
            color = "red"
        elif status == "timeout":
            content = f"**状态**: 执行超时"
            color = "orange"
        else:
            content = f"**状态**: {status}"
            color = "blue"

        return await NotificationService.send_notification(
            notify_type, webhook_url, secret, title, content, color=color
        )


notification_service = NotificationService()
