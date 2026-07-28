import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Venv


class VenvService:
    """虚拟环境服务"""

    @staticmethod
    def get_by_id(db: Session, venv_id: int) -> Optional[Venv]:
        return db.query(Venv).filter(Venv.id == venv_id).first()

    @staticmethod
    def get_list(
        db: Session, page: int = 1, page_size: int = 20, keyword: Optional[str] = None
    ) -> Tuple[list, int]:
        query = db.query(Venv).filter(Venv.status == 1)
        if keyword:
            query = query.filter(Venv.name.like(f"%{keyword}%"))

        total = query.count()
        items = query.order_by(Venv.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def create(db: Session, name: str, description: str = None) -> Venv:
        """创建虚拟环境"""
        # 检查名称是否存在
        if db.query(Venv).filter(Venv.name == name).first():
            raise ValueError(f"Environment '{name}' already exists")

        venv_path = os.path.join(settings.VENVS_DIR, name)

        # 1. 物理创建 venv
        try:
            if not os.path.exists(settings.VENVS_DIR):
                os.makedirs(settings.VENVS_DIR)

            logger.info(f"Creating venv at: {venv_path}")
            subprocess.run(
                [sys.executable, "-m", "venv", venv_path],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create venv: {e.stderr}")
            raise RuntimeError(f"Failed to create venv: {e.stderr}")

        # 2. 数据库记录
        venv = Venv(
            name=name,
            path=venv_path,
            python_version=sys.version.split()[0],  # 记录基础Python版本
            description=description,
            status=1,
        )
        db.add(venv)
        db.commit()
        db.refresh(venv)
        return venv

    @staticmethod
    def delete(db: Session, venv_id: int) -> None:
        """删除虚拟环境"""
        venv = VenvService.get_by_id(db, venv_id)
        if not venv:
            raise ValueError("Environment not found")

        # 1. 删除物理文件
        if os.path.exists(venv.path):
            try:
                shutil.rmtree(venv.path)
            except Exception as e:
                logger.error(f"Failed to delete directory {venv.path}: {e}")
                # 继续执行数据库删除

        # 2. 数据库逻辑删除 (或者物理删除，这里选逻辑删除为了保留记录？不，Venv通常物理删)
        # 修正：需求是可重复创建同名，所以建议物理删除记录
        db.delete(venv)
        db.commit()

    @staticmethod
    def install_package(db: Session, venv_id: int, package_name: str) -> bool:
        """安装单个包"""
        venv = VenvService.get_by_id(db, venv_id)
        if not venv:
            raise ValueError("Environment not found")

        pip_path = os.path.join(venv.path, "bin", "pip")
        if not os.path.exists(pip_path):
            raise RuntimeError(f"pip not found at {pip_path}")

        try:
            logger.info(f"Installing {package_name} in {venv.name}")
            subprocess.run(
                [pip_path, "install", package_name], check=True, capture_output=True, text=True
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Install failed: {e.stderr}")
            raise RuntimeError(f"Install failed: {e.stderr}")

    @staticmethod
    def install_packages_batch(db: Session, venv_id: int, packages: List[str]) -> dict:
        """批量安装包

        Args:
            db: 数据库会话
            venv_id: 虚拟环境ID
            packages: 包列表，格式如 ['requests==2.31.0', 'beautifulsoup4']

        Returns:
            dict: {
                'total': 总数,
                'success': 成功数,
                'failed': 失败数,
                'details': [{'package': 'xxx', 'status': 'success/failed', 'message': '...'}]
            }
        """
        venv = VenvService.get_by_id(db, venv_id)
        if not venv:
            raise ValueError("Environment not found")

        pip_path = os.path.join(venv.path, "bin", "pip")
        if not os.path.exists(pip_path):
            raise RuntimeError(f"pip not found at {pip_path}")

        result = {"total": len(packages), "success": 0, "failed": 0, "details": []}

        for package in packages:
            try:
                logger.info(f"Installing {package} in {venv.name}")
                subprocess.run(
                    [pip_path, "install", package],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5分钟超时
                )
                result["success"] += 1
                result["details"].append(
                    {"package": package, "status": "success", "message": "Installed successfully"}
                )
                logger.info(f"✓ {package} installed successfully")
            except subprocess.TimeoutExpired:
                result["failed"] += 1
                result["details"].append(
                    {
                        "package": package,
                        "status": "failed",
                        "message": "Installation timeout (5 minutes)",
                    }
                )
                logger.error(f"✗ {package} installation timeout")
            except subprocess.CalledProcessError as e:
                result["failed"] += 1
                error_msg = e.stderr if e.stderr else str(e)
                result["details"].append(
                    {"package": package, "status": "failed", "message": error_msg}
                )
                logger.error(f"✗ {package} installation failed: {error_msg}")
            except Exception as e:
                result["failed"] += 1
                result["details"].append(
                    {"package": package, "status": "failed", "message": str(e)}
                )
                logger.error(f"✗ {package} installation error: {e}")

        return result

    @staticmethod
    def list_packages(db: Session, venv_id: int) -> List[dict]:
        """获取已安装包列表"""
        venv = VenvService.get_by_id(db, venv_id)
        if not venv:
            raise ValueError("Environment not found")

        pip_path = os.path.join(venv.path, "bin", "pip")
        if not os.path.exists(pip_path):
            raise RuntimeError(f"pip not found at {pip_path}")

        try:
            # 使用 pip list --format=json
            cmd = [pip_path, "list", "--format=json"]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            import json

            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"List packages failed: {e}")
            return []

    @staticmethod
    async def install_packages_background(
        db_session_factory, venv_id: int, packages: List[str]
    ) -> None:
        """后台异步安装包（不阻塞 API）

        Args:
            db_session_factory: 数据库会话工厂（SessionLocal）
            venv_id: 虚拟环境ID
            packages: 包列表
        """
        import asyncio

        db = db_session_factory()
        try:
            venv = VenvService.get_by_id(db, venv_id)
            if not venv:
                logger.error(f"Venv {venv_id} not found for background install")
                return

            pip_path = os.path.join(venv.path, "bin", "pip")
            if not os.path.exists(pip_path):
                venv.install_status = "idle"
                venv.install_message = f"错误: pip 未找到 ({pip_path})"
                db.commit()
                return

            # 更新状态为 installing
            venv.install_status = "installing"
            venv.install_message = f"正在安装 0/{len(packages)} 个包..."
            db.commit()

            success = 0
            failed = 0
            failed_packages = []

            for i, package in enumerate(packages, 1):
                # 更新进度
                venv.install_message = f"正在安装 {i}/{len(packages)}: {package}"
                db.commit()

                try:
                    logger.info(f"[后台] Installing {package} in {venv.name}")
                    proc = await asyncio.create_subprocess_exec(
                        pip_path,
                        "install",
                        package,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

                    if proc.returncode == 0:
                        success += 1
                        logger.info(f"[后台] ✓ {package} installed successfully")
                    else:
                        failed += 1
                        failed_packages.append(package)
                        error_msg = stderr.decode() if stderr else "Unknown error"
                        logger.error(f"[后台] ✗ {package} failed: {error_msg}")
                except asyncio.TimeoutError:
                    failed += 1
                    failed_packages.append(package)
                    logger.error(f"[后台] ✗ {package} installation timeout")
                except Exception as e:
                    failed += 1
                    failed_packages.append(package)
                    logger.error(f"[后台] ✗ {package} error: {e}")

            # 完成，更新最终状态
            venv.install_status = "idle"
            if failed == 0:
                venv.install_message = f"安装完成: 成功 {success} 个包"
            else:
                venv.install_message = f"安装完成: 成功 {success}, 失败 {failed} ({', '.join(failed_packages[:3])}{'...' if len(failed_packages) > 3 else ''})"
            db.commit()
            logger.info(f"[后台] {venv.name} 安装完成: 成功 {success}, 失败 {failed}")
        except Exception as e:
            logger.error(f"[后台] 安装任务异常: {e}")
            # 尝试重置状态
            try:
                venv = VenvService.get_by_id(db, venv_id)
                if venv:
                    venv.install_status = "idle"
                    venv.install_message = f"安装异常: {str(e)[:100]}"
                    db.commit()
            except:
                pass
        finally:
            db.close()


venv_service = VenvService()
