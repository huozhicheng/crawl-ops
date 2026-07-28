from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ===== 通用响应 =====
class ResponseBase(BaseModel):
    code: int = 200
    message: str = "success"


class PaginatedResponse(ResponseBase):
    total: int = 0
    page: int = 1
    page_size: int = 20


# ===== 用户相关 =====
class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role_ids: List[int] = []


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[int] = None


class UserResponse(UserBase):
    id: int
    status: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(PaginatedResponse):
    items: List[UserResponse] = []


# ===== 认证相关 =====
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# ===== 项目相关 =====
class ProjectBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    type: str = "python"
    source_type: str = "upload"
    git_url: Optional[str] = None
    git_branch: Optional[str] = "main"
    entry_file: Optional[str] = None
    python_version: str = "3.10"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    entry_file: Optional[str] = None
    status: Optional[int] = None


class ProjectResponse(ProjectBase):
    id: int
    status: int
    created_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(PaginatedResponse):
    items: List[ProjectResponse] = []


# ===== 任务相关 =====
class TaskBase(BaseModel):
    name: str
    project_id: int
    venv_id: Optional[int] = None
    description: Optional[str] = None
    schedule_type: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    scheduled_time: Optional[datetime] = None
    random_start_hour: Optional[int] = Field(None, ge=0, le=22, description="随机调度开始小时 (0-22)")
    random_end_hour: Optional[int] = Field(None, ge=1, le=23, description="随机调度结束小时 (1-23)")
    timeout_seconds: int = 3600
    retry_count: int = 0
    retry_interval: int = 60
    command: Optional[str] = None
    use_proxy: int = 0
    proxy_policy: str = "direct"  # fail/direct/wait
    allow_parallel: int = 0
    max_instances: int = 1


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[int] = None
    venv_id: Optional[int] = None
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    random_start_hour: Optional[int] = Field(None, ge=0, le=22)
    random_end_hour: Optional[int] = Field(None, ge=1, le=23)
    timeout_seconds: Optional[int] = None
    retry_count: Optional[int] = None
    retry_interval: Optional[int] = None
    command: Optional[str] = None
    use_proxy: Optional[int] = None
    proxy_policy: Optional[str] = None
    allow_parallel: Optional[int] = None
    max_instances: Optional[int] = None
    status: Optional[int] = None


class TaskResponse(TaskBase):
    id: int
    status: int
    created_at: datetime

    class Config:
        from_attributes = True


class TaskListResponse(PaginatedResponse):
    items: List[TaskResponse] = []


# ===== 执行记录相关 =====
class ExecutionResponse(BaseModel):
    id: int
    task_id: int
    trigger_type: str
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ExecutionListResponse(PaginatedResponse):
    items: List[ExecutionResponse] = []


# ===== 节点相关 =====
class NodeBase(BaseModel):
    name: str
    host: str
    port: int = 8080
    token: Optional[str] = None


class NodeCreate(NodeBase):
    pass


class NodeResponse(NodeBase):
    id: int
    os_type: Optional[str] = None
    status: str = "offline"
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    last_heartbeat: Optional[datetime] = None

    class Config:
        from_attributes = True


class NodeListResponse(PaginatedResponse):
    items: List[NodeResponse] = []


# ===== 代理相关 =====
class ProxyBase(BaseModel):
    ip: str
    port: int
    protocol: str = "http"
    username: Optional[str] = None
    password: Optional[str] = None


class ProxyCreate(ProxyBase):
    pass


class ProxyImport(BaseModel):
    proxies: List[str]
    protocol: str = "http"


class ProxyResponse(ProxyBase):
    id: int
    score: int = 50
    response_time: Optional[int] = None
    status: int = 1
    last_check_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProxyListResponse(PaginatedResponse):
    items: List[ProxyResponse] = []


class ProxyGetResponse(BaseModel):
    proxy: str


# ===== 仪表盘相关 =====
class DashboardOverview(BaseModel):
    total_projects: int = 0
    total_tasks: int = 0
    today_executions: int = 0
    success_rate: float = 0
    online_nodes: int = 0
    available_proxies: int = 0


# ===== 系统配置相关 =====


class SystemConfigBase(BaseModel):
    config_key: str
    config_value: Optional[str] = None
    description: Optional[str] = None


class SystemConfigUpdate(BaseModel):
    config_key: str
    config_value: str


class SystemConfigResponse(SystemConfigBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemConfigListResponse(BaseModel):
    items: List[SystemConfigResponse] = []
