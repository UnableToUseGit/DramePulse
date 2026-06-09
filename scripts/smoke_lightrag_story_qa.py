from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]


QUESTIONS = [
    ("beiwang", "\u6c88\u5fc3\u5982\u662f\u771f\u7684\u8df3\u6cb3\u6b7b\u4e86\u5417\uff1f"),
    ("beiwang", "\u6c88\u5fc3\u5982 \u9648\u5929\u7fd4 \u5f20\u854a"),
    ("jialijiawai", "\u9648\u6d77\u6e05\u7ed9\u8521\u6653\u8273\u7684\u5b58\u6298\u4f59\u989d\u662f\u591a\u5c11\uff1f"),
    ("jialijiawai", "\u6d3b\u671f\u50a8\u84c4\u5b58\u6298 \u6d77\u9e25\u724c\u673a\u68b0\u5973\u8868"),
]

NO_CONFIRM = "\u5f53\u524d\u89c2\u770b\u8fdb\u5ea6\u5185\u65e0\u6cd5\u786e\u8ba4"


def configure_environment(lightrag_root: Path) -> None:
    if load_dotenv is not None:
        load_dotenv(lightrag_root / ".env")

    sys.path.insert(0, str(lightrag_root))
    os.environ["STORY_QA_BACKEND"] = "lightrag"
    os.environ["LIGHTRAG_WORKING_ROOT"] = "data/story_qa"
    os.environ["LIGHTRAG_QUERY_MODE"] = "hybrid"
    os.environ["LIGHTRAG_ENABLE_RERANK"] = "false"
    os.environ["LIGHTRAG_TOP_K"] = "20"
    os.environ["LIGHTRAG_CHUNK_TOP_K"] = "10"
    os.environ["LIGHTRAG_COSINE_THRESHOLD"] = "0.0"
    os.environ["LIGHTRAG_MAX_ENTITY_TOKENS"] = "6000"
    os.environ["LIGHTRAG_MAX_RELATION_TOKENS"] = "8000"
    os.environ["LIGHTRAG_MAX_TOTAL_TOKENS"] = "30000"
    os.environ["LIGHTRAG_RESPONSE_TYPE"] = "\u4e00\u53e5\u8bdd\u77ed\u56de\u7b54\uff0c\u6700\u591a60\u4e2a\u4e2d\u6587\u5b57\uff0c\u4e0d\u8981\u5f15\u7528\u6765\u6e90\uff0c\u4e0d\u8981\u8f93\u51faReferences\uff0c\u4e0d\u8981\u8f93\u51fa\u601d\u8003\u8fc7\u7a0b"

    if "LLM_MODEL" in os.environ:
        os.environ["OPENAI_MODEL"] = os.environ["LLM_MODEL"]
    if "LLM_BINDING_HOST" in os.environ:
        os.environ["OPENAI_API_BASE"] = os.environ["LLM_BINDING_HOST"]
    if "LLM_BINDING_API_KEY" in os.environ:
        os.environ["OPENAI_API_KEY"] = os.environ["LLM_BINDING_API_KEY"]
    if "EMBEDDING_MODEL" in os.environ:
        os.environ["LIGHTRAG_EMBEDDING_MODEL"] = os.environ["EMBEDDING_MODEL"]
    if "EMBEDDING_DIM" in os.environ:
        os.environ["LIGHTRAG_EMBEDDING_DIM"] = os.environ["EMBEDDING_DIM"]
    if "EMBEDDING_BINDING_HOST" in os.environ:
        os.environ["LIGHTRAG_EMBEDDING_API_BASE"] = os.environ["EMBEDDING_BINDING_HOST"]
    if "EMBEDDING_BINDING_API_KEY" in os.environ:
        os.environ["LIGHTRAG_EMBEDDING_API_KEY"] = os.environ["EMBEDDING_BINDING_API_KEY"]
    os.environ["LIGHTRAG_EMBEDDING_SEND_DIM"] = "false"


def assert_expected(results: dict[tuple[str, int, str], str]) -> None:
    beiwang_ep1 = results[("beiwang", 1, QUESTIONS[0][1])]
    if NO_CONFIRM not in beiwang_ep1 and any(term in beiwang_ep1 for term in ["\u9648\u5929\u7fd4", "\u5f20\u854a", "\u5047\u88c5", "\u9634\u8c0b"]):
        raise AssertionError(f"beiwang episode 1 leaked future plot: {beiwang_ep1}")

    beiwang_ep5 = results[("beiwang", 5, QUESTIONS[0][1])]
    if NO_CONFIRM in beiwang_ep5:
        raise AssertionError(f"beiwang episode 5 failed to answer: {beiwang_ep5}")

    jialijiawai_ep1 = results[("jialijiawai", 1, QUESTIONS[2][1])]
    if "3000" in jialijiawai_ep1:
        raise AssertionError(f"jialijiawai episode 1 leaked balance: {jialijiawai_ep1}")

    jialijiawai_ep5 = results[("jialijiawai", 5, QUESTIONS[2][1])]
    if "3000" not in jialijiawai_ep5:
        raise AssertionError(f"jialijiawai episode 5 did not answer balance: {jialijiawai_ep5}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lightrag-root",
        default=r"D:\XuProject\KG_RAG\LightRAG-main\LightRAG-main",
        help="Local LightRAG source checkout containing .env and lightrag package.",
    )
    parser.add_argument("--no-assert", action="store_true", help="Print answers without enforcing smoke expectations.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    configure_environment(Path(args.lightrag_root))

    from services.api.story_qa import service

    results: dict[tuple[str, int, str], str] = {}
    for series_id, question in QUESTIONS:
        for episode in (1, 5):
            answer = service.ask(question, series_id, episode, 9999)["answer"]
            results[(series_id, episode, question)] = answer
            print(f"[{series_id} ep{episode}] {question}")
            print(answer)
            print()

    if not args.no_assert:
        assert_expected(results)
        print("LightRAG story QA smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
