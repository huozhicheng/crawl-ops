from fastapi import APIRouter, Depends

from app.api.v1 import (
    audits,
    auth,
    dashboard,
    dependencies,
    executions,
    files,
    nodes,
    notifications,
    projects,
    proxies,
    roles,
    statistics,
    system,
    tasks,
    users,
    venvs,
)

api_router = APIRouter()

# 登录、刷新令牌和当前用户信息是仅有的用户侧公开端点。
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])

# 所有控制平面接口统一要求登录，避免只依赖前端路由守卫。
protected_router = APIRouter(dependencies=[Depends(auth.get_current_user)])
protected_router.include_router(users.router, prefix="/users", tags=["用户管理"])
protected_router.include_router(roles.router, prefix="/roles", tags=["角色管理"])
protected_router.include_router(projects.router, prefix="/projects", tags=["项目管理"])
protected_router.include_router(tasks.router, prefix="/tasks", tags=["任务管理"])
protected_router.include_router(dependencies.router, prefix="/tasks", tags=["任务依赖"])
protected_router.include_router(executions.router, prefix="/executions", tags=["执行记录"])
protected_router.include_router(nodes.router, prefix="/nodes", tags=["节点管理"])
protected_router.include_router(proxies.router, prefix="/proxies", tags=["代理池"])
protected_router.include_router(dashboard.router, prefix="/dashboard", tags=["仪表盘"])
protected_router.include_router(
    notifications.router, prefix="/system/notifications", tags=["通知配置"]
)
protected_router.include_router(statistics.router, prefix="/statistics", tags=["统计报表"])
protected_router.include_router(audits.router, prefix="/audits", tags=["审计日志"])
protected_router.include_router(venvs.router, prefix="/venvs", tags=["虚拟环境"])
protected_router.include_router(files.router, prefix="/files", tags=["文件管理"])
protected_router.include_router(system.router, prefix="/system", tags=["系统配置"])
api_router.include_router(protected_router)

# Worker 不使用用户登录：注册使用部署令牌，后续请求使用节点令牌。
api_router.include_router(nodes.worker_router, prefix="/nodes", tags=["Worker"])
api_router.include_router(projects.worker_router, prefix="/projects", tags=["Worker"])
