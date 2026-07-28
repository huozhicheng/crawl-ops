# Security Policy

## Supported version

当前 `main` 分支是唯一受支持版本。

## Reporting a vulnerability

请不要在公开 issue 中披露可利用漏洞、密钥或私有部署信息。请通过仓库启用后的 GitHub 私密漏洞报告功能提交复现步骤、影响范围与修复建议；维护者会在确认后协调修复与披露。

部署者应：

- 使用唯一、强度足够的数据库、Redis、管理员和 Worker 注册凭据；
- 将 MySQL、Redis 与 Worker 通道放在私有网络或 TLS 保护之下；
- 仅授予可信用户控制台访问权；
- 定期更新镜像和依赖。
