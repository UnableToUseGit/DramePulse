from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.story_qa import service


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


class StoryQaApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

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
            fake_lightrag = types.ModuleType("lightrag")
            fake_llm = types.ModuleType("lightrag.llm")
            fake_openai = types.ModuleType("lightrag.llm.openai")
            fake_utils = types.ModuleType("lightrag.utils")

            class FakeQueryParam:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeEmbeddingFunc:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

            class FakeLightRAG:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

                async def initialize_storages(self):
                    return None

                async def aquery(self, question, param):
                    self.question = question
                    self.param = param
                    return "容遇是纪家长辈，也是前三集的核心人物。"

                async def finalize_storages(self):
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
                    "LIGHTRAG_WORKING_DIR": tmpdir,
                    "LIGHTRAG_QUERY_MODE": "hybrid",
                    "LIGHTRAG_ENABLE_RERANK": "false",
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

    def test_lightrag_missing_working_dir_returns_400(self) -> None:
        missing_dir = str(Path(tempfile.gettempdir()) / "dramepulse-missing-lightrag-working-dir")
        with patch.dict(
            "os.environ",
            {
                "STORY_QA_BACKEND": "lightrag",
                "LIGHTRAG_WORKING_DIR": missing_dir,
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
        self.assertIn("LIGHTRAG_WORKING_DIR does not exist", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
