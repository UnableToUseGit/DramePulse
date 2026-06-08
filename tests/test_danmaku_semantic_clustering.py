from __future__ import annotations

import json
from pathlib import Path


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        vectors: list[list[float]] = []
        for text in texts:
            if "帅" in text or "眼神" in text or "老公" in text:
                vectors.append([1.0, 0.0, 0.0])
            elif "怼" in text or "争气" in text:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


class CoordinateEmbeddingClient:
    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self.vectors_by_text = vectors_by_text
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self.vectors_by_text[text] for text in texts]


def write_semantic_cluster_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,10000,3,这个眼神太帅了",
                "北往,第1集,10800,1,男主眼神绝了",
                "北往,第1集,11600,2,老公好帅",
                "北往,第1集,70000,5,她终于怼回去了",
                "北往,第1集,71000,2,女主这句太争气了",
                "北往,第1集,72000,1,终于怼回去了",
                "北往,第1集,90000,0,哈哈哈",
                "北往,第2集,10000,4,第二集男主好帅",
            ]
        )
        + "\n",
        encoding="gb18030",
    )


class CapturePrint:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, *args: object, **kwargs: object) -> None:
        self.calls.append({"args": args, "kwargs": kwargs})


def test_cluster_episode_danmaku_groups_semantic_texts_and_peak_intervals(tmp_path: Path) -> None:
    from pipelines.danmaku_semantic_clustering import cluster_danmaku_semantics_from_csv

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    write_semantic_cluster_csv(csv_path)
    fake_client = FakeEmbeddingClient()
    events: list[tuple[str, dict[str, object]]] = []

    result = cluster_danmaku_semantics_from_csv(
        csv_path,
        embedding_client=fake_client,
        series_id="beiwang",
        episode_id="ep01",
        cluster_method="connected_components",
        similarity_threshold=0.8,
        min_cluster_comment_count=2,
        peak_window_sec=5.0,
        max_clusters_per_episode=10,
        progress_callback=lambda event, payload: events.append((event, payload)),
    )

    assert result["sourceCsv"] == str(csv_path)
    assert result["diagnostics"]["normalizedRowCount"] == 8
    assert result["episodeCount"] == 1
    assert result["clusterCount"] == 2
    assert len(fake_client.calls) == 1
    assert "哈哈哈" not in fake_client.calls[0]

    clusters = result["clusters"]
    assert clusters[0]["videoId"] == "beiwang_ep01"
    assert clusters[0]["commentCount"] == 3
    assert clusters[0]["uniqueTextCount"] == 3
    assert clusters[0]["peakIntervals"][0]["startTime"] == 10.0
    assert clusters[0]["peakIntervals"][0]["endTime"] == 15.0
    assert clusters[0]["peakIntervals"][0]["commentCount"] == 3
    assert clusters[0]["sourceCommentIds"] == [
        "csv_beiwang_ep01_1",
        "csv_beiwang_ep01_2",
        "csv_beiwang_ep01_3",
    ]
    assert {example["text"] for example in clusters[0]["examples"]} == {
        "这个眼神太帅了",
        "男主眼神绝了",
        "老公好帅",
    }

    assert clusters[1]["peakIntervals"][0]["startTime"] == 70.0
    assert clusters[1]["peakIntervals"][0]["commentCount"] == 3
    event_names = [event for event, _payload in events]
    assert event_names == [
        "prepared",
        "episode_start",
        "embedding_start",
        "embedding_done",
        "clustering_start",
        "clustering_done",
        "completed",
    ]
    assert events[1][1]["video_id"] == "beiwang_ep01"
    assert events[1][1]["expression_group_count"] == 6
    assert events[-1][1]["cluster_count"] == 2


def test_cluster_episode_selects_strong_clusters_before_time_order(tmp_path: Path) -> None:
    from pipelines.danmaku_semantic_clustering import cluster_danmaku_semantics_from_csv

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    rows = ["剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容"]
    rows.extend(
        [
            "北往,第1集,1000,0,早期小簇A",
            "北往,第1集,2000,0,早期小簇B",
            "北往,第1集,3000,0,早期小簇C",
        ]
    )
    rows.extend(
        f"北往,第1集,{70000 + index * 300},0,后期强簇{index}"
        for index in range(8)
    )
    csv_path.write_text("\n".join(rows) + "\n", encoding="gb18030")

    class StrengthFakeEmbeddingClient:
        last_call_diagnostics: dict[str, object] = {}

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] if text.startswith("早期") else [0.0, 1.0] for text in texts]

    result = cluster_danmaku_semantics_from_csv(
        csv_path,
        embedding_client=StrengthFakeEmbeddingClient(),
        series_id="beiwang",
        episode_id="ep01",
        cluster_method="connected_components",
        similarity_threshold=0.8,
        min_cluster_comment_count=2,
        max_clusters_per_episode=1,
    )

    assert result["clusterCount"] == 1
    assert result["clusters"][0]["commentCount"] == 8
    assert result["clusters"][0]["peakIntervals"][0]["startTime"] == 70.0


def test_hdbscan_scores_top_clusters_and_selects_representative_comments(tmp_path: Path) -> None:
    from pipelines.danmaku_semantic_clustering import cluster_danmaku_semantics_from_csv

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    rows = ["剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容"]
    rows.extend(
        [
            "北往,第1集,10000,4,男主眼神太帅了",
            "北往,第1集,10800,2,这个眼神好帅",
            "北往,第1集,11600,1,老公这个眼神绝了",
            "北往,第1集,70000,1,女主终于怼回去了",
            "北往,第1集,70800,1,她这句太争气了",
            "北往,第1集,71600,1,终于反击了",
            "北往,第1集,90000,10,孤立高赞一句",
            "北往,第1集,91000,0,孤立高赞另一句",
        ]
    )
    csv_path.write_text("\n".join(rows) + "\n", encoding="gb18030")
    embedding_client = CoordinateEmbeddingClient(
        {
            "男主眼神太帅了": [1.0, 0.0],
            "这个眼神好帅": [0.99, 0.01],
            "老公这个眼神绝了": [0.98, 0.02],
            "女主终于怼回去了": [0.0, 1.0],
            "她这句太争气了": [0.01, 0.99],
            "终于反击了": [0.02, 0.98],
            "孤立高赞一句": [-1.0, 0.0],
            "孤立高赞另一句": [-0.99, 0.01],
        }
    )

    result = cluster_danmaku_semantics_from_csv(
        csv_path,
        embedding_client=embedding_client,
        series_id="beiwang",
        episode_id="ep01",
        cluster_method="hdbscan",
        hdbscan_min_cluster_size=3,
        hdbscan_min_samples=1,
        top_k_clusters=1,
        representative_comment_count=2,
    )

    assert result["parameters"]["clusterMethod"] == "hdbscan"
    assert result["parameters"]["topKClusters"] == 1
    assert result["diagnostics"]["rawClusterCount"] == 2
    assert result["clusterCount"] == 1
    assert result["topClusters"] == result["clusters"]
    assert len(result["allClustersByScore"]) == 2
    assert result["allClustersByScore"][0]["clusterScore"] >= result["allClustersByScore"][1]["clusterScore"]

    cluster = result["clusters"][0]
    assert cluster["commentCount"] == 3
    assert cluster["clusterScore"] > 0
    assert cluster["scoreBreakdown"]["commentCount"] == 3
    assert len(cluster["representativeComments"]) == 2
    assert cluster["representativeComments"][0]["text"] == "这个眼神好帅"
    assert cluster["representativeComments"][0]["distanceToCentroid"] < cluster["representativeComments"][1]["distanceToCentroid"]
    assert {example["text"] for example in cluster["examples"]} == {
        "男主眼神太帅了",
        "这个眼神好帅",
        "老公这个眼神绝了",
    }


def test_danmaku_semantic_clustering_cli_writes_artifact(tmp_path: Path) -> None:
    from scripts.run_danmaku_semantic_clustering import main

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    output_path = tmp_path / "semantic_clusters.json"
    write_semantic_cluster_csv(csv_path)
    fake_client = FakeEmbeddingClient()

    result = main(
        [
            "--csv-path",
            str(csv_path),
            "--output-path",
            str(output_path),
            "--series-id",
            "beiwang",
            "--episode-id",
            "ep01",
            "--cluster-method",
            "connected_components",
            "--min-cluster-comment-count",
            "2",
        ],
        embedding_client=fake_client,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["clusterCount"] == 2
    assert payload["clusters"][0]["videoId"] == "beiwang_ep01"


def test_danmaku_semantic_clustering_cli_prints_progress(tmp_path: Path, capsys) -> None:
    from scripts.run_danmaku_semantic_clustering import main

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    output_path = tmp_path / "semantic_clusters.json"
    write_semantic_cluster_csv(csv_path)
    fake_client = FakeEmbeddingClient()

    result = main(
        [
            "--csv-path",
            str(csv_path),
            "--output-path",
            str(output_path),
            "--series-id",
            "beiwang",
            "--episode-id",
            "ep01",
            "--cluster-method",
            "connected_components",
            "--min-cluster-comment-count",
            "2",
        ],
        embedding_client=fake_client,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "prepared: episodes=1 comments=7" in captured.out
    assert "[beiwang_ep01] episode_start: comments=7 expression_groups=6" in captured.out
    assert "[beiwang_ep01] embedding_start: expression_groups=6" in captured.out
    assert "[beiwang_ep01] embedding_done: vectors=6" in captured.out
    assert "[beiwang_ep01] clustering_start: vectors=6 method=connected_components threshold=0.82" in captured.out
    assert "[beiwang_ep01] clustering_done: clusters=2" in captured.out
    assert "completed: episodes=1 clusters=2" in captured.out


def test_semantic_clustering_progress_prints_flush(monkeypatch) -> None:
    from scripts.run_danmaku_semantic_clustering import print_embedding_progress

    capture = CapturePrint()
    monkeypatch.setattr("builtins.print", capture)

    print_embedding_progress(
        "embedding_batch",
        {"batch_index": 1, "batch_count": 2, "batch_size": 128, "total_tokens": 10},
    )

    assert capture.calls[0]["kwargs"]["flush"] is True


def test_danmaku_semantic_clustering_cli_builds_openrouter_embedding_client(tmp_path: Path) -> None:
    from scripts.run_danmaku_semantic_clustering import build_embedding_client_from_args, build_parser

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "EMBEDDING_API_KEY=test-openrouter-key",
                "EMBEDDING_BASE_URL=https://openrouter.ai/api/v1/embeddings",
                "EMBEDDING_MODEL=baai/bge-m3",
                "OPENROUTER_SITE_URL=https://dramepulse.example",
                "OPENROUTER_SITE_NAME=DramePulse",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    args = build_parser().parse_args(["--env-file", str(env_path), "--embedding-batch-size", "16"])
    client = build_embedding_client_from_args(args)

    assert client.__class__.__name__ == "CachedEmbeddingClient"
    assert client.inner_client.__class__.__name__ == "OpenRouterEmbeddingClient"
    assert client.inner_client.url == "https://openrouter.ai/api/v1/embeddings"
    assert client.model_name == "baai/bge-m3"
    assert client.inner_client.batch_size == 16
    assert client.inner_client.site_url == "https://dramepulse.example"
    assert client.inner_client.site_name == "DramePulse"


def test_danmaku_semantic_clustering_cli_wraps_embedding_client_with_cache(tmp_path: Path) -> None:
    from scripts.run_danmaku_semantic_clustering import build_embedding_client_from_args, build_parser

    env_path = tmp_path / ".env"
    cache_path = tmp_path / "embedding_cache.sqlite"
    env_path.write_text(
        "\n".join(
            [
                "EMBEDDING_API_KEY=test-openrouter-key",
                "EMBEDDING_BASE_URL=https://openrouter.ai/api/v1/embeddings",
                "EMBEDDING_MODEL=baai/bge-m3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    args = build_parser().parse_args(
        [
            "--env-file",
            str(env_path),
            "--embedding-cache-path",
            str(cache_path),
        ]
    )
    client = build_embedding_client_from_args(args)

    assert client.__class__.__name__ == "CachedEmbeddingClient"
    assert client.cache_path == cache_path
    assert client.model_name == "baai/bge-m3"
    assert client.inner_client.__class__.__name__ == "OpenRouterEmbeddingClient"


def test_danmaku_semantic_clustering_cli_can_disable_embedding_cache(tmp_path: Path) -> None:
    from scripts.run_danmaku_semantic_clustering import build_embedding_client_from_args, build_parser

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "EMBEDDING_API_KEY=test-openrouter-key",
                "EMBEDDING_BASE_URL=https://openrouter.ai/api/v1/embeddings",
                "EMBEDDING_MODEL=baai/bge-m3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    args = build_parser().parse_args(["--env-file", str(env_path), "--no-embedding-cache"])
    client = build_embedding_client_from_args(args)

    assert client.__class__.__name__ == "OpenRouterEmbeddingClient"


def test_danmaku_semantic_clustering_cli_normalizes_openrouter_base_url(tmp_path: Path) -> None:
    from scripts.run_danmaku_semantic_clustering import build_embedding_client_from_args, build_parser

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "EMBEDDING_API_KEY=test-openrouter-key",
                "EMBEDDING_BASE_URL=https://openrouter.ai/api/v1",
                "EMBEDDING_MODEL=baai/bge-m3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    args = build_parser().parse_args(["--env-file", str(env_path)])
    client = build_embedding_client_from_args(args)

    assert client.__class__.__name__ == "CachedEmbeddingClient"
    assert client.inner_client.__class__.__name__ == "OpenRouterEmbeddingClient"
    assert client.inner_client.url == "https://openrouter.ai/api/v1/embeddings"
