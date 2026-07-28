import os
import tempfile
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.venv_service import venv_service

router = APIRouter()

# ===== Schema Definitions =====


class VenvCreate(BaseModel):
    name: str
    description: Optional[str] = None


class PackageInstall(BaseModel):
    package: str


class PackageBatchInstall(BaseModel):
    packages: List[str]


class VenvResponse(BaseModel):
    id: int
    name: str
    path: str
    python_version: Optional[str]
    description: Optional[str]
    status: int
    install_status: Optional[str] = "idle"
    install_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VenvListResponse(BaseModel):
    items: List[VenvResponse]
    total: int


# ===== API Endpoints =====


@router.get("", response_model=VenvListResponse)
async def list_venvs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取虚拟环境列表"""
    items, total = venv_service.get_list(db, page, page_size, keyword)
    return {"items": items, "total": total}


@router.post("", response_model=VenvResponse)
async def create_venv(data: VenvCreate, db: Session = Depends(get_db)):
    """创建虚拟环境"""
    try:
        venv = venv_service.create(db, data.name, data.description)
        return venv
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{venv_id}")
async def delete_venv(venv_id: int, db: Session = Depends(get_db)):
    """删除虚拟环境"""
    try:
        venv_service.delete(db, venv_id)
        return {"message": "Success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{venv_id}/packages")
async def list_packages(venv_id: int, db: Session = Depends(get_db)):
    """获取已安装包列表"""
    try:
        packages = venv_service.list_packages(db, venv_id)
        return packages
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{venv_id}/packages")
async def install_package(venv_id: int, data: PackageInstall, db: Session = Depends(get_db)):
    """安装单个包"""
    try:
        venv_service.install_package(db, venv_id, data.package)
        return {"message": "Install success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{venv_id}/packages/batch")
async def install_packages_batch(
    venv_id: int,
    data: PackageBatchInstall,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """批量安装包（后台执行，立即返回）"""
    venv = venv_service.get_by_id(db, venv_id)
    if not venv:
        raise HTTPException(status_code=404, detail="环境不存在")

    if venv.install_status == "installing":
        raise HTTPException(status_code=400, detail="正在安装中，请稍后再试")

    if not data.packages:
        raise HTTPException(status_code=400, detail="请提供要安装的包列表")

    # 立即更新状态
    venv.install_status = "installing"
    venv.install_message = f"准备安装 {len(data.packages)} 个包..."
    db.commit()

    # 添加后台任务
    from app.core.database import SessionLocal

    background_tasks.add_task(
        venv_service.install_packages_background, SessionLocal, venv_id, data.packages
    )

    return {"message": "安装任务已启动", "status": "installing", "total": len(data.packages)}


@router.post("/{venv_id}/packages/upload-requirements")
async def upload_requirements(
    venv_id: int,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """上传 requirements.txt 并批量安装（后台执行）"""
    if not file.filename.endswith((".txt", ".requirements")):
        raise HTTPException(status_code=400, detail="仅支持 .txt 或 .requirements 文件")

    venv = venv_service.get_by_id(db, venv_id)
    if not venv:
        raise HTTPException(status_code=404, detail="环境不存在")

    if venv.install_status == "installing":
        raise HTTPException(status_code=400, detail="正在安装中，请稍后再试")

    try:
        # 读取文件内容
        content = await file.read()
        text = content.decode("utf-8")

        # 解析 requirements.txt
        packages = []
        for line in text.split("\n"):
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            # 跳过 -e 和 --xxx 选项
            if line.startswith("-"):
                continue
            packages.append(line)

        if not packages:
            raise HTTPException(status_code=400, detail="文件中没有找到有效的包")

        # 立即更新状态
        venv.install_status = "installing"
        venv.install_message = f"准备安装 {len(packages)} 个包..."
        db.commit()

        # 添加后台任务
        from app.core.database import SessionLocal

        background_tasks.add_task(
            venv_service.install_packages_background, SessionLocal, venv_id, packages
        )

        return {
            "message": "安装任务已启动",
            "status": "installing",
            "total": len(packages),
            "packages": packages,
        }
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请使用 UTF-8 编码")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
