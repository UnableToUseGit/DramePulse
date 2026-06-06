from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.story_qa import service


def make_lightrag_working_dir(root: str | Path, series_id: str, statuses: dict[str, object] | None = None) -> Path:
    working_dir = Path(root) / series_id / "lightrag"
    working_dir.mkdir(parents=True)
    (working_dir / "kv_store_doc_status.json").write_text(
        "{}" if statuses is None else json.dumps(statuses),
        encoding="utf-8",
    )
    return working_dir


class FakeNode:
    def __init__(self, text: str, metadata: dict[str, object], score: float | None = 0.8) -> None:
        self._text = text
        self.metadata = metadata
        self.score = score

    def get_text(self) -> str:
        return self._text


class StoryQaServiceTest(unittest.TestCase):
    def test_is_visible_allows_prior_episode_and_current_time_only(self) -> None:
        previous_episode = FakeNode("previous", {"episode": 1, "end_time": 9999})
        current_visible = FakeNode("visible", {"episode": 2, "end_time": 12.0})
        current_future = FakeNode("future", {"episode": 2, "end_time": 13.0})
        future_episode = FakeNode("future episode", {"episode": 3, "end_time": 1.0})

        self.assertTrue(service.is_visible(previous_episode, current_episode=2, current_time=12.0))
        self.assertTrue(service.is_visible(current_visible, current_episode=2, current_time=12.0))
        self.assertFalse(service.is_visible(current_future, current_episode=2, current_time=12.0))
        self.assertFalse(service.is_visible(future_episode, current_episode=2, current_time=12.0))

    def test_build_prompt_contains_spoiler_safe_constraints(self) -> None:
        prompt = service.build_prompt(
            "她为什么离开？",
            [FakeNode("她收到一封信。", {"source_type": "transcript", "episode": 1, "start_time": 8, "end_time": 10})],
        )

        self.assertIn("只能基于下方检索到的、用户当前观看进度内的资料回答", prompt)
        self.assertIn("当前观看进度内无法确认", prompt)
        self.assertIn("她收到一封信。", prompt)
        self.assertIn("问题：她为什么离开？", prompt)

    def test_summarize_collection_rows_groups_by_episode_and_source_type(self) -> None:
        summary = service.summarize_collection_rows(
            collection="dramepulse_story_qa",
            chroma_dir=Path("data/chroma"),
            ids=["1", "2", "3"],
            metadatas=[
                {"series_id": "demo", "episode": 1, "source_type": "transcript"},
                {"series_id": "demo", "episode": 1, "source_type": "frame_analysis"},
                {"series_id": "demo", "episode": 1, "source_type": "transcript"},
            ],
        )

        self.assertEqual(summary["total_documents"], 3)
        self.assertEqual(summary["episodes"][0]["series_id"], "demo")
        self.assertEqual(summary["episodes"][0]["episode"], 1)
        self.assertEqual(summary["episodes"][0]["documents"], 3)
        self.assertEqual(summary["episodes"][0]["source_types"]["transcript"], 2)
        self.assertEqual(summary["episodes"][0]["source_types"]["frame_analysis"], 1)

    def test_clean_lightrag_text_removes_references(self) -> None:
        answer = service._clean_lightrag_text(
            "Short answer.[1]\n\n### References\n\n- [1] gpt.txt"
        )

        self.assertEqual(answer, "Short answer.")

    def test_clean_lightrag_text_removes_think_blocks(self) -> None:
        answer = service._clean_lightrag_text(
            "<think>hidden reasoning</think>容遇是纪家长辈。"
        )

        self.assertEqual(answer, "容遇是纪家长辈。")


class StoryQaApiTest(unittest.TestCase):
    def setUp(self) -> None:
        service.reset_lightrag_cache_for_tests()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        service.reset_lightrag_cache_for_tests()

    def test_ask_returns_answer_and_sources(self) -> None:
        with patch(
            "services.api.routers.story_qa.service.ask",
            return_value={
                "answer": "当前观看进度内无法确认。",
                "sources": [
                    {
                        "score": 0.9,
                        "text": "她收到一封信。",
                        "metadata": {"series_id": "demo", "episode": 1},
                    }
                ],
            },
        ) as ask:
            response = self.client.post(
                "/api/story-qa/ask",
                json={
                    "question": "她为什么离开？",
                    "series_id": "demo",
                    "current_episode": 1,
                    "current_time": 12.0,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "当前观看进度内无法确认。")
        self.assertEqual(response.json()["sources"][0]["score"], 0.9)
        ask.assert_called_once_with("她为什么离开？", "demo", 1, 12.0)

    def test_ingest_returns_document_count(self) -> None:
        with patch(
            "services.api.routers.story_qa.service.ingest",
            return_value={
                "input_dir": "D:/tmp/result",
                "series_id": "demo",
                "episode": 1,
                "documents": 3,
                "by_type": {"transcript": 2, "episode_summary": 1},
                "chroma_dir": "data/chroma",
                "collection": "dramepulse_story_qa",
            },
        ) as ingest:
            response = self.client.post(
                "/api/story-qa/ingest",
                json={"input_dir": "D:/tmp/result", "series_id": "demo", "episode": 1},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["documents"], 3)
        ingest.assert_called_once_with(Path("D:/tmp/result"), "demo", 1)

    def test_collections_returns_summary(self) -> None:
        with patch(
            "services.api.routers.story_qa.service.collections",
            return_value={
                "collection": "dramepulse_story_qa",
                "chroma_dir": "data/chroma",
                "total_documents": 2,
                "episodes": [
                    {
                        "series_id": "demo",
                        "episode": 1,
                        "documents": 2,
                        "source_types": {"transcript": 2},
                    }
                ],
            },
        ):
            response = self.client.get("/api/story-qa/collections")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_documents"], 2)
        self.assertEqual(response.json()["episodes"][0]["source_types"]["transcript"], 2)

    def test_service_error_returns_400_without_stack_trace(self) -> None:
        with patch("services.api.routers.story_qa.service.ask", side_effect=RuntimeError("rag unavailable")):
            response = self.client.post(
                "/api/story-qa/ask",
                json={
                    "question": "她为什么离开？",
                    "series_id": "demo",
                    "current_episode": 1,
                    "current_time": 12.0,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "rag unavailable"})

    def test_lightrag_ask_returns_answer_with_empty_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            make_lightrag_working_dir(tmpdir, "demo-drama")
            fake_lightrag = types.ModuleType("lightrag")
            fake_llm = types.ModuleType("lightrag.llm")
            fake_openai = types.ModuleType("lightrag.llm.openai")
            fake_utils = types.ModuleType("lightrag.utils")
            query_params = []
            rag_instances = []

            class FakeQueryParam:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
                    query_params.append(kwargs)

            class FakeEmbeddingFunc:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeLightRAG:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
                    self.initialize_count = 0
                    self.finalize_count = 0
                    rag_instances.append(self)

                async def initialize_storages(self):
                    self.initialize_count += 1
                    return None

                async def aquery(self, question, param):
                    self.question = question
                    self.param = param
                    return "容遇是纪家长辈，也是前三集的核心人物。"

                async def finalize_storages(self):
                    self.finalize_count += 1
                    return None

            async def fake_complete(*args, **kwargs):
                return ""

            async def fake_embed(*args, **kwargs):
                return []

            fake_lightrag.LightRAG = FakeLightRAG
            fake_lightrag.QueryParam = FakeQueryParam
            fake_openai.openai_complete_if_cache = fake_complete
            fake_openai.openai_embed = fake_embed
            fake_utils.EmbeddingFunc = FakeEmbeddingFunc

            with patch.dict(
                sys.modules,
                {
                    "lightrag": fake_lightrag,
                    "lightrag.llm": fake_llm,
                    "lightrag.llm.openai": fake_openai,
                    "lightrag.utils": fake_utils,
                },
            ), patch.dict(
                "os.environ",
                {
                    "STORY_QA_BACKEND": "lightrag",
                    "LIGHTRAG_WORKING_ROOT": tmpdir,
                    "LIGHTRAG_QUERY_MODE": "hybrid",
                    "LIGHTRAG_ENABLE_RERANK": "false",
                    "LIGHTRAG_TOP_K": "6",
                    "LIGHTRAG_CHUNK_TOP_K": "4",
                    "LIGHTRAG_COSINE_THRESHOLD": "0.4",
                    "LIGHTRAG_MAX_ENTITY_TOKENS": "1800",
                    "LIGHTRAG_MAX_RELATION_TOKENS": "2400",
                    "LIGHTRAG_MAX_TOTAL_TOKENS": "6000",
                    "LIGHTRAG_RESPONSE_TYPE": "Single Paragraph",
                    "OPENAI_API_KEY": "test-key",
                },
            ):
                response = self.client.post(
                    "/api/story-qa/ask",
                    json={
                        "question": "容遇是谁？",
                        "series_id": "demo-drama",
                        "current_episode": 3,
                        "current_time": 9999,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "容遇是纪家长辈，也是前三集的核心人物。", "sources": []})

    def test_lightrag_reuses_instance_and_passes_speed_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            make_lightrag_working_dir(tmpdir, "demo-drama")
            fake_lightrag = types.ModuleType("lightrag")
            fake_llm = types.ModuleType("lightrag.llm")
            fake_openai = types.ModuleType("lightrag.llm.openai")
            fake_utils = types.ModuleType("lightrag.utils")
            query_params = []
            rag_instances = []

            class FakeQueryParam:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
                    query_params.append(kwargs)

            class FakeEmbeddingFunc:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeLightRAG:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
                    self.initialize_count = 0
                    self.finalize_count = 0
                    rag_instances.append(self)

                async def initialize_storages(self):
                    self.initialize_count += 1
                    return None

                async def aquery(self, question, param):
                    return "answer from lightrag"

                async def finalize_storages(self):
                    self.finalize_count += 1
                    return None

            async def fake_complete(*args, **kwargs):
                return ""

            async def fake_embed(*args, **kwargs):
                return []

            fake_lightrag.LightRAG = FakeLightRAG
            fake_lightrag.QueryParam = FakeQueryParam
            fake_openai.openai_complete_if_cache = fake_complete
            fake_openai.openai_embed = fake_embed
            fake_utils.EmbeddingFunc = FakeEmbeddingFunc

            with patch.dict(
                sys.modules,
                {
                    "lightrag": fake_lightrag,
                    "lightrag.llm": fake_llm,
                    "lightrag.llm.openai": fake_openai,
                    "lightrag.utils": fake_utils,
                },
            ), patch.dict(
                "os.environ",
                {
                    "STORY_QA_BACKEND": "lightrag",
                    "LIGHTRAG_WORKING_ROOT": tmpdir,
                    "LIGHTRAG_QUERY_MODE": "hybrid",
                    "LIGHTRAG_ENABLE_RERANK": "false",
                    "LIGHTRAG_TOP_K": "6",
                    "LIGHTRAG_CHUNK_TOP_K": "4",
                    "LIGHTRAG_COSINE_THRESHOLD": "0.4",
                    "LIGHTRAG_MAX_ENTITY_TOKENS": "1800",
                    "LIGHTRAG_MAX_RELATION_TOKENS": "2400",
                    "LIGHTRAG_MAX_TOTAL_TOKENS": "6000",
                    "LIGHTRAG_RESPONSE_TYPE": "Single Paragraph",
                    "OPENAI_API_KEY": "test-key",
                },
            ):
                first_response = self.client.post(
                    "/api/story-qa/ask",
                    json={
                        "question": "who is he?",
                        "series_id": "demo-drama",
                        "current_episode": 3,
                        "current_time": 9999,
                    },
                )
                second_response = self.client.post(
                    "/api/story-qa/ask",
                    json={
                        "question": "what just happened?",
                        "series_id": "demo-drama",
                        "current_episode": 3,
                        "current_time": 9999,
                    },
                )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.json(), {"answer": "answer from lightrag", "sources": []})
        self.assertEqual(len(rag_instances), 1)
        self.assertEqual(rag_instances[0].initialize_count, 1)
        self.assertEqual(rag_instances[0].finalize_count, 0)
        self.assertEqual(rag_instances[0].kwargs["top_k"], 6)
        self.assertEqual(rag_instances[0].kwargs["chunk_top_k"], 4)
        self.assertEqual(rag_instances[0].kwargs["cosine_threshold"], 0.4)
        self.assertEqual(rag_instances[0].kwargs["cosine_better_than_threshold"], 0.4)
        self.assertEqual(rag_instances[0].kwargs["max_entity_tokens"], 1800)
        self.assertEqual(rag_instances[0].kwargs["max_relation_tokens"], 2400)
        self.assertEqual(rag_instances[0].kwargs["max_total_tokens"], 6000)
        self.assertEqual(len(query_params), 2)
        self.assertEqual(query_params[0]["mode"], "hybrid")
        self.assertFalse(query_params[0]["enable_rerank"])
        self.assertEqual(query_params[0]["top_k"], 6)
        self.assertEqual(query_params[0]["chunk_top_k"], 4)
        self.assertEqual(query_params[0]["max_entity_tokens"], 1800)
        self.assertEqual(query_params[0]["max_relation_tokens"], 2400)
        self.assertEqual(query_params[0]["max_total_tokens"], 6000)
        self.assertEqual(query_params[0]["response_type"], "Single Paragraph")
        self.assertEqual(query_params[0]["current_chapter_id"], 3)
        self.assertEqual(query_params[1]["current_chapter_id"], 3)

    def test_lightrag_enhances_keywords_from_entity_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            working_dir = make_lightrag_working_dir(tmpdir, "demo-drama")
            (working_dir / "vdb_entities.json").write_text(
                json.dumps(
                    {
                        "data": [
                            {
                                "entity_name": "活期储蓄存折",
                                "content": "活期储蓄存折 余额是3000.00元",
                            },
                            {
                                "entity_name": "海鸥牌机械女表",
                                "content": "海鸥牌机械女表是结婚礼物",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fake_lightrag = types.ModuleType("lightrag")
            fake_llm = types.ModuleType("lightrag.llm")
            fake_openai = types.ModuleType("lightrag.llm.openai")
            fake_utils = types.ModuleType("lightrag.utils")
            query_params = []

            class FakeQueryParam:
                def __init__(self, **kwargs):
                    query_params.append(kwargs)

            class FakeEmbeddingFunc:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeLightRAG:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

                async def initialize_storages(self):
                    return None

                async def aquery(self, question, param):
                    return "answer from lightrag"

            async def fake_complete(*args, **kwargs):
                return ""

            async def fake_embed(*args, **kwargs):
                return []

            fake_lightrag.LightRAG = FakeLightRAG
            fake_lightrag.QueryParam = FakeQueryParam
            fake_openai.openai_complete_if_cache = fake_complete
            fake_openai.openai_embed = fake_embed
            fake_utils.EmbeddingFunc = FakeEmbeddingFunc

            with patch.dict(
                sys.modules,
                {
                    "lightrag": fake_lightrag,
                    "lightrag.llm": fake_llm,
                    "lightrag.llm.openai": fake_openai,
                    "lightrag.utils": fake_utils,
                },
            ), patch.dict(
                "os.environ",
                {
                    "STORY_QA_BACKEND": "lightrag",
                    "LIGHTRAG_WORKING_ROOT": tmpdir,
                    "LIGHTRAG_QUERY_MODE": "hybrid",
                    "LIGHTRAG_ENABLE_RERANK": "false",
                    "OPENAI_API_KEY": "test-key",
                },
            ):
                response = self.client.post(
                    "/api/story-qa/ask",
                    json={
                        "question": "陈海清给蔡晓艳的存折余额是多少？",
                        "series_id": "demo-drama",
                        "current_episode": 5,
                        "current_time": 9999,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("活期储蓄存折", query_params[0]["hl_keywords"])
        self.assertIn("活期储蓄存折", query_params[0]["ll_keywords"])
        self.assertEqual(query_params[0]["top_k"], 20)
        self.assertEqual(query_params[0]["chunk_top_k"], 10)
        self.assertEqual(query_params[0]["max_entity_tokens"], 6000)
        self.assertEqual(query_params[0]["max_relation_tokens"], 8000)
        self.assertEqual(query_params[0]["max_total_tokens"], 30000)
        self.assertEqual(query_params[0]["current_chapter_id"], 5)

    def test_lightrag_blocks_future_question_when_entity_name_is_mentioned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            working_dir = make_lightrag_working_dir(tmpdir, "demo-drama")
            (working_dir / "vdb_entities.json").write_text(
                json.dumps(
                    {
                        "data": [
                            {
                                "entity_name": "\u6c88\u5fc3\u5982",
                                "chapter_id": 4,
                                "content": "\u6c88\u5fc3\u5982\u5047\u88c5\u8df3\u6cb3\u81ea\u6740\uff0c\u5b9e\u9645\u662f\u8bbe\u8ba1\u63ed\u9732\u4e08\u592b\u548c\u95fa\u871c\u7684\u9634\u8c0b\u3002",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            question = "\u6c88\u5fc3\u5982\u662f\u771f\u7684\u8df3\u6cb3\u6b7b\u4e86\u5417\uff1f"

            self.assertTrue(service._is_future_lightrag_entity_question(working_dir, question, 1))
            self.assertFalse(service._is_future_lightrag_entity_question(working_dir, question, 5))
            self.assertEqual(service._load_lightrag_entity_keywords(working_dir, question), ["\u6c88\u5fc3\u5982"])

    def test_lightrag_entity_fallback_extracts_allowed_money_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            working_dir = make_lightrag_working_dir(tmpdir, "demo-drama")
            (working_dir / "vdb_entities.json").write_text(
                json.dumps(
                    {
                        "data": [
                            {
                                "entity_name": "\u6d3b\u671f\u50a8\u84c4\u5b58\u6298",
                                "chapter_id": 5,
                                "content": "\u6d3b\u671f\u50a8\u84c4\u5b58\u6298\n\u5b58\u6298\u4f59\u989d\u4e3a3000\u5143\uff0c\u7531\u9648\u6d77\u6e05\u4ea4\u7ed9\u8521\u6653\u8273\u3002",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            question = "\u9648\u6d77\u6e05\u7ed9\u8521\u6653\u8273\u7684\u5b58\u6298\u4f59\u989d\u662f\u591a\u5c11\uff1f"

            self.assertTrue(service._is_future_lightrag_entity_question(working_dir, question, 1))
            self.assertFalse(service._is_future_lightrag_entity_question(working_dir, question, 5))
            self.assertIsNone(service._fallback_lightrag_entity_answer(working_dir, question, 1))
            self.assertEqual(service._fallback_lightrag_entity_answer(working_dir, question, 5), "3000.00 \u5143")

    def test_lightrag_uses_series_specific_working_dirs_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            drama_a_dir = make_lightrag_working_dir(tmpdir, "drama-a")
            drama_b_dir = make_lightrag_working_dir(tmpdir, "drama-b")
            fake_lightrag = types.ModuleType("lightrag")
            fake_llm = types.ModuleType("lightrag.llm")
            fake_openai = types.ModuleType("lightrag.llm.openai")
            fake_utils = types.ModuleType("lightrag.utils")
            rag_instances = []

            class FakeQueryParam:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeEmbeddingFunc:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeLightRAG:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
                    rag_instances.append(self)

                async def initialize_storages(self):
                    return None

                async def aquery(self, question, param):
                    return f"answer from {Path(self.kwargs['working_dir']).parent.name}"

            async def fake_complete(*args, **kwargs):
                return ""

            async def fake_embed(*args, **kwargs):
                return []

            fake_lightrag.LightRAG = FakeLightRAG
            fake_lightrag.QueryParam = FakeQueryParam
            fake_openai.openai_complete_if_cache = fake_complete
            fake_openai.openai_embed = fake_embed
            fake_utils.EmbeddingFunc = FakeEmbeddingFunc

            with patch.dict(
                sys.modules,
                {
                    "lightrag": fake_lightrag,
                    "lightrag.llm": fake_llm,
                    "lightrag.llm.openai": fake_openai,
                    "lightrag.utils": fake_utils,
                },
            ), patch.dict(
                "os.environ",
                {
                    "STORY_QA_BACKEND": "lightrag",
                    "LIGHTRAG_WORKING_ROOT": tmpdir,
                    "OPENAI_API_KEY": "test-key",
                },
            ):
                first_a = self.client.post(
                    "/api/story-qa/ask",
                    json={"question": "q", "series_id": "drama-a", "current_episode": 1, "current_time": 0},
                )
                second_a = self.client.post(
                    "/api/story-qa/ask",
                    json={"question": "q", "series_id": "drama-a", "current_episode": 1, "current_time": 0},
                )
                first_b = self.client.post(
                    "/api/story-qa/ask",
                    json={"question": "q", "series_id": "drama-b", "current_episode": 1, "current_time": 0},
                )

        self.assertEqual(first_a.status_code, 200)
        self.assertEqual(second_a.status_code, 200)
        self.assertEqual(first_b.status_code, 200)
        self.assertEqual(len(rag_instances), 2)
        self.assertEqual(Path(rag_instances[0].kwargs["working_dir"]), drama_a_dir)
        self.assertEqual(Path(rag_instances[1].kwargs["working_dir"]), drama_b_dir)

    def test_lightrag_rejects_unsafe_series_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {
                "STORY_QA_BACKEND": "lightrag",
                "LIGHTRAG_WORKING_ROOT": tmpdir,
                "OPENAI_API_KEY": "test-key",
            },
        ):
            response = self.client.post(
                "/api/story-qa/ask",
                json={"question": "q", "series_id": "../drama", "current_episode": 1, "current_time": 0},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid series_id", response.json()["detail"])

    def test_lightrag_stream_passes_current_episode_as_chapter_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            make_lightrag_working_dir(tmpdir, "demo-drama")
            fake_lightrag = types.ModuleType("lightrag")
            fake_llm = types.ModuleType("lightrag.llm")
            fake_openai = types.ModuleType("lightrag.llm.openai")
            fake_utils = types.ModuleType("lightrag.utils")
            query_params = []

            class FakeQueryParam:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
                    query_params.append(kwargs)

            class FakeEmbeddingFunc:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeStream:
                def __aiter__(self):
                    self.items = iter(["answer ", "from stream"])
                    return self

                async def __anext__(self):
                    try:
                        return next(self.items)
                    except StopIteration as exc:
                        raise StopAsyncIteration from exc

            class FakeLightRAG:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

                async def initialize_storages(self):
                    return None

                async def aquery(self, question, param):
                    return FakeStream()

            async def fake_complete(*args, **kwargs):
                return ""

            async def fake_embed(*args, **kwargs):
                return []

            fake_lightrag.LightRAG = FakeLightRAG
            fake_lightrag.QueryParam = FakeQueryParam
            fake_openai.openai_complete_if_cache = fake_complete
            fake_openai.openai_embed = fake_embed
            fake_utils.EmbeddingFunc = FakeEmbeddingFunc

            with patch.dict(
                sys.modules,
                {
                    "lightrag": fake_lightrag,
                    "lightrag.llm": fake_llm,
                    "lightrag.llm.openai": fake_openai,
                    "lightrag.utils": fake_utils,
                },
            ), patch.dict(
                "os.environ",
                {
                    "STORY_QA_BACKEND": "lightrag",
                    "LIGHTRAG_WORKING_ROOT": tmpdir,
                    "LIGHTRAG_QUERY_MODE": "hybrid",
                    "LIGHTRAG_ENABLE_RERANK": "false",
                    "LIGHTRAG_TOP_K": "6",
                    "LIGHTRAG_CHUNK_TOP_K": "4",
                    "LIGHTRAG_COSINE_THRESHOLD": "0.4",
                    "LIGHTRAG_MAX_ENTITY_TOKENS": "1800",
                    "LIGHTRAG_MAX_RELATION_TOKENS": "2400",
                    "LIGHTRAG_MAX_TOTAL_TOKENS": "6000",
                    "LIGHTRAG_RESPONSE_TYPE": "Single Paragraph",
                    "OPENAI_API_KEY": "test-key",
                },
            ):
                response = self.client.post(
                    "/api/story-qa/ask-stream",
                    json={
                        "question": "who is he?",
                        "series_id": "demo-drama",
                        "current_episode": 1,
                        "current_time": 12,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "answer from stream")
        self.assertEqual(query_params[0]["current_chapter_id"], 1)
        self.assertTrue(query_params[0]["stream"])

    def test_lightrag_missing_working_dir_returns_400(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "STORY_QA_BACKEND": "lightrag",
                "LIGHTRAG_WORKING_ROOT": str(Path(tempfile.gettempdir()) / "dramepulse-missing-lightrag-working-root"),
                "OPENAI_API_KEY": "test-key",
            },
        ):
            response = self.client.post(
                "/api/story-qa/ask",
                json={
                    "question": "容遇是谁？",
                    "series_id": "demo-drama",
                    "current_episode": 3,
                    "current_time": 9999,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("LightRAG working directory does not exist", response.json()["detail"])

    def test_lightrag_collections_lists_series_working_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            make_lightrag_working_dir(
                tmpdir,
                "drama-a",
                {
                    "doc-1": {"chapter_id": 1},
                    "doc-2": {"chapter_id": 2},
                    "doc-3": {"chapter_id": 2},
                },
            )
            make_lightrag_working_dir(tmpdir, "drama-b", {"doc-1": {"chapter_id": 1}})
            with patch.dict(
                "os.environ",
                {
                    "STORY_QA_BACKEND": "lightrag",
                    "LIGHTRAG_WORKING_ROOT": tmpdir,
                },
            ):
                response = self.client.get("/api/story-qa/collections")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_documents"], 4)
        by_series = {item["series_id"]: item for item in payload["episodes"]}
        self.assertEqual(by_series["drama-a"]["documents"], 3)
        self.assertEqual(by_series["drama-a"]["source_types"]["chapter_2"], 2)
        self.assertEqual(by_series["drama-b"]["documents"], 1)


if __name__ == "__main__":
    unittest.main()
