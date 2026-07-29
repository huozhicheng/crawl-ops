import json
import logging
import os
import signal
import socket
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class TaskExecutor:
    """任务执行器"""

    def execute(self, task_payload: Dict[str, Any], work_dir: str):
        execution_id = task_payload.get("execution_id")
        command = task_payload.get("command")
        arguments = task_payload.get("arguments")
        env_vars = task_payload.get("env_vars")
        venv_id = task_payload.get("venv_id")
        venv_path = task_payload.get("venv_path")  # Master 传递的虚拟环境路径
        timeout = task_payload.get("timeout", 3600)

        logger.info(f"Executing task {execution_id} in {work_dir}")

        # 从 task_payload 获取 node_id（由 listener 注入）
        node_id = task_payload.get("node_id")
        node_token = task_payload.get("node_token")
        worker_headers = {"X-Node-Token": node_token} if node_token else None

        # 立即通知 Master 任务已开始执行（状态 pending → running）
        master_url = os.environ.get("MASTER_URL", "http://backend:18081")
        start_url = f"{master_url}/api/v1/executions/{execution_id}/start"
        try:
            import requests

            resp = requests.post(start_url, headers=worker_headers, timeout=5)
            if resp.status_code == 200:
                logger.info(f"Notified Master: execution {execution_id} started on node {node_id}")
            else:
                logger.warning(f"Start notification failed: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed to notify start: {e}")

        # 准备环境
        env = os.environ.copy()

        # 1. 注入 Venv - 使用 Master 传递的 venv_path
        # 在分布式场景下，Venv 目录需要通过 NFS 共享或相同路径挂载
        if venv_path and os.path.exists(venv_path):
            bin_path = os.path.join(venv_path, "bin")
            if os.path.exists(bin_path):
                env["PATH"] = f"{bin_path}:{env.get('PATH', '')}"
                env["VIRTUAL_ENV"] = venv_path  # 显式设置 VIRTUAL_ENV 变量，模拟激活状态
                logger.info(f"Injected venv PATH: {bin_path}")
            else:
                logger.warning(f"Venv bin path not found: {bin_path}")
        elif venv_id:
            logger.warning(
                f"Venv ID {venv_id} specified but venv_path not provided or not accessible"
            )

        # 2. 注入自定义变量
        if env_vars:
            try:
                custom_env = json.loads(env_vars)
                env.update(custom_env)
            except:
                pass

        # 3. 拼接命令
        full_cmd = command
        if arguments:
            full_cmd += f" {arguments}"

        # 4. 执行
        log_dir = os.path.join(settings.LOGS_DIR, "executions")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{execution_id}.log")
        pid_file = os.path.join(log_dir, f"{execution_id}.pid")

        try:
            # 先写入日志头部（使用 w 模式覆盖）
            with open(log_path, "w", encoding="utf-8") as log_file:
                log_file.write(
                    f"--- [Worker:{socket.gethostname()}] Task Started: {datetime.now()} ---\n"
                )
                log_file.write(f"Cmd: {full_cmd}\n\n")

            process = subprocess.Popen(
                full_cmd,
                shell=True,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                bufsize=1,
                start_new_session=True,
            )

            # 保存 PID 文件用于停止任务
            with open(pid_file, "w") as f:
                f.write(str(process.pid))

            # 启动线程和事件
            import threading

            import redis

            stop_monitor = threading.Event()
            monitor_finished = threading.Event()
            stop_requested = threading.Event()  # 用户请求停止的标志
            log_lock = threading.Lock()  # 日志写入锁，防止多线程写入冲突

            def write_log(content):
                """线程安全的日志写入"""
                with log_lock:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(content)
                        f.flush()

            def monitor_memory(pid, stop_event, finished_event):
                """后台监控进程内存使用"""
                try:
                    import psutil

                    parent_proc = psutil.Process(pid)
                    last_log_time = time.time()
                    max_memory_mb = 0

                    while not stop_event.is_set():
                        try:
                            total_mem_mb = 0
                            try:
                                total_mem_mb = parent_proc.memory_info().rss / 1024 / 1024
                                for child in parent_proc.children(recursive=True):
                                    try:
                                        total_mem_mb += child.memory_info().rss / 1024 / 1024
                                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                                        pass
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                break

                            max_memory_mb = max(max_memory_mb, total_mem_mb)

                            current_time = time.time()
                            system_mem = psutil.virtual_memory()

                            should_log = (current_time - last_log_time >= 30) or (
                                system_mem.percent > 85
                            )

                            if should_log and not stop_event.is_set():
                                write_log(
                                    f"[Monitor] Process Memory: {total_mem_mb:.1f}MB, System: {system_mem.percent}% ({system_mem.used // 1024 // 1024}MB used)\n"
                                )
                                last_log_time = current_time

                                if system_mem.percent > 85:
                                    logger.warning(f"High memory usage: {system_mem.percent}%")

                            stop_event.wait(5)
                        except psutil.NoSuchProcess:
                            break
                        except Exception:
                            break

                    if max_memory_mb > 0 and not stop_event.is_set():
                        write_log(f"[Monitor] Peak Memory: {max_memory_mb:.1f}MB\n")
                except Exception as e:
                    logger.error(f"Memory monitor error: {e}")
                finally:
                    finished_event.set()

            def listen_stop_signal(exec_id, proc, stop_event):
                """监听 Redis Pub/Sub 停止信号"""
                try:
                    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
                    pubsub = r.pubsub()
                    pubsub.subscribe(f"stop:execution:{exec_id}")
                    logger.info(f"开始监听停止信号: stop:execution:{exec_id}")

                    for message in pubsub.listen():
                        if message["type"] == "message":
                            logger.info(f"收到停止信号: execution_id={exec_id}")
                            stop_event.set()
                            try:
                                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                                logger.info(f"已终止进程组: PID={proc.pid}")
                            except Exception:
                                try:
                                    proc.kill()
                                    logger.info(f"已强制终止进程: PID={proc.pid}")
                                except:
                                    pass
                            break
                    pubsub.unsubscribe()
                except Exception as e:
                    logger.warning(f"停止信号监听异常: {e}")

            def read_output(proc):
                """在独立线程中读取进程输出"""
                try:
                    for line in proc.stdout:
                        write_log(line)
                except Exception as e:
                    logger.debug(f"读取输出结束: {e}")

            monitor_thread = threading.Thread(
                target=monitor_memory,
                args=(process.pid, stop_monitor, monitor_finished),
                daemon=True,
            )
            monitor_thread.start()

            stop_listener_thread = threading.Thread(
                target=listen_stop_signal, args=(execution_id, process, stop_requested), daemon=True
            )
            stop_listener_thread.start()

            output_thread = threading.Thread(target=read_output, args=(process,), daemon=True)
            output_thread.start()

            # 等待进程结束（带超时保护）
            timeout_expired = False
            try:
                process.wait(timeout=timeout if timeout else None)
            except subprocess.TimeoutExpired:
                timeout_expired = True
                logger.warning(f"Execution {execution_id} timed out locally after {timeout}s")
                write_log(f"\n[Timeout] 任务执行超时 ({timeout}秒)，正在终止进程...\n")
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        process.wait(timeout=5)
                except OSError:
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except Exception:
                        pass
            exit_code = process.returncode

            # 等待输出线程完成
            output_thread.join(timeout=2)

            # 停止监控线程
            stop_monitor.set()
            monitor_finished.wait(timeout=2)

            # 写入结束日志（使用同一个锁）
            write_log(f"\n--- Task Finished: {datetime.now()} ---\n")
            write_log(f"Exit Code: {exit_code}\n")

            if stop_requested.is_set():
                write_log("任务被用户手动停止\n")
            elif timeout_expired:
                write_log(f"任务执行超时：超过 {timeout} 秒\n")

            if exit_code != 0 and not stop_requested.is_set() and not timeout_expired:
                write_log(f"\n--- Diagnostic Info ---\n")

                if exit_code > 128:
                    signal_num = exit_code - 128
                    signal_names = {
                        1: "SIGHUP",
                        2: "SIGINT",
                        3: "SIGQUIT",
                        6: "SIGABRT",
                        9: "SIGKILL",
                        14: "SIGALRM",
                        15: "SIGTERM",
                    }
                    signal_name = signal_names.get(signal_num, f"Signal {signal_num}")
                    write_log(f"Signal: {signal_name} ({signal_num})\n")

                    if signal_num == 9:
                        write_log("Hint: SIGKILL 通常由 OOM Killer 发送，检查内存使用\n")
                    elif signal_num == 15:
                        write_log("Hint: SIGTERM 可能来源：1)手动停止 2)Docker重启 3)进程管理器\n")

                try:
                    import psutil

                    mem = psutil.virtual_memory()
                    write_log(
                        f"Memory: {mem.percent}% used ({mem.used // 1024 // 1024}MB / {mem.total // 1024 // 1024}MB)\n"
                    )
                except:
                    pass

            # 5. 上报结果（必须在 if 块外部，确保始终执行）
            logger.info(
                f"Execution {execution_id} finished with code {exit_code}, stopped={stop_requested.is_set()}"
            )

            # Callback to Master (带重试)
            master_url = os.environ.get("MASTER_URL", "http://backend:18081")
            callback_url = f"{master_url}/api/v1/executions/{execution_id}/callback"

            # 根据终止原因上报不同状态
            if stop_requested.is_set():
                payload = {
                    "status": "stopped",
                    "exit_code": exit_code,
                    "error_message": "任务被用户手动停止",
                }
            elif timeout_expired:
                payload = {
                    "status": "timeout",
                    "exit_code": exit_code if exit_code is not None else -1,
                    "error_message": f"任务执行超时：超过 {timeout} 秒",
                }
            else:
                payload = {
                    "status": "success" if exit_code == 0 else "failed",
                    "exit_code": exit_code,
                    "error_message": (
                        f"Process exited with code {exit_code}" if exit_code != 0 else None
                    ),
                }
            self._send_callback_with_retry(callback_url, payload, headers=worker_headers)

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            # Try to report failure (带重试)
            master_url = os.environ.get("MASTER_URL", "http://backend:18081")
            callback_url = f"{master_url}/api/v1/executions/{execution_id}/callback"
            payload = {"status": "failed", "exit_code": 1, "error_message": str(e)}
            self._send_callback_with_retry(callback_url, payload, headers=worker_headers)
        finally:
            # 始终清理 PID 文件
            if os.path.exists(pid_file):
                try:
                    os.remove(pid_file)
                except Exception as e:
                    logger.warning(f"Failed to remove PID file: {e}")

    def _send_callback_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = None,
        base_delay: float = None,
    ) -> bool:
        """
        发送回调请求（带重试机制）

        Args:
            url: 回调URL
            payload: 请求体
            max_retries: 最大重试次数（默认使用配置）
            base_delay: 基础延迟（秒），使用指数退避（默认使用配置）

        Returns:
            True if successful, False otherwise
        """
        import requests

        # 使用配置默认值
        if max_retries is None:
            max_retries = settings.CALLBACK_MAX_RETRIES
        if base_delay is None:
            base_delay = settings.CALLBACK_BASE_DELAY

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Callback sent successfully to {url}")
                    return True
                logger.warning(f"Callback returned status {response.status_code}")
                if 400 <= response.status_code < 500 and response.status_code not in (408, 429):
                    logger.error(
                        "Callback request is invalid or unauthorized; it will not be retried"
                    )
                    return False
            except Exception as e:
                logger.warning(f"Callback attempt {attempt + 1}/{max_retries + 1} failed: {e}")

            # 如果不是最后一次尝试，等待后重试
            if attempt < max_retries:
                delay = base_delay * (2**attempt)  # 指数退避: 2s, 4s, 8s
                logger.info(f"Retrying callback in {delay}s...")
                time.sleep(delay)

        # P3: 所有重试失败后，持久化到本地文件等待后续重试
        logger.error(
            f"Failed to send callback after {max_retries + 1} attempts, persisting for later retry"
        )
        self._persist_failed_callback(url, payload, headers)
        return False

    def _persist_failed_callback(
        self, url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        持久化失败的回调到本地文件
        网络恢复后可由 retry_failed_callbacks 方法重试
        """
        import uuid

        failed_dir = os.path.join(settings.LOGS_DIR, "failed_callbacks")
        os.makedirs(failed_dir, exist_ok=True)

        callback_data = {
            "url": url,
            "payload": payload,
            "node_token": headers.get("X-Node-Token") if headers else None,
            "timestamp": datetime.now().isoformat(),
            "retry_count": 0,
        }

        file_path = os.path.join(failed_dir, f"{uuid.uuid4()}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(callback_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Persisted failed callback to {file_path}")
        except Exception as e:
            logger.error(f"Failed to persist callback: {e}")

    @staticmethod
    def retry_failed_callbacks(node_token: Optional[str] = None) -> int:
        """
        重试所有失败的回调（Worker 启动时调用）

        - 过期文件（超过配置的小时数）自动删除
        - 超过最大重试次数的文件自动删除

        Returns:
            成功重试的回调数量
        """
        import glob

        import requests

        failed_dir = os.path.join(settings.LOGS_DIR, "failed_callbacks")
        if not os.path.exists(failed_dir):
            return 0

        success_count = 0
        expired_count = 0
        max_retry_exceeded_count = 0
        failed_files = glob.glob(os.path.join(failed_dir, "*.json"))

        max_age_hours = settings.CALLBACK_MAX_AGE_HOURS
        max_retry_count = settings.CALLBACK_MAX_RETRY_COUNT

        for file_path in failed_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    callback_data = json.load(f)

                # 检查过期
                timestamp_str = callback_data.get("timestamp")
                if timestamp_str:
                    created_at = datetime.fromisoformat(timestamp_str)
                    age_seconds = (datetime.now() - created_at).total_seconds()
                    if age_seconds > max_age_hours * 3600:
                        os.remove(file_path)
                        expired_count += 1
                        logger.warning(
                            f"Expired callback removed (age > {max_age_hours}h): {file_path}"
                        )
                        continue

                # 检查重试次数
                retry_count = callback_data.get("retry_count", 0)
                if retry_count >= max_retry_count:
                    os.remove(file_path)
                    max_retry_exceeded_count += 1
                    logger.error(
                        f"Max retry exceeded ({max_retry_count}), callback abandoned: {file_path}"
                    )
                    continue

                url = callback_data["url"]
                payload = callback_data["payload"]

                callback_token = callback_data.get("node_token") or node_token
                headers = {"X-Node-Token": callback_token} if callback_token else None
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    os.remove(file_path)
                    success_count += 1
                    logger.info(f"Retried callback successfully: {url}")
                elif 400 <= response.status_code < 500 and response.status_code not in (408, 429):
                    os.remove(file_path)
                    logger.error(
                        f"Discarded invalid or unauthorized callback: {file_path} "
                        f"(status {response.status_code})"
                    )
                else:
                    # 更新重试次数
                    callback_data["retry_count"] = retry_count + 1
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(callback_data, f, ensure_ascii=False, indent=2)
                    logger.warning(
                        f"Retry callback failed with status {response.status_code}, attempt {retry_count + 1}"
                    )
            except Exception as e:
                logger.warning(f"Failed to retry callback {file_path}: {e}")

        if success_count > 0 or expired_count > 0 or max_retry_exceeded_count > 0:
            logger.info(
                f"Callback retry summary: {success_count} succeeded, "
                f"{expired_count} expired, {max_retry_exceeded_count} max retries exceeded"
            )

        return success_count
