import os
import subprocess
import threading
import time
from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from app.core.config import settings
from app.models import Task, TaskExecution


class TaskService:
    """任务服务"""

    @staticmethod
    def get_by_id(db: Session, task_id: int) -> Optional[Task]:
        """根据ID获取任务"""
        return db.query(Task).filter(Task.id == task_id).first()

    @staticmethod
    def get_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        project_id: Optional[int] = None,
        schedule_type: Optional[str] = None,
        status: Optional[int] = None,
        name: Optional[str] = None
    ) -> Tuple[list, int]:
        """获取任务列表"""
        query = db.query(Task)

        if project_id:
            query = query.filter(Task.project_id == project_id)
        if schedule_type:
            query = query.filter(Task.schedule_type == schedule_type)
        if status is not None:
            query = query.filter(Task.status == status)
        if name:
            query = query.filter(Task.name.like(f"%{name}%"))

        total = query.count()
        items = query.order_by(Task.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    @staticmethod
    def create(db: Session, user_id: int, **kwargs) -> Task:
        """创建任务"""
        task = Task(created_by=user_id, status=1, **kwargs)
        db.add(task)
        db.commit()
        db.refresh(task)

        # 同步到调度器
        from app.core.scheduler import sync_task_to_scheduler
        sync_task_to_scheduler(task)

        return task

    @staticmethod
    def update(db: Session, task: Task, **kwargs) -> Task:
        """更新任务"""
        for key, value in kwargs.items():
            if value is not None and hasattr(task, key):
                setattr(task, key, value)
        db.commit()
        db.refresh(task)

        # 同步到调度器
        from app.core.scheduler import sync_task_to_scheduler
        sync_task_to_scheduler(task)

        return task

    @staticmethod
    def delete(db: Session, task: Task) -> None:
        """删除任务"""
        task_id = task.id
        db.delete(task)
        db.commit()

        # 从调度器移除
        from app.core.scheduler import scheduler_manager
        scheduler_manager.remove_job(f"task_{task_id}")

    @staticmethod
    def count(db: Session) -> int:
        """统计任务数量"""
        return db.query(Task).filter(Task.status == 1).count()

    @staticmethod
    def run(db: Session, task: Task, trigger_type: str = "manual") -> TaskExecution:
        """执行任务 (通过 Redis 队列)"""
        execution = TaskExecution(
            task_id=task.id,
            trigger_type=trigger_type,
            status="pending",
            start_time=datetime.now()
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        logger.info(f"Triggering task {task.id} (Execution {execution.id})")

        # 将任务推送到 Redis 队列
        try:
            import redis
            import json

            project_code = task.project.code
            r = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # 获取虚拟环境路径（如果配置了）
            venv_path = None
            if task.venv_id:
                from app.models import Venv
                venv = db.query(Venv).filter(Venv.id == task.venv_id).first()
                if venv:
                    venv_path = venv.path

            task_payload = {
                "execution_id": execution.id,
                "task_id": task.id,
                "project_id": task.project_id,
                "project_code": project_code,
                "command": task.command,
                "arguments": task.arguments,
                "env_vars": task.env_vars,
                "venv_id": task.venv_id,
                "venv_path": venv_path,  # 传递虚拟环境路径供 Worker 使用
                "timeout": task.timeout_seconds
            }
            r.lpush("crawlops:task:queue", json.dumps(task_payload))
            logger.info(f"Pushed execution {execution.id} to crawlops:task:queue")

        except Exception as e:
            logger.error(f"Failed to push task to Redis: {e}")
            execution.status = "failed"
            execution.error_message = f"Failed to dispatch: {str(e)}"
            execution.end_time = datetime.now()
            db.commit()

        return execution

    @staticmethod
    def _execute_task(task_id: int, execution_id: int):
        """后台执行任务逻辑"""
        from app.core.database import SessionLocal
        db = SessionLocal()
        logger.info(f"Background thread started for execution {execution_id}")
        try:
            # 1. 获取任务和执行记录
            task = db.query(Task).filter(Task.id == task_id).first()
            execution = db.query(TaskExecution).filter(TaskExecution.id == execution_id).first()
            if not task or not execution:
                logger.error(f"Task {task_id} or Execution {execution_id} not found in background thread")
                return

            # 2. 更新状态为 running
            execution.status = "running"
            db.commit()

            # 同步项目代码
            from app.services.project_service import project_service
            if not project_service.sync_project_code(db, task.project_id):
                execution.status = "failed"
                execution.error_message = "Project code sync failed"
                db.commit()
                logger.error(f"Execution {execution_id} failed: Project code sync failed")
                return

            # 3. 准备执行路径和日志
            try:
                project_code = task.project.code
            except Exception as e:
                logger.error(f"Failed to get project code for task {task_id}: {e}")
                execution.status = "failed"
                execution.error_message = f"Failed to get project code: {e}"
                db.commit()
                return

            project_path = os.path.join(settings.PROJECTS_DIR, project_code)
            if not os.path.exists(project_path):
                os.makedirs(project_path, exist_ok=True)

            log_dir = os.path.join(settings.LOGS_DIR, "executions")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"{execution_id}.log")

            logger.info(f"Execution {execution_id} command: {task.command}, path: {project_path}")

            # 4. 执行命令
            cmd = task.command
            if task.arguments:
                cmd += f" {task.arguments}"

            start_time = time.time()
            try:
                with open(log_path, "w", encoding="utf-8") as log_file:
                    log_file.write(f"--- Task Execution Started: {datetime.now()} ---\n")
                    log_file.write(f"Command: {cmd}\n")
                    log_file.write(f"Work Dir: {project_path}\n")
                    log_file.write("-" * 40 + "\n\n")

                    # 合并环境变量
                    env = os.environ.copy()

                    # 1. 注入虚拟环境 PATH
                    if task.venv_id:
                        from app.models import Venv
                        venv = db.query(Venv).filter(Venv.id == task.venv_id).first()
                        if venv and os.path.exists(venv.path):
                            bin_path = os.path.join(venv.path, "bin")
                            env["PATH"] = f"{bin_path}:{env.get('PATH', '')}"
                            log_file.write(f"Using Venv: {venv.name} ({venv.path})\n")
                            logger.info(f"Using Venv: {venv.name} for execution {execution_id}")

                    # 2. 合并用户自定义变量
                    if task.env_vars:
                        import json
                        try:
                            custom_env = json.loads(task.env_vars)
                            env.update(custom_env)
                        except Exception as e:
                            logger.error(f"Failed to parse env_vars: {e}")
                            log_file.write(f"Warning: Failed to parse env_vars: {e}\n")

                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        cwd=project_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        env=env,
                        text=True,
                        bufsize=1
                    )

                    # 实时读取输出并写入日志
                    if process.stdout:
                        for line in process.stdout:
                            log_file.write(line)
                            log_file.flush()

                    process.wait(timeout=task.timeout_seconds)
                    exit_code = process.returncode

                    log_file.write(f"\n" + "-" * 40 + "\n")
                    log_file.write(f"--- Task Execution Finished: {datetime.now()} ---\n")
                    log_file.write(f"Exit Code: {exit_code}\n")

                # 5. 更新成功/失败状态
                execution.status = "success" if exit_code == 0 else "failed"
                execution.exit_code = exit_code
                if exit_code != 0:
                    execution.error_message = f"Process exited with code {exit_code}"
                logger.info(f"Execution {execution_id} finished with status {execution.status}")

            except subprocess.TimeoutExpired:
                logger.warning(f"Execution {execution_id} timed out")
                execution.status = "timeout"
                execution.error_message = f"Task timed out after {task.timeout_seconds} seconds"
            except Exception as e:
                logger.exception(f"Execution {execution_id} encountered an error: {e}")
                execution.status = "failed"
                execution.error_message = str(e)

            # 6. 完成记录
            execution.end_time = datetime.now()
            execution.duration = int(time.time() - start_time)
            db.commit()

        except Exception as e:
            logger.exception(f"Critical error in execution thread {execution_id}: {e}")
        finally:
            db.close()


class ExecutionService:
    """执行记录服务"""

    @staticmethod
    def get_by_id(db: Session, execution_id: int) -> Optional[TaskExecution]:
        """根据ID获取执行记录"""
        return db.query(TaskExecution).filter(TaskExecution.id == execution_id).first()

    @staticmethod
    def get_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        task_id: Optional[int] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Tuple[list, int]:
        """获取执行记录列表"""
        query = db.query(TaskExecution)

        if task_id:
            query = query.filter(TaskExecution.task_id == task_id)
        if status:
            query = query.filter(TaskExecution.status == status)
        if start_time:
            query = query.filter(TaskExecution.start_time >= start_time)
        if end_time:
            query = query.filter(TaskExecution.start_time <= end_time)

        total = query.count()
        items = query.order_by(TaskExecution.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    @staticmethod
    def get_recent(db: Session, limit: int = 10) -> list:
        """获取最近执行记录"""
        return db.query(TaskExecution).order_by(TaskExecution.id.desc()).limit(limit).all()

    @staticmethod
    def count_today(db: Session) -> int:
        """统计今日执行次数"""
        from datetime import date
        today = date.today()
        return db.query(TaskExecution).filter(
            TaskExecution.start_time >= datetime.combine(today, datetime.min.time())
        ).count()

    @staticmethod
    def success_rate(db: Session) -> float:
        """计算成功率"""
        total = db.query(TaskExecution).count()
        if total == 0:
            return 0
        success = db.query(TaskExecution).filter(TaskExecution.status == "success").count()
        return round(success / total * 100, 2)

    @staticmethod
    def update(db: Session, execution: TaskExecution, **kwargs) -> TaskExecution:
        """更新执行记录"""
        for key, value in kwargs.items():
            if value is not None and hasattr(execution, key):
                setattr(execution, key, value)
        db.commit()
        db.refresh(execution)
        return execution


task_service = TaskService()
execution_service = ExecutionService()
