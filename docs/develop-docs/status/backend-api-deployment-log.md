# 后端 API 开发与部署日志

本文档记录 DramePulse 后端 API、MySQL、OSS 和 ECS 云端部署的阶段性进展。它只记录已经完成和验证过的事实，不替代架构设计文档。

## 2026-05-22

### 已完成

- 新增 FastAPI 后端，代码入口位于 `services/api/`。
- 新增后端基础接口：
  - `GET /api/health`
  - `GET /api/videos`
  - `GET /api/videos/{video_id}`
  - `GET /api/videos/{video_id}/stream`
  - `POST /api/playback-events`
- 完成阿里云 MySQL 连接验证。
- 初始化 MySQL 业务库和核心表：
  - `videos`
  - `playback_events`
- 完成阿里云 OSS 连接验证。
- 从 OSS Bucket `dramepulse` 导入 24 个 `.mp4` 视频对象元数据到 MySQL。
- 视频文件本体继续保存在 OSS，MySQL 只保存视频元数据和 OSS object key。
- 本地 `/api/videos/ep_01/stream` 验证通过。
- 本地 Range 请求验证通过：
  - 返回 `206 Partial Content`
  - 返回 `Content-Type: video/mp4`
  - 返回 `Content-Disposition: inline`
  - 返回 `Accept-Ranges: bytes`
  - 返回 `Content-Range`
- 完成 ECS 云端部署。
- ECS 上 FastAPI 服务监听 `0.0.0.0:8000`。
- 阿里云安全组入方向放行 `8000/8000`。
- ECS 系统内 `firewalld` 放行 `8000/tcp`。
- 公网访问可用。

### 云端资源状态

#### MySQL

- 使用阿里云 RDS MySQL。
- 当前后端已能连接 MySQL。
- `videos` 表已保存 `ep_01` 到 `ep_24` 共 24 条视频元数据。
- `playback_events` 表用于保存播放反馈事件。
- 当前已验证 `pause` 类型播放事件可以写入。

#### OSS

- 使用阿里云 OSS Bucket `dramepulse`。
- OSS 中保存真实短剧视频文件。
- 当前已验证后端可以读取 OSS object，并按 Range 拉取视频片段。
- 由于 OSS 默认域名访问视频可能触发下载行为，当前不让前端直接访问 OSS 默认 URL，而是通过 FastAPI `/stream` 接口代理播放。

#### ECS

- 使用阿里云 ECS 部署 FastAPI 后端。
- 当前公网 IP：`39.96.219.88`。
- 后端部署目录：`/opt/dramepulse/DramePulse`。
- 当前 API Base URL：

```text
http://39.96.219.88:8000
```

### 已验证接口

健康检查：

```text
GET http://39.96.219.88:8000/api/health
```

视频列表：

```text
GET http://39.96.219.88:8000/api/videos
```

视频播放流：

```text
GET http://39.96.219.88:8000/api/videos/ep_01/stream
```

Range 请求示例：

```bash
curl -v -H "Range: bytes=0-1023" \
  -o /tmp/ep_01_head.bin \
  http://127.0.0.1:8000/api/videos/ep_01/stream
```

已验证返回：

```text
HTTP/1.1 206 Partial Content
content-type: video/mp4
content-disposition: inline
content-length: 1024
content-range: bytes 0-1023/121401222
```

### 当前前端对接方式

前端可先调用：

```text
GET /api/videos
```

拿到视频列表后，将 `stream_url` 拼接 API Base URL 作为播放器视频地址。

示例：

```text
http://39.96.219.88:8000/api/videos/ep_01/stream
```

当前播放器 Demo 仍然使用本地 fixture 和本地视频资源，尚未改为调用云端 API。


## 2026-05-23

### Local-first collaboration mode

The backend now supports two runtime modes behind the same public API:

```text
DRAMEPULSE_MODE=local
DRAMEPULSE_MODE=cloud
```

Shared API paths are unchanged:

```text
GET  /api/health
GET  /api/videos
GET  /api/videos/{video_id}
GET  /api/videos/{video_id}/stream
POST /api/playback-events
```

Local mode is the default for team development after cloning the repository:

- Video file: `demo_video.mp4`
- SQLite database: `dramepulse.sqlite`
- Init command: `python -m services.api.scripts.init_local_dev`
- Local API: `http://127.0.0.1:8000`
- Local video row: `video_id=demo_ep01`, `oss_object_key=demo_video.mp4`, `source=local`

Cloud mode keeps using Aliyun RDS MySQL and Aliyun OSS:

- ECS API: `http://39.96.219.88:8000`
- ECS service: `dramepulse-api`
- Service manager: `systemd`
- Cloud video rows are loaded from MySQL and video bytes are proxied from OSS through `/stream`.

### Frontend switching rule

The player demo now uses one frontend API base URL:

```text
apps/player-demo/src/config/api.ts
```

Local:

```ts
export const API_BASE_URL = "http://127.0.0.1:8000";
```

Cloud:

```ts
export const API_BASE_URL = "http://39.96.219.88:8000";
```

The frontend requests `GET /api/videos`, takes the first returned `stream_url`, and plays `{API_BASE_URL}{stream_url}`. It no longer needs to hard-code `demo_ep01` for local mode or `ep_01` for cloud mode.

### Collaboration workflow

- Teammates can clone the repository and run the backend locally without `.env`, MySQL, or OSS credentials.
- Local debugging reads `dramepulse.sqlite`, streams `demo_video.mp4`, and writes playback events back to SQLite.
- The maintainer can set `DRAMEPULSE_MODE=cloud` locally to verify cloud MySQL/OSS behavior.
- After cloud verification, deploy the backend code to ECS and restart `dramepulse-api`.
- Remote teammates who want cloud videos only need to change frontend `API_BASE_URL` to the ECS API address.

### Verification

Backend checks passed locally:

```text
python -m pytest tests\test_api_routes.py tests\test_api_oss_client.py
16 passed
```

Python syntax checks passed for the modified backend modules and local init script.
