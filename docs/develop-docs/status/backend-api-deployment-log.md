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

### 本地优先协作模式

后端现在支持两种运行模式，并且两种模式共用同一套对外 API：

```text
DRAMEPULSE_MODE=local
DRAMEPULSE_MODE=cloud
```

对外接口路径保持不变：

```text
GET  /api/health
GET  /api/videos
GET  /api/videos/{video_id}
GET  /api/videos/{video_id}/stream
POST /api/playback-events
```

本地模式是团队 clone 仓库后的默认开发方式：

- 视频文件：`demo_video.mp4`
- SQLite 数据库：`dramepulse.sqlite`
- 初始化命令：`python -m services.api.scripts.init_local_dev`
- 本地 API：`http://127.0.0.1:8000`
- 本地视频记录：`video_id=demo_ep01`，`oss_object_key=demo_video.mp4`，`source=local`

云端模式继续使用阿里云 RDS MySQL 和阿里云 OSS：

- ECS API：`http://39.96.219.88:8000`
- ECS 服务名：`dramepulse-api`
- 服务管理方式：`systemd`
- 云端视频元数据从 MySQL 读取，视频文件通过后端 `/stream` 接口从 OSS 代理读取。

### 前端切换规则

播放器 Demo 现在只通过一个前端 API Base URL 切换本地和云端：

```text
apps/player-demo/src/config/api.ts
```

本地：

```ts
export const API_BASE_URL = "http://127.0.0.1:8000";
```

云端：

```ts
export const API_BASE_URL = "http://39.96.219.88:8000";
```

前端会先请求 `GET /api/videos`，取返回列表中的第一条 `stream_url`，再播放 `{API_BASE_URL}{stream_url}`。因此前端不再需要在本地模式写死 `demo_ep01`，也不需要在云端模式写死 `ep_01`。

### 团队协作流程

- 同事 clone 仓库后，可以不配置 `.env`、MySQL 或 OSS 密钥，直接启动本地后端调试。
- 本地调试时，后端读取 `dramepulse.sqlite`，播放 `demo_video.mp4`，并把播放事件写回 SQLite。
- 维护者可以在本机设置 `DRAMEPULSE_MODE=cloud`，验证云端 MySQL/OSS 链路。
- 云端验证通过后，将后端代码部署到 ECS，并重启 `dramepulse-api` 服务。
- 远程同事如果想看云端视频，只需要把前端 `API_BASE_URL` 改成 ECS API 地址。

### 验证结果

本地后端测试已通过：

```text
python -m pytest tests\test_api_routes.py tests\test_api_oss_client.py
16 passed
```

已对修改后的后端模块和本地初始化脚本执行 Python 语法检查。
