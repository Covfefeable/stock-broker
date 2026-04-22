# Stock Broker

AI 量化策略平台基础框架，按 `api/`、`web/`、`docker/` 三段式组织。

## 结构

```text
api/      Flask API 服务，使用 uv 管理依赖
web/      Next.js App Router 前端
docker/   Docker Compose 和环境变量模板
```

## 本地开发

启动基础设施：

```bash
cd docker
cp .env.example .env
docker compose --env-file .env -f docker-compose.dev.yml up -d
```

启动 API：

```bash
cd api
cp .env.example .env
uv sync
uv run flask --app app run --host 0.0.0.0 --port 8000 --debug
```

启动前端：

```bash
cd web
cp .env.example .env.local
pnpm install
pnpm run dev
```

完整容器栈：

```bash
cd docker
docker compose --env-file .env -f docker-compose.yml up --build
```
