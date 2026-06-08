# VedioRAG

VedioRAG is a small LlamaIndex + Chroma service for short-drama plot Q&A. It ingests one `video-analyzer` result directory and stores spoiler-safe RAG chunks with episode/time metadata.

## Install

```powershell
cd D:\XuPlace\bytedance\project\Vedio\video-analyzer\vediorag
pip install -r requirements.txt
```

Set environment variables:

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_API_BASE="https://vip.auto-code.net/v1"
$env:OPENAI_MODEL="gpt-5.4"
$env:OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
$env:CHROMA_DIR="D:\XuPlace\bytedance\project\Vedio\video-analyzer\vediorag\data\chroma"
```

## Ingest one episode

```powershell
python -m app.ingest --input ..\ui_data\results\a129b27e-4c53-4f4e-b585-b831473c8b17 --series-id demo-drama --episode 1
```

The ingester reads:

- `analysis.json`
- `transcript.json`
- `frame_analyses.jsonl`
- `fusion_result.md`

It writes Chroma data to `CHROMA_DIR`.

## Run API

```powershell
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health`
- `POST /ingest`
- `POST /ask`
- `GET /collections`

Example ask request:

```json
{
  "question": "皇帝为什么要测试权贵子弟？",
  "series_id": "demo-drama",
  "current_episode": 1,
  "current_time": 9999
}
```

## Spoiler-safe retrieval

Every chunk stores:

- `series_id`
- `episode`
- `start_time`
- `end_time`
- `source_type`
- `source_file`
- `session_id`

`/ask` only retrieves prior episodes and chunks whose `end_time <= current_time` in the current episode. `fusion_result.md` is stored as `episode_summary` with its time set to episode end, so it is only visible after the user reaches the end.

## ECS migration checklist

Copy these to ECS:

- `vediorag/`
- analyzed result directories under `ui_data/results/<session_id>/` if you want to re-ingest
- or existing `vediorag/data/chroma/` if you want to query without re-ingesting
- environment variables: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `CHROMA_DIR`

ECS needs Python 3.10+ and:

```bash
pip install -r vediorag/requirements.txt
```

It does not need FFmpeg, Whisper, or Torch unless the ECS server also runs the video analysis pipeline.
