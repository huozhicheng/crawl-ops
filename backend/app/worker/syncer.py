import logging
import os
import shutil
import subprocess
import tempfile
import zipfile

logger = logging.getLogger(__name__)


class ProjectSyncer:
    """代码同步器

    负责在 Worker 节点同步项目代码：
    - Git 类型项目：执行 git pull
    - Upload 类型项目：从 Master API 下载 zip 包并解压
    """

    def sync(self, project_code: str, target_path: str, node_token: str) -> bool:
        """同步项目代码到本地

        Args:
            project_code: 项目代码标识
            target_path: 本地目标路径

        Returns:
            bool: 同步是否成功
        """
        # 确保目录存在
        if not os.path.exists(target_path):
            os.makedirs(target_path, exist_ok=True)

        # 检查是否为 git 仓库
        git_dir = os.path.join(target_path, ".git")
        if os.path.isdir(git_dir):
            return self._sync_git(project_code, target_path)
        else:
            # 非 Git 项目，尝试从 Master API 下载
            return self._sync_from_api(project_code, target_path, node_token)

    def _sync_git(self, project_code: str, target_path: str) -> bool:
        """通过 Git 同步代码"""
        try:
            logger.info(f"Pulling latest code for {project_code}...")
            subprocess.check_call(["git", "pull"], cwd=target_path)
            return True
        except Exception as e:
            logger.error(f"Git pull failed: {e}")
            return False

    def _sync_from_api(self, project_code: str, target_path: str, node_token: str) -> bool:
        """从 Master API 下载项目代码

        用于 Upload 类型的项目，Worker 无法通过 Git 同步时使用。
        """
        import requests

        master_url = os.environ.get("MASTER_URL", "http://backend:18081")
        download_url = f"{master_url}/api/v1/projects/code/{project_code}/download"

        try:
            logger.info(f"Downloading project {project_code} from {download_url}...")

            resp = requests.get(
                download_url,
                headers={"X-Node-Token": node_token},
                timeout=60,
                stream=True,
            )
            if resp.status_code == 404:
                # 项目在 Master 上不存在，可能是纯本地项目
                logger.warning(f"Project {project_code} not found on Master, skipping download")
                return os.path.exists(target_path) and os.listdir(target_path)

            if resp.status_code != 200:
                logger.error(f"Failed to download project: HTTP {resp.status_code}")
                return False

            # 保存到临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
            try:
                for chunk in resp.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file.close()

                # 解压到目标目录
                # 先清空目标目录（保留 .git 如果有的话）
                if os.path.exists(target_path):
                    for item in os.listdir(target_path):
                        if item == ".git":
                            continue
                        item_path = os.path.join(target_path, item)
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)

                # 解压 zip 文件
                with zipfile.ZipFile(temp_file.name, "r") as zip_ref:
                    # zip 内容结构是 project_code/... 所以需要提取顶层目录
                    for member in zip_ref.namelist():
                        # 跳过目录
                        if member.endswith("/"):
                            continue
                        # 去掉顶层目录前缀
                        parts = member.split("/", 1)
                        if len(parts) > 1:
                            relative_path = parts[1]
                        else:
                            relative_path = member

                        # 创建目标路径
                        dest_path = os.path.join(target_path, relative_path)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                        # 提取文件
                        with zip_ref.open(member) as src, open(dest_path, "wb") as dst:
                            dst.write(src.read())

                logger.info(f"Successfully downloaded and extracted project {project_code}")
                return True

            finally:
                # 清理临时文件
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error downloading project: {e}")
            return False
        except zipfile.BadZipFile as e:
            logger.error(f"Invalid zip file received: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to sync project from API: {e}")
            return False
