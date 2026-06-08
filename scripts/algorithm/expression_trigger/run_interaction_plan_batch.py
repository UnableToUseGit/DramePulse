from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pipelines.expression_trigger.interaction_plan import build_expression_interaction_plan


DEFAULT_EXPRESSION_TRIGGER_ROOT = Path("output/expression_trigger_from_plot_beats")
DEFAULT_OUTPUT_ROOT = Path("output/interaction_plan/from_expression_triggers")
EXPRESSION_TRIGGER_FILENAME = "expression_triggers.json"
OUTPUT_FILENAME = "interaction_plan.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build emotional button interaction plans from expression triggers.")
    parser.add_argument("--expression-trigger-root", type=Path, default=DEFAULT_EXPRESSION_TRIGGER_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--video-id", nargs="+", action="append", help="Only process exact video ids such as beiwang_ep01.")
    parser.add_argument("--force", action="store_true", help="Regenerate outputs that already exist.")
    parser.add_argument("--duration-sec", type=float, default=5.0)
    return parser


def _flatten_groups(groups: list[list[str]] | None) -> list[str]:
    return [item for group in (groups or []) for item in group]


def _expression_trigger_path(root: Path, video_id: str) -> Path:
    return root / video_id / EXPRESSION_TRIGGER_FILENAME


def _output_path(root: Path, video_id: str) -> Path:
    return root / video_id / OUTPUT_FILENAME


def _load_expression_trigger_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if not isinstance(payload.get("expression_triggers"), list):
        raise ValueError(f"{path} missing `expression_triggers` list")
    return payload


def discover_expression_trigger_video_ids(root: Path, *, video_ids: Sequence[str] | None = None) -> list[str]:
    if video_ids:
        return sorted(set(video_ids))
    if not root.exists():
        raise FileNotFoundError(root)
    return sorted(path.parent.name for path in root.glob(f"*/{EXPRESSION_TRIGGER_FILENAME}"))


def write_interaction_plan_from_expression_triggers(
    *,
    expression_trigger_path: Path,
    output_root: Path,
    duration_sec: float = 5.0,
) -> Path:
    payload = _load_expression_trigger_payload(expression_trigger_path)
    video_id = str(payload.get("video_id") or expression_trigger_path.parent.name)
    series_id = str(payload.get("series_id") or "")
    plan = build_expression_interaction_plan(
        list(payload.get("expression_triggers") or []),
        video_id=video_id,
        series_id=series_id,
        duration_sec=duration_sec,
    )
    output_path = _output_path(output_root, video_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    video_ids = discover_expression_trigger_video_ids(
        args.expression_trigger_root,
        video_ids=_flatten_groups(args.video_id),
    )
    processed = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    for video_id in video_ids:
        expression_trigger_path = _expression_trigger_path(args.expression_trigger_root, video_id)
        output_path = _output_path(args.output_root, video_id)
        if output_path.exists() and not args.force:
            skipped += 1
            print(f"SKIP {video_id}: existing {output_path}")
            continue
        if not expression_trigger_path.exists():
            failed.append((video_id, f"missing expression triggers: {expression_trigger_path}"))
            print(f"FAIL {video_id}: missing expression triggers {expression_trigger_path}")
            continue
        try:
            written_path = write_interaction_plan_from_expression_triggers(
                expression_trigger_path=expression_trigger_path,
                output_root=args.output_root,
                duration_sec=args.duration_sec,
            )
        except Exception as exc:  # noqa: BLE001 - batch should continue and report per-episode failures.
            failed.append((video_id, str(exc)))
            print(f"FAIL {video_id}: {exc}")
            continue
        processed += 1
        print(f"WROTE {written_path}")

    print(f"DONE processed={processed} skipped={skipped} failed={len(failed)}")
    if failed:
        for video_id, error in failed:
            print(f"FAILED {video_id}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
