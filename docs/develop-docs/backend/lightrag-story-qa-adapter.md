# LightRAG Story Q&A Adapter

LightRAG is integrated as an optional backend for `/api/story-qa/*`. DramePulse keeps the public API stable and uses LightRAG only as an internal query engine.

## Local setup

Install LightRAG into the `Flask` conda environment:

```powershell
conda run -n Flask python -m pip install -e D:\XuProject\KG_RAG\LightRAG-main\LightRAG-main
```

If `conda run` fails because of a Windows temporary-file lock, use the environment interpreter directly:

```powershell
C:\Users\NSSC\.conda\envs\Flask\python.exe -m pip install -e D:\XuProject\KG_RAG\LightRAG-main\LightRAG-main
```

Verify imports:

```powershell
conda run -n Flask python -c "from lightrag import LightRAG, QueryParam; from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed; print('ok')"
```

## Data migration

Build or update the knowledge graph offline in the LightRAG project. Copy the full working directory, not only the GraphML file:

```text
from: D:\XuProject\KG_RAG\LightRAG-main\LightRAG-main\rag_storage\*
to:   data/story_qa/demo-drama/episode-001/lightrag/
```

The current demo working directory was generated from `gpt还原剧本.txt` and contains one processed document with four chunks, 35 entities, and 21 relations.

## Runtime config

```env
STORY_QA_BACKEND=lightrag
LIGHTRAG_WORKING_DIR=data/story_qa/demo-drama/episode-001/lightrag
LIGHTRAG_QUERY_MODE=hybrid
LIGHTRAG_ENABLE_RERANK=false
LIGHTRAG_EMBEDDING_MODEL=text-embedding-3-small
LIGHTRAG_EMBEDDING_DIM=1536
LIGHTRAG_EMBEDDING_API_BASE=https://api.openai.com/v1
LIGHTRAG_EMBEDDING_API_KEY=
LIGHTRAG_EMBEDDING_SEND_DIM=false
OPENAI_API_KEY=
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`LIGHTRAG_EMBEDDING_*` must match the embedding backend used when the working directory was built. A working directory built with 1024-dimensional embeddings must be served with `LIGHTRAG_EMBEDDING_DIM=1024`.

When `STORY_QA_BACKEND=chroma`, DramePulse uses the existing Chroma/LlamaIndex backend.

## Boundaries

The LightRAG backend does not run online KG extraction. `/api/story-qa/ingest` only validates that a prebuilt LightRAG working directory exists.

The current demo index covers the first three episodes as a whole, so it cannot strictly enforce `current_time` spoiler filtering within an episode. Strict spoiler control requires generating separate LightRAG working directories by episode or playback time bucket.

## Frontend player usage

`apps/player-demo` exposes Story Q&A from the right-side player rail. Users can open a bottom sheet while the video continues playing, enter a plot question, or tap one of the quick prompts.

The frontend sends:

```http
POST /api/story-qa/ask
```

with the current video context:

```json
{
  "question": "刚才发生了什么？",
  "series_id": "current-series-or-video-id",
  "current_episode": 1,
  "current_time": 22.5
}
```

The player does not call LightRAG directly. It only depends on DramePulse's stable Story Q&A API; `STORY_QA_BACKEND=lightrag` is a backend deployment choice.
