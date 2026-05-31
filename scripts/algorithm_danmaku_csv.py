from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any


SERIES_SLUGS = {
    "云渺1：我修仙多年强亿点怎么了": "yunmiao_1",
    "北往": "beiwang",
    "北派寻宝笔记": "beipai_xunbao_biji",
    "十八岁太奶奶驾到，重整家族荣耀第三部": "shibasui_tainainai",
    "天下第一纨绔": "tianxia_diyi_wanku",
    "家里家外": "jiali_jiawai",
    "幸得相遇离婚时": "xingde_xiangyu_lihunshi",
    "撕夜": "siye",
    "荒年全村啃树皮，我有系统满仓肉": "huangnian_quancun_kenshupi",
    "那年冬至": "nanian_dongzhi",
}

DANMAKU_CSV_ENCODINGS = ("utf-8-sig", "gb18030")


def discover_danmaku_csv_paths(data_root: Path) -> list[Path]:
    return sorted(path for path in data_root.glob("*.csv") if path.is_file())


def normalize_episode_id(value: Any) -> str | None:
    match = re.search(r"\d+", str(value or ""))
    if not match:
        return None
    return f"ep{int(match.group(0)):02d}"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    for encoding in DANMAKU_CSV_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except UnicodeDecodeError:
            continue
        except OSError:
            return []
    return []


def _normalize_csv_row(row: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    series_name = str(row.get("剧名称") or "").strip()
    series_id = SERIES_SLUGS.get(series_name)
    episode_id = normalize_episode_id(row.get("group_title"))
    text = str(row.get("弹幕内容") or "").strip()
    if not series_id or not episode_id or not text:
        return None
    try:
        time_ms = float(row.get("发弹幕时刻相对于视频起始时间偏移量") or 0.0)
    except (TypeError, ValueError):
        return None
    if time_ms < 0:
        return None
    try:
        digg_count = int(float(row.get("累计点赞数") or 0))
    except (TypeError, ValueError):
        digg_count = 0
    time_sec = round(time_ms / 1000.0, 3)
    return {
        "danmaku_id": f"csv_{series_id}_{episode_id}_{index + 1}",
        "series_id": series_id,
        "episode_id": episode_id,
        "time_sec": time_sec,
        "time_ms": int(round(time_ms)),
        "text": text,
        "digg_count": digg_count,
        "source": "data_root_csv",
    }


def load_danmaku_csv_items(data_root: Path, *, series_id: str, episode_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for csv_path in discover_danmaku_csv_paths(data_root):
        for index, row in enumerate(_read_csv_rows(csv_path)):
            item = _normalize_csv_row(row, index=index)
            if item is None:
                continue
            if item["series_id"] == series_id and item["episode_id"] == episode_id:
                items.append(item)
    return sorted(items, key=lambda item: (float(item["time_sec"]), str(item["danmaku_id"])))
