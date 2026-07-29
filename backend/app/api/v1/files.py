import os
import shutil
import zipfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.project_service import project_service

router = APIRouter()


def validate_path(project_path: str, relative_path: str) -> str:
    """验证路径安全性，防止路径穿越攻击"""
    project_root = os.path.realpath(project_path)
    target_path = os.path.realpath(os.path.join(project_root, relative_path or ""))

    # 必须在规范化后校验，并附加路径分隔符，避免 /projects/a 与 /projects/abc 混淆。
    if target_path != project_root and not target_path.startswith(project_root + os.sep):
        raise HTTPException(status_code=400, detail="非法路径")
    return target_path


def validate_upload_filename(filename: Optional[str]) -> str:
    """仅允许上传单个文件名，避免文件名被当作路径使用。"""
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="文件名无效")

    # 在 Unix 容器中，反斜杠不是路径分隔符；仍需拒绝它以避免跨平台绕过。
    if "/" in filename or "\\" in filename or "\x00" in filename:
        raise HTTPException(status_code=400, detail="文件名不能包含路径")

    return filename


def safe_extract_zip(zip_file: zipfile.ZipFile, destination: str) -> None:
    """逐项解压，并阻止 Zip Slip 写入目标目录之外。"""
    destination_root = os.path.realpath(destination)
    for member in zip_file.infolist():
        target_path = os.path.realpath(os.path.join(destination_root, member.filename))
        if os.path.commonpath([destination_root, target_path]) != destination_root:
            raise HTTPException(status_code=400, detail="压缩包包含非法路径")
        zip_file.extract(member, destination_root)


@router.post("/upload/project/{project_id}")
async def upload_project_file(
    project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """上传项目文件（支持zip）"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if project.source_type != "upload":
        raise HTTPException(status_code=400, detail="该项目不是上传类型")

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="仅支持zip文件")

    project_path = os.path.join(settings.PROJECTS_DIR, project.code)

    # 确保目录存在
    if not os.path.exists(project_path):
        os.makedirs(project_path, exist_ok=True)

    # 保存临时文件
    temp_zip = os.path.join(project_path, "temp.zip")
    try:
        with open(temp_zip, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 解压
        with zipfile.ZipFile(temp_zip, "r") as zip_ref:
            safe_extract_zip(zip_ref, project_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")
    finally:
        if os.path.exists(temp_zip):
            os.remove(temp_zip)

    return {"message": "上传并解压成功", "files": os.listdir(project_path)}


@router.get("/project/{project_id}/list")
async def list_project_files(
    project_id: int, path: str = Query("", description="相对路径"), db: Session = Depends(get_db)
):
    """列出项目文件和目录"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_path = os.path.join(settings.PROJECTS_DIR, project.code)

    # 确保项目目录存在
    if not os.path.exists(project_path):
        os.makedirs(project_path, exist_ok=True)
        return {"files": [], "path": path, "project_code": project.code}

    target_path = validate_path(project_path, path)

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="路径不存在")

    if not os.path.isdir(target_path):
        raise HTTPException(status_code=400, detail="路径不是目录")

    files = []
    try:
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            try:
                stat = os.stat(item_path)
                is_dir = os.path.isdir(item_path)

                files.append(
                    {
                        "name": item,
                        "type": "directory" if is_dir else "file",
                        "size": 0 if is_dir else stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "path": os.path.join(path, item).replace("\\", "/"),
                    }
                )
            except Exception:
                continue

        # 排序：目录在前，然后按名称排序
        files.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取目录失败: {str(e)}")

    return {"files": files, "path": path, "project_code": project.code}


@router.get("/project/{project_id}/download")
async def download_project_file(
    project_id: int,
    path: str = Query(..., description="文件相对路径"),
    db: Session = Depends(get_db),
):
    """下载项目中的单个文件"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_path = os.path.join(settings.PROJECTS_DIR, project.code)
    target_path = validate_path(project_path, path)

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if os.path.isdir(target_path):
        raise HTTPException(status_code=400, detail="不能下载目录")

    filename = os.path.basename(target_path)
    return FileResponse(path=target_path, filename=filename, media_type="application/octet-stream")


@router.get("/project/{project_id}/view")
async def view_project_file(
    project_id: int,
    path: str = Query(..., description="文件相对路径"),
    db: Session = Depends(get_db),
):
    """预览项目文件内容（文本文件）"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_path = os.path.join(settings.PROJECTS_DIR, project.code)
    target_path = validate_path(project_path, path)

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if os.path.isdir(target_path):
        raise HTTPException(status_code=400, detail="不能预览目录")

    # 检查文件大小（限制10MB）
    file_size = os.path.getsize(target_path)
    if file_size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大，无法预览")

    try:
        # 尝试以文本方式读取
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "content": content,
            "filename": os.path.basename(target_path),
            "size": file_size,
            "path": path,
        }
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件不是文本格式，无法预览")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")


@router.post("/project/{project_id}/upload-file")
async def upload_single_file(
    project_id: int,
    path: str = Query("", description="目标目录相对路径"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传单个文件到指定目录"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_path = os.path.join(settings.PROJECTS_DIR, project.code)
    target_dir = validate_path(project_path, path)

    # 确保目标目录存在
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    if not os.path.isdir(target_dir):
        raise HTTPException(status_code=400, detail="目标路径不是目录")

    filename = validate_upload_filename(file.filename)
    file_path = validate_path(project_path, os.path.join(path, filename))

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {
            "message": "上传成功",
            "filename": filename,
            "path": os.path.join(path, filename).replace("\\", "/"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.put("/project/{project_id}/save")
async def save_project_file(
    project_id: int,
    path: str = Query(..., description="文件相对路径"),
    content: dict = None,
    db: Session = Depends(get_db),
):
    """保存文件内容（在线编辑）"""
    if not content or "content" not in content:
        raise HTTPException(status_code=400, detail="缺少文件内容")

    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_path = os.path.join(settings.PROJECTS_DIR, project.code)
    target_path = validate_path(project_path, path)

    # 确保父目录存在
    parent_dir = os.path.dirname(target_path)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content["content"])

        return {"message": "保存成功", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.delete("/project/{project_id}")
async def delete_project_file(
    project_id: int,
    path: str = Query(..., description="文件/目录相对路径"),
    db: Session = Depends(get_db),
):
    """删除项目文件或目录"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not path or path == "/" or path == ".":
        raise HTTPException(status_code=400, detail="不能删除根目录")

    project_path = os.path.join(settings.PROJECTS_DIR, project.code)
    target_path = validate_path(project_path, path)

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="文件或目录不存在")

    # 禁止删除某些重要文件/目录
    forbidden = [".git", ".env"]
    basename = os.path.basename(target_path)
    if basename in forbidden:
        raise HTTPException(status_code=403, detail=f"禁止删除 {basename}")

    try:
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)

        return {"message": "删除成功", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/project/{project_id}/search")
async def search_project_files(
    project_id: int,
    keyword: str = Query(..., description="搜索关键词"),
    db: Session = Depends(get_db),
):
    """搜索项目文件（按文件名）"""
    project = project_service.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_path = os.path.join(settings.PROJECTS_DIR, project.code)

    if not os.path.exists(project_path):
        return {"results": [], "keyword": keyword}

    results = []
    keyword_lower = keyword.lower()

    try:
        for root, dirs, files in os.walk(project_path):
            # 跳过某些目录
            dirs[:] = [d for d in dirs if d not in [".git", "__pycache__", "node_modules", ".venv"]]

            for filename in files:
                if keyword_lower in filename.lower():
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, project_path).replace("\\", "/")
                    stat = os.stat(file_path)

                    results.append(
                        {
                            "name": filename,
                            "path": relative_path,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        }
                    )

        return {"results": results, "keyword": keyword, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")
