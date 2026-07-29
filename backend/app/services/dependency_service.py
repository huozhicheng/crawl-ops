"""
任务依赖服务

实现DAG调度逻辑：
- 依赖关系管理
- 拓扑排序
- 循环依赖检测
- 依赖触发
"""

from typing import Dict, List, Optional, Set

from loguru import logger
from sqlalchemy.orm import Session

from app.models import Task, TaskExecution
from app.models.task_dependency import TaskDependency


class DependencyService:
    """任务依赖服务"""

    @staticmethod
    def add_dependency(
        db: Session, task_id: int, depends_on_task_id: int, condition_type: str = "success"
    ) -> TaskDependency:
        """
        添加任务依赖

        Args:
            task_id: 当前任务ID
            depends_on_task_id: 依赖的任务ID
            condition_type: 触发条件（success/complete/any）
        """
        # 检查是否会产生循环依赖
        if DependencyService.would_create_cycle(db, task_id, depends_on_task_id):
            raise ValueError("添加此依赖会产生循环依赖")

        dependency = TaskDependency(
            task_id=task_id, depends_on_task_id=depends_on_task_id, condition_type=condition_type
        )
        db.add(dependency)
        db.commit()
        db.refresh(dependency)

        logger.info(f"添加任务依赖: {task_id} -> {depends_on_task_id}")
        return dependency

    @staticmethod
    def remove_dependency(db: Session, task_id: int, depends_on_task_id: int) -> bool:
        """移除任务依赖"""
        dep = (
            db.query(TaskDependency)
            .filter(
                TaskDependency.task_id == task_id,
                TaskDependency.depends_on_task_id == depends_on_task_id,
            )
            .first()
        )

        if dep:
            db.delete(dep)
            db.commit()
            return True
        return False

    @staticmethod
    def get_dependencies(db: Session, task_id: int) -> List[TaskDependency]:
        """获取任务的所有依赖"""
        return db.query(TaskDependency).filter(TaskDependency.task_id == task_id).all()

    @staticmethod
    def get_dependents(db: Session, task_id: int) -> List[TaskDependency]:
        """获取依赖此任务的所有任务"""
        return db.query(TaskDependency).filter(TaskDependency.depends_on_task_id == task_id).all()

    @staticmethod
    def would_create_cycle(db: Session, task_id: int, depends_on_task_id: int) -> bool:
        """
        检测添加依赖是否会产生循环

        使用DFS检查从depends_on_task_id是否能到达task_id
        """
        if task_id == depends_on_task_id:
            return True

        visited: Set[int] = set()
        stack = [depends_on_task_id]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            # 获取current的依赖
            deps = db.query(TaskDependency).filter(TaskDependency.task_id == current).all()

            for dep in deps:
                if dep.depends_on_task_id == task_id:
                    return True
                stack.append(dep.depends_on_task_id)

        return False

    @staticmethod
    def check_dependencies_satisfied(db: Session, task_id: int) -> bool:
        """
        检查任务的所有依赖是否满足

        Returns:
            True如果所有依赖都满足
        """
        dependencies = DependencyService.get_dependencies(db, task_id)

        if not dependencies:
            return True

        for dep in dependencies:
            # 获取依赖任务的最新执行记录
            latest_execution = (
                db.query(TaskExecution)
                .filter(TaskExecution.task_id == dep.depends_on_task_id)
                .order_by(TaskExecution.id.desc())
                .first()
            )

            if not latest_execution:
                return False

            if dep.condition_type == "success":
                if latest_execution.status != "success":
                    return False
            elif dep.condition_type == "complete":
                if latest_execution.status not in ("success", "failed"):
                    return False
            # "any" 类型只要有执行记录就满足

        return True

    @staticmethod
    def trigger_dependents(db: Session, task_id: int, task_status: str) -> List[int]:
        """
        触发依赖此任务的任务

        当任务完成时，检查并触发满足条件的下游任务

        Returns:
            被触发的任务ID列表
        """
        triggered: List[int] = []
        dependents = DependencyService.get_dependents(db, task_id)

        for dep in dependents:
            # 检查触发条件
            should_trigger = False

            if dep.condition_type == "success" and task_status == "success":
                should_trigger = True
            elif dep.condition_type == "complete" and task_status in ("success", "failed"):
                should_trigger = True
            elif dep.condition_type == "any":
                should_trigger = True

            if should_trigger:
                # 检查该任务的所有依赖是否都满足
                if DependencyService.check_dependencies_satisfied(db, dep.task_id):
                    triggered.append(dep.task_id)
                    logger.info(f"依赖触发任务: {dep.task_id} (由任务 {task_id} 触发)")

        return triggered

    @staticmethod
    def topological_sort(db: Session, task_ids: List[int]) -> List[int]:
        """
        对任务进行拓扑排序

        返回按依赖关系排序的任务ID列表
        """
        # 构建邻接表和入度表
        graph: Dict[int, List[int]] = {tid: [] for tid in task_ids}
        in_degree: Dict[int, int] = {tid: 0 for tid in task_ids}

        for tid in task_ids:
            deps = DependencyService.get_dependencies(db, tid)
            for dep in deps:
                if dep.depends_on_task_id in graph:
                    graph[dep.depends_on_task_id].append(tid)
                    in_degree[tid] += 1

        # Kahn算法
        queue = [tid for tid in task_ids if in_degree[tid] == 0]
        result: List[int] = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(task_ids):
            raise ValueError("检测到循环依赖，无法进行拓扑排序")

        return result


dependency_service = DependencyService()
