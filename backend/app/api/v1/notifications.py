"""
通知配置API

提供通知渠道配置CRUD和测试发送功能。
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json

from app.core.database import get_db
from app.models import NotificationConfig
from app.services.notification_service import notification_service, NotificationType

router = APIRouter()


# ===== 请求/响应模型 =====

class NotificationConfigCreate(BaseModel):
    """创建通知配置"""
    name: str
    type: str  # feishu / dingtalk / wecom
    webhook_url: str
    secret: Optional[str] = None
    is_default: bool = False


class NotificationConfigUpdate(BaseModel):
    """更新通知配置"""
    name: Optional[str] = None
    webhook_url: Optional[str] = None
    secret: Optional[str] = None
    is_default: Optional[bool] = None
    status: Optional[int] = None


class NotificationTestRequest(BaseModel):
    """测试通知请求"""
    type: str
    webhook_url: str
    secret: Optional[str] = None
    title: str = "测试通知"
    content: str = "这是一条测试消息，如果您收到了，说明配置正确。"


# ===== 数据库操作 =====

def get_notification_configs(db: Session) -> List[dict]:
    """获取所有通知配置"""
    configs = db.query(NotificationConfig).all()

    result = []
    for config in configs:
        try:
            config_data = json.loads(config.config)
            data = {
                "id": config.id,
                "name": config.name,
                "type": config.type,
                "is_default": bool(config.is_default),
                "status": config.status,
                "created_at": config.created_at,
                "webhook_url": config_data.get("webhook_url"),
                # 通知密钥只保存在服务端，列表接口永不回传明文。
                "has_secret": bool(config_data.get("secret")),
            }
            result.append(data)
        except:
            continue

    return result


def create_notification_config(
    db: Session,
    name: str,
    notify_type: str,
    webhook_url: str,
    secret: Optional[str] = None,
    is_default: bool = False
) -> NotificationConfig:
    """创建通知配置"""

    config_json = json.dumps({
        "webhook_url": webhook_url,
        "secret": secret
    })

    config = NotificationConfig(
        name=name,
        type=notify_type,
        config=config_json,
        is_default=1 if is_default else 0,
        status=1
    )
    db.add(config)
    db.commit()
    db.refresh(config)

    return config


def delete_notification_config(db: Session, config_id: int) -> bool:
    """删除通知配置"""
    config = db.query(NotificationConfig).filter(NotificationConfig.id == config_id).first()
    if config:
        db.delete(config)
        db.commit()
        return True
    return False


def update_notification_config(
    db: Session,
    config_id: int,
    data: NotificationConfigUpdate
) -> Optional[NotificationConfig]:
    """更新通知配置"""

    config = db.query(NotificationConfig).filter(NotificationConfig.id == config_id).first()
    if not config:
        return None

    try:
        current_config_data = json.loads(config.config)
    except:
        current_config_data = {}

    # 更新字段
    if data.name is not None:
        config.name = data.name
    if data.is_default is not None:
        config.is_default = 1 if data.is_default else 0
    if data.status is not None:
        config.status = data.status

    # 更新config JSON
    if data.webhook_url is not None:
        current_config_data["webhook_url"] = data.webhook_url
    # 空字符串表示“保持不变”；只有提供非空新值才替换已存储的密钥。
    if data.secret:
        current_config_data["secret"] = data.secret

    config.config = json.dumps(current_config_data)

    db.commit()
    db.refresh(config)
    return config


# ===== API端点 =====

@router.get("")
async def get_configs(db: Session = Depends(get_db)):
    """获取所有通知配置"""
    configs = get_notification_configs(db)
    return {"items": configs, "total": len(configs)}


@router.post("")
async def create_config(data: NotificationConfigCreate, db: Session = Depends(get_db)):
    """创建通知配置"""
    # 验证类型
    valid_types = [t.value for t in NotificationType]
    if data.type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的通知类型，支持: {', '.join(valid_types)}"
        )

    config = create_notification_config(
        db,
        name=data.name,
        notify_type=data.type,
        webhook_url=data.webhook_url,
        secret=data.secret,
        is_default=data.is_default
    )

    return {"message": "创建成功", "id": config.id}


@router.delete("/{config_id}")
async def delete_config(config_id: int, db: Session = Depends(get_db)):
    """删除通知配置"""
    success = delete_notification_config(db, config_id)
    if not success:
        raise HTTPException(status_code=404, detail="配置不存在")

    return {"message": "删除成功"}


@router.put("/{config_id}")
async def update_config(
    config_id: int,
    data: NotificationConfigUpdate,
    db: Session = Depends(get_db)
):
    """更新通知配置"""
    config = update_notification_config(db, config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    return {"message": "更新成功"}


@router.post("/test")
async def test_notification(data: NotificationTestRequest):
    """测试通知发送"""
    # 验证类型
    valid_types = [t.value for t in NotificationType]
    if data.type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的通知类型，支持: {', '.join(valid_types)}"
        )

    result = await notification_service.send_notification(
        notify_type=data.type,
        webhook_url=data.webhook_url,
        secret=data.secret,
        title=data.title,
        content=data.content
    )

    if result.success:
        return {"message": "发送成功", "result": result.raw_response}
    else:
        raise HTTPException(status_code=500, detail=result.message)


@router.post("/{config_id}/test")
async def test_saved_notification_config(
    config_id: int,
    title: str = "测试通知",
    content: str = "这是一条测试消息，如果您收到了，说明配置正确。",
    db: Session = Depends(get_db),
):
    """使用服务端保存的密钥测试通知，避免将密钥重新发送给浏览器。"""
    config = db.query(NotificationConfig).filter(NotificationConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    try:
        config_data = json.loads(config.config)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="通知配置格式无效") from exc

    result = await notification_service.send_notification(
        notify_type=config.type,
        webhook_url=config_data.get("webhook_url", ""),
        secret=config_data.get("secret"),
        title=title,
        content=content,
    )
    if result.success:
        return {"message": "发送成功", "result": result.raw_response}
    raise HTTPException(status_code=500, detail=result.message)


@router.get("/types")
async def get_notification_types():
    """获取支持的通知类型"""
    return {
        "types": [
            {"value": "feishu", "label": "飞书"},
            {"value": "dingtalk", "label": "钉钉"},
            {"value": "wecom", "label": "企业微信"},
        ]
    }
