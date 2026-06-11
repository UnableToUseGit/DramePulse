from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipelines.highlight_commerce.generation import (
    DEFAULT_STYLE_REFERENCE_DIR,
    HighlightCommerceCartoonPipeline,
)
from pipelines.highlight_commerce.seedream_generation import SeedreamImageGenerationClient
from scripts.transcription.env import get_env_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate privacy-safe cartoon references for highlight commerce.")
    parser.add_argument("--asset", type=Path, required=True, help="Path to highlight commerce JSON.")
    parser.add_argument("--output-root", type=Path, default=Path("output/role-commerce-v2"), help="Output root.")
    parser.add_argument("--style-reference-dir", type=Path, default=DEFAULT_STYLE_REFERENCE_DIR)
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file.")
    return parser


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def build_seedream_client(*, env_path: Path | None = None) -> SeedreamImageGenerationClient:
    dotenv_api_key = get_env_value("ARK_API_KEY", env_path=env_path)
    dotenv_base_url = get_env_value("ARK_BASE_URL", env_path=env_path)
    dotenv_model = get_env_value("ARK_SEEDREAM_MODEL", env_path=env_path)
    return SeedreamImageGenerationClient(
        api_key=dotenv_api_key or None,
        base_url=dotenv_base_url or None,
        model_name=dotenv_model or None,
    )


def _output_dir(output_root: Path, asset: dict[str, object]) -> Path:
    campaign_id = str(asset.get("campaign_id") or "").strip()
    if not campaign_id:
        raise ValueError("Highlight commerce asset requires `campaign_id`")
    return output_root / campaign_id


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: HighlightCommerceCartoonPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    asset = _load_json(args.asset)
    output_dir = _output_dir(args.output_root, asset)
    active_pipeline = pipeline or HighlightCommerceCartoonPipeline(
        seedream_client=build_seedream_client(env_path=args.env_file),
        style_reference_dir=args.style_reference_dir,
    )
    result = active_pipeline.run(asset, output_dir=output_dir)
    output_path = output_dir / "highlight_commerce_cartoon_asset.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote highlight commerce cartoon asset: {output_path}")
    refs = result.get("cartoon_references")
    if isinstance(refs, dict):
        for key in ["highlight_reference_path", "male_avatar_path", "female_avatar_path"]:
            if refs.get(key):
                print(f"{key}: {refs[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
