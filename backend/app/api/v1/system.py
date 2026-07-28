"""
系统配置API
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from app.core.database import get_db
from app.models import SystemConfig
from app.schemas import schemas

router = APIRouter()


@router.get("/configs")
async def get_system_configs(db: Session = Depends(get_db)):
    """获取系统配置"""
    configs = db.query(SystemConfig).filter(
        # 排除包含 notification_ 的配置，因为它们由 NotificationConfig 管理 (旧数据兼容)
        ~SystemConfig.config_key.like("notification_%")
    ).all()

    # 转换为字典格式返回，方便前端使用
    result = {}
    items = []
    for config in configs:
        items.append({
            "id": config.id,
            "config_key": config.config_key,
            "config_value": config.config_value,
            "description": config.description,
            "updated_at": config.updated_at
        })
        result[config.config_key] = config.config_value

    return {"items": items, "kv_map": result}


@router.put("/configs")
async def update_system_configs(
    updates: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """批量更新系统配置"""
    # updates: {"site_name": "New Name", "max_limit": "100"}

    updated_keys = []
    for key, value in updates.items():
        # 转为字符串存储
        str_val = str(value) if value is not None else ""

        config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if config:
            config.config_value = str_val
        else:
            # 如果不存在，自动创建?
            # 策略：允许自动创建，或者严格限制只能更新已有。
            # 这里允许创建
            config = SystemConfig(
                config_key=key,
                config_value=str_val,
                description=f"Auto created: {key}"
            )
            db.add(config)

        updated_keys.append(key)

    db.commit()
    return {"message": "更新成功", "updated_keys": updated_keys}
