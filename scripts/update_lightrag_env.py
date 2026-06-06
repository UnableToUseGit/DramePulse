from __future__ import annotations

from pathlib import Path


UPDATES = {
    "STORY_QA_BACKEND": "lightrag",
    "LIGHTRAG_WORKING_ROOT": "data/story_qa",
    "LIGHTRAG_QUERY_MODE": "hybrid",
    "LIGHTRAG_ENABLE_RERANK": "false",
    "LIGHTRAG_TOP_K": "20",
    "LIGHTRAG_CHUNK_TOP_K": "10",
    "LIGHTRAG_COSINE_THRESHOLD": "0.0",
    "LIGHTRAG_MAX_ENTITY_TOKENS": "6000",
    "LIGHTRAG_MAX_RELATION_TOKENS": "8000",
    "LIGHTRAG_MAX_TOTAL_TOKENS": "30000",
    "LIGHTRAG_RESPONSE_TYPE": "一句话短回答，最多60个中文字，不要引用来源，不要输出References，不要输出思考过程",
}


def main() -> int:
    path = Path(".env")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in UPDATES:
            output.append(f"{key}={UPDATES[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in UPDATES.items():
        if key not in seen:
            output.append(f"{key}={value}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
