-- =============================================
-- CrawlOps 数据库初始化脚本
-- 包含表结构、系统角色与本地默认管理员。
-- =============================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = utf8mb4_unicode_ci;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20),
    avatar VARCHAR(255),
    status TINYINT DEFAULT 1 COMMENT '0禁用 1正常',
    last_login_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 角色表
CREATE TABLE IF NOT EXISTS roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    code VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- 用户角色关联表
CREATE TABLE IF NOT EXISTS user_roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_role (user_id, role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

-- 虚拟环境表 (需要在 tasks 表之前创建，因为 tasks 引用 venvs)
CREATE TABLE IF NOT EXISTS venvs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    path VARCHAR(255) NOT NULL,
    python_version VARCHAR(20),
    description VARCHAR(255),
    status INT DEFAULT 1,
    install_status VARCHAR(20) DEFAULT 'idle' COMMENT 'idle/installing 安装状态',
    install_message VARCHAR(500) COMMENT '当前安装进度信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='虚拟环境表';

-- 项目表
CREATE TABLE IF NOT EXISTS projects (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    type VARCHAR(20) DEFAULT 'python',
    source_type VARCHAR(20) NOT NULL COMMENT 'upload/git',
    git_url VARCHAR(500),
    git_branch VARCHAR(100) DEFAULT 'main',
    entry_file VARCHAR(255),
    python_version VARCHAR(20) DEFAULT '3.10',
    status TINYINT DEFAULT 1,
    created_by BIGINT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='项目表';

-- 任务表
CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    project_id BIGINT NOT NULL,
    description TEXT,
    schedule_type VARCHAR(20) NOT NULL COMMENT 'once/cron/interval/random',
    cron_expression VARCHAR(100),
    interval_seconds INT,
    scheduled_time DATETIME,
    random_start_hour INT COMMENT '随机调度开始小时 (0-23)',
    random_end_hour INT COMMENT '随机调度结束小时 (0-23)',
    timeout_seconds INT DEFAULT 3600,
    retry_count INT DEFAULT 0,
    retry_interval INT DEFAULT 60,
    node_id BIGINT,
    command VARCHAR(500),
    arguments TEXT,
    env_vars TEXT,
    use_proxy TINYINT DEFAULT 0,
    proxy_policy VARCHAR(20) DEFAULT 'direct' COMMENT 'fail/direct/wait',
    allow_parallel TINYINT DEFAULT 0,
    max_instances INT DEFAULT 1,
    status TINYINT DEFAULT 1,
    created_by BIGINT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    venv_id BIGINT,
    INDEX idx_project_id (project_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- 任务执行记录表
CREATE TABLE IF NOT EXISTS task_executions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL,
    node_id BIGINT,
    trigger_type VARCHAR(20) NOT NULL COMMENT 'schedule/manual/retry',
    status VARCHAR(20) NOT NULL COMMENT 'pending/running/success/failed/timeout',
    retry_attempt INT DEFAULT 0 COMMENT '当前重试次数 (0=首次执行)',
    start_time DATETIME,
    end_time DATETIME,
    duration INT COMMENT '执行时长(秒)',
    exit_code INT,
    error_message TEXT,
    result_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_status (status),
    INDEX idx_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务执行记录表';

-- 任务依赖关系表
CREATE TABLE IF NOT EXISTS task_dependencies (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL,
    depends_on_task_id BIGINT NOT NULL,
    condition_type VARCHAR(20) DEFAULT 'success',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_dependency (task_id, depends_on_task_id),
    INDEX idx_task_id (task_id),
    INDEX idx_depends_on (depends_on_task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务依赖关系表';

-- 节点表
CREATE TABLE IF NOT EXISTS nodes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INT DEFAULT 8080,
    token VARCHAR(255),
    os_type VARCHAR(20),
    status VARCHAR(20) DEFAULT 'offline',
    cpu_usage DECIMAL(5,2),
    memory_usage DECIMAL(5,2),
    disk_usage DECIMAL(5,2),
    last_heartbeat DATETIME,
    deleted TINYINT DEFAULT 0 COMMENT '0:未删除 1:已删除',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='节点表';

-- 节点性能指标历史表
CREATE TABLE IF NOT EXISTS node_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    node_id BIGINT NOT NULL,
    cpu_usage DECIMAL(5,2),
    memory_usage DECIMAL(5,2),
    disk_usage DECIMAL(5,2),
    network_sent BIGINT COMMENT '累计发送字节数',
    network_recv BIGINT COMMENT '累计接收字节数',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_node_time (node_id, created_at),
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='节点性能指标历史表';

-- 代理表
CREATE TABLE IF NOT EXISTS proxies (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ip VARCHAR(50) NOT NULL,
    port INT NOT NULL,
    protocol VARCHAR(10) DEFAULT 'http',
    username VARCHAR(100),
    password VARCHAR(100),
    country VARCHAR(50),
    region VARCHAR(50),
    source VARCHAR(50),
    score INT DEFAULT 50,
    response_time INT,
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,
    last_check_time DATETIME,
    status TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ip_port (ip, port),
    INDEX idx_status (status),
    INDEX idx_score (score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理表';

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    description VARCHAR(255),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- 通知配置表
CREATE TABLE IF NOT EXISTS notification_configs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    config TEXT NOT NULL,
    is_default TINYINT DEFAULT 0,
    status TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通知配置表';

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    username VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id BIGINT,
    resource_name VARCHAR(100),
    detail TEXT,
    ip VARCHAR(50),
    user_agent VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审计日志表';


-- =============================================
-- 初始数据
-- =============================================

-- 默认角色
INSERT INTO roles (name, code, description) VALUES
('超级管理员', 'super_admin', '系统最高权限'),
('项目管理员', 'project_admin', '管理指定项目'),
('普通用户', 'user', '查看和触发任务')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- 默认管理员：admin / 123456。仅在初始化空数据卷时写入，不会覆盖已有账号。
INSERT INTO users (username, password_hash, status) VALUES
('admin', '$2b$12$C076o59b6j3vIid/qXdha.Z5joxP1OJIATd5/FFdGwteMtKnHS20y', 1)
ON DUPLICATE KEY UPDATE username=VALUES(username);

INSERT INTO user_roles (user_id, role_id)
SELECT users.id, roles.id
FROM users, roles
WHERE users.username = 'admin' AND roles.code = 'super_admin'
ON DUPLICATE KEY UPDATE user_id=VALUES(user_id);

-- 默认系统配置
INSERT INTO system_configs (config_key, config_value, description) VALUES
('max_upload_size_mb', '100', '项目文件最大上传大小(MB)'),
('proxy_retry_count', '3', '代理获取重试次数'),
('proxy_retry_interval', '5', '代理获取重试间隔(秒)'),
('token_expire_hours', '2', 'Access Token有效期(小时)'),
('refresh_token_expire_days', '7', 'Refresh Token有效期(天)'),
('proxy_crawl_interval', '10', '代理采集任务间隔(分钟)'),
('proxy_verify_interval', '5', '代理验证任务间隔(分钟)')
ON DUPLICATE KEY UPDATE config_key=VALUES(config_key);
