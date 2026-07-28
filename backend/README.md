# CrawlOps Backend

FastAPI 后端服务。运行前必须提供 `DATABASE_URL` 和 `REDIS_URL`；Docker 部署会从根目录 `.env` 注入这些配置。

```bash
poetry install
poetry run uvicorn main:app --reload
```

测试使用内存 SQLite：

```bash
poetry run pytest
```

Docker 首次初始化数据卷时，会由根目录 `init.sql` 直接写入本地默认管理员 `admin / 123456`。密码以 bcrypt 哈希形式保存；已有账号不会被覆盖。
