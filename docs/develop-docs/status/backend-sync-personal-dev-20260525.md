# personal-dev-20260525 后端同步状态

本文记录 `feature/personal-dev-20260525` 分支中，后端相关内容同步到 `integration/backend-personal-dev-20260525` 的状态。

当前同步提交：

```text
a6a339d Sync backend APIs from personal dev branch
```

说明：这些内容目前在 integration 分支中，还没有合入 `main`。

## 已同步内容

### 后端 API

- `GET /api/feed/home`
- `GET /api/series`
- `GET /api/series/{series_id}/episodes`
- `GET /api/series/{series_id}/episodes/{episode_no}`
- `GET /api/videos/{video_id}/playback-assets`
- 管理后台相关 API：登录、内容管理、Dashboard
- Watch Assistant 相关 API
- Story Q&A 的 LightRAG 后端更新

### 后端实现文件

- `services/api/admin_auth.py`
- `services/api/repositories/admin_content.py`
- `services/api/repositories/admin_dashboard.py`
- `services/api/routers/admin.py`
- `services/api/routers/feed.py`
- `services/api/routers/series.py`
- `services/api/routers/watch_assistant.py`
- `services/api/watch_assistant/`
- `services/api/schemas.py` 中新增的返回结构
- `services/api/story_qa/service.py` 中 LightRAG 相关更新
- `services/api/repositories/videos.py` 中 feed、series、playback assets 相关查询逻辑

### 配套脚本和配置

- `.env.example`
- `README.md`
- `pyproject.toml`
- `requirements.txt`
- `scripts/smoke_lightrag_story_qa.py`
- `scripts/update_lightrag_env.py`
- `services/api/scripts/prepare_danmaku_storage_experiment.py`

### 后端测试

- `tests/test_api_routes.py`
- `tests/test_api_story_qa.py`
- `tests/test_api_admin_auth.py`
- `tests/test_api_admin_content.py`
- `tests/test_api_admin_dashboard.py`
- `tests/test_api_watch_assistant.py`

已运行验证：

```bash
PYTHONPATH=. pytest tests/test_api_routes.py tests/test_api_story_qa.py tests/test_api_admin_auth.py tests/test_api_admin_content.py tests/test_api_admin_dashboard.py tests/test_api_watch_assistant.py tests/test_video_repository_story_assets.py tests/test_api_dev_logs.py -q
```

结果：

```text
67 passed
```

## 已同步但没有完全照搬的内容

这些地方从队友分支同步了后端能力，但保留了 `main` 上已有功能：

- `services/api/main.py`
  - 保留 `CORSMiddleware`
  - 保留 `dev_logs` router
  - 保留 `/storyboards` 静态资源挂载
  - 同时加入 admin、feed、series、watch assistant 和 Story Q&A warmup
- `services/api/config.py`
  - 保留 `storyboard_root`
  - 保留 `story_chapter_output_root`
  - 同时加入 LightRAG 和 Watch Assistant 新配置
- `services/api/routers/videos.py`
  - 保留前端当前需要的 `GET /api/videos/{video_id}/storyboard`
  - 同时加入 `GET /api/videos/{video_id}/playback-assets`
- `services/api/repositories/videos.py`
  - 保留 storyboard URL 兼容处理
  - 同时加入 feed、series、playback assets 查询逻辑

## 尚未同步内容

### 明确暂不合入的前端内容

- `apps/player-demo/` 的大规模重构
- `apps/admin-dashboard/` 管理后台前端
- `apps/annotation-tool/` 的改动
- `apps/story-chapter-viewer/` 的删除

原因：当前先只同步后端，避免覆盖播放器前端近期已经完成的云端适配。

### 未同步的数据和示例资产

- `data/story_qa/demo-drama/episode-001/lightrag/`

原因：这是 LightRAG 示例数据，不是后端 API 代码。是否需要合入要单独决定。

### 未同步的脚本删除和 pipeline 清理

队友分支删除了一批旧脚本和 pipeline 文件，这次没有同步这些删除：

- storyboard 生成相关脚本
- story chapter 生成相关脚本
- scene detection 相关脚本
- highlight candidate generation 相关脚本
- `scripts/check_cloud_api.sh`

原因：这些不属于本轮后端 API 同步范围，其中 `scripts/check_cloud_api.sh` 在当前工作区还有本地改动，不能直接删除。

### 未同步的非 API 测试改动

- annotation tool 测试改动
- transcription 测试改动
- pipeline / storyboard / story chapter 相关测试删除

原因：这些不是后端 API 路由验证范围，后续如果要同步 pipeline 或工具链清理，再单独处理。

### 队友分支中被我们保留差异的后端文件

这些后端文件和 `feature/personal-dev-20260525` 仍有差异，但不是遗漏：

- `services/api/main.py`
- `services/api/config.py`
- `services/api/repositories/videos.py`
- `services/api/routers/videos.py`
- `services/api/routers/dev_logs.py`

原因：队友分支删除或缺少部分 `main` 现有能力；integration 分支保留了这些能力以兼容当前前端和本地开发观测。

## 后续建议

如果要继续推进，建议顺序是：

1. 先把 `integration/backend-personal-dev-20260525` 作为后端同步分支评审；
2. 确认后再合入 `main`；
3. 再单独评估是否同步 admin dashboard 前端、player demo 重构和 pipeline 清理。
