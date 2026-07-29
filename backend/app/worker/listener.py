import json
import logging
import os
import signal
import socket
import time
from typing import Any, Dict

import psutil
import redis

from app.core.config import settings
from app.worker.executor import TaskExecutor
from app.worker.syncer import ProjectSyncer

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [WORKER] - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _get_memory_usage() -> float:
    """
    获取内存使用百分比（容器感知）

    在 Docker 容器内，psutil.virtual_memory() 读取的是宿主机的 /proc/meminfo，
    而非容器的 cgroup 内存限制。此函数优先从 cgroup 文件读取容器实际内存使用。
    """
    try:
        # cgroup v2
        cg_max = "/sys/fs/cgroup/memory.max"
        cg_current = "/sys/fs/cgroup/memory.current"
        if os.path.exists(cg_max) and os.path.exists(cg_current):
            with open(cg_max) as f:
                max_val = f.read().strip()
            if max_val != "max":  # "max" 表示无限制
                with open(cg_current) as f:
                    current = int(f.read().strip())
                return round(current / int(max_val) * 100, 1)

        # cgroup v1
        cg_limit = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
        cg_usage = "/sys/fs/cgroup/memory/memory.usage_in_bytes"
        if os.path.exists(cg_limit) and os.path.exists(cg_usage):
            with open(cg_limit) as f:
                limit = int(f.read().strip())
            # 超大值表示无限制（通常 > 主机内存）
            host_mem = psutil.virtual_memory().total
            if limit < host_mem:
                with open(cg_usage) as f:
                    usage = int(f.read().strip())
                return round(usage / limit * 100, 1)
    except Exception:
        pass

    # 非容器环境，直接用 psutil
    return psutil.virtual_memory().percent


def _get_disk_usage() -> float:
    """
    获取磁盘使用百分比

    优先检测数据目录所在分区，而非根分区。
    在 Docker 中根分区是 overlay，多个容器看到的值相同。
    数据目录通常是独立挂载的 volume，更能反映实际使用情况。
    """
    try:
        data_dir = getattr(settings, "PROJECTS_DIR", "/app/data/projects")
        if os.path.exists(data_dir):
            return psutil.disk_usage(data_dir).percent
    except Exception:
        pass
    return psutil.disk_usage("/").percent


class WorkerListener:
    """Worker 监听器"""

    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.queue_key = "crawlops:task:queue"
        self.running = True
        self.hostname = socket.gethostname()
        self.executor = TaskExecutor()
        self.syncer = ProjectSyncer()
        self.token = None
        self.node_id = None

        # 注册信号处理
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
        logger.info("Received shutdown signal, stopping worker...")
        self.running = False

    def register(self):
        """Register via API"""
        master_url = os.environ.get("MASTER_URL", "http://backend:18081")
        url = f"{master_url}/api/v1/nodes/register"
        registration_token = settings.WORKER_REGISTRATION_TOKEN
        if not registration_token:
            logger.error("WORKER_REGISTRATION_TOKEN is not configured")
            return False

        try:
            import platform

            import requests

            payload = {
                "name": self.hostname,
                "host": socket.gethostbyname(self.hostname),
                "port": 0,
                "os_type": platform.system(),
            }
            logger.info(f"Registering to {url}...")
            resp = requests.post(
                url,
                json=payload,
                headers={"X-Worker-Registration-Token": registration_token},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                self.node_id = data.get("node_id")
                logger.info(f"Registered successfully! Node ID: {self.node_id}")
                return True
            else:
                logger.error(f"Registration failed: {resp.text}")
        except Exception as e:
            logger.error(f"Registration error: {e}")
        return False

    def heartbeat_loop(self):
        """Send heartbeats periodically"""
        master_url = os.environ.get("MASTER_URL", "http://backend:18081")
        url = f"{master_url}/api/v1/nodes/heartbeat"
        import platform

        import requests

        while self.running:
            # 如果没有 token，尝试重新注册
            if not self.token:
                logger.info("No token, attempting to register...")
                if self.register():
                    logger.info("Registration successful!")
                else:
                    time.sleep(5)
                    continue

            try:
                net_io = psutil.net_io_counters()
                payload = {
                    "cpu_usage": psutil.cpu_percent(),
                    "memory_usage": _get_memory_usage(),
                    "disk_usage": _get_disk_usage(),
                    "os_type": platform.system(),
                    "network_sent": net_io.bytes_sent,
                    "network_recv": net_io.bytes_recv,
                }
                headers = {"X-Node-Token": self.token}
                resp = requests.post(url, json=payload, headers=headers, timeout=5)
                if resp.status_code != 200:
                    logger.warning(f"Heartbeat failed: {resp.status_code}")
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            time.sleep(5)

    def run(self):
        if not self.register():
            logger.warning("Initial registration failed, will retry in loop/heartbeat")

        # P3: 启动时重试之前失败的回调
        retry_count = TaskExecutor.retry_failed_callbacks(self.token)
        if retry_count > 0:
            logger.info(f"Startup: retried {retry_count} failed callbacks")

        # Start heartbeat thread
        import threading

        hb_thread = threading.Thread(target=self.heartbeat_loop)
        hb_thread.daemon = True
        hb_thread.start()

        while self.running:
            try:
                # 阻塞读取队列 (timeout=5s)
                item = self.redis.blpop(self.queue_key, timeout=5)

                if item:
                    _, payload_str = item
                    task_payload = json.loads(payload_str)
                    self.process_task(task_payload)

            except redis.ConnectionError:
                logger.error("Redis connection lost, reconnecting in 5s...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(1)

    def process_task(self, payload: Dict[str, Any]):
        execution_id = payload.get("execution_id")
        task_id = payload.get("task_id")
        logger.info(f"Received task {task_id} (Execution {execution_id})")

        # 注入节点身份，供 Worker 回调时进行服务端鉴权。
        payload["node_id"] = self.node_id
        payload["node_token"] = self.token

        # 1. 同步代码
        project_code = payload.get("project_code")
        project_path = os.path.join(settings.PROJECTS_DIR, project_code)

        if not self.syncer.sync(project_code, project_path, self.token):
            logger.error(f"Failed to sync project {project_code}")
            # TODO: Report failure to Master API
            return

        # 2. 执行任务
        self.executor.execute(payload, project_path)


if __name__ == "__main__":
    worker = WorkerListener()
    worker.run()
