from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import OpenAI

from scripts.transcription.env import load_dotenv_values


def _first_value(dotenv_values: dict[str, str], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value.strip()
    for key in keys:
        value = dotenv_values.get(key)
        if value:
            return value.strip()
    return None


def _masked_secret(value: str | None) -> str:
    if not value:
        return "<unset>"
    if len(value) <= 10:
        return f"<set len={len(value)}>"
    return f"<set len={len(value)} prefix={value[:4]!r} suffix={value[-4:]!r}>"


def _response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        dumped = response.model_dump()
        return dumped if isinstance(dumped, dict) else {"value": dumped}
    if hasattr(response, "to_dict_recursive"):
        dumped = response.to_dict_recursive()
        return dumped if isinstance(dumped, dict) else {"value": dumped}
    if isinstance(response, dict):
        return response
    return {"repr": repr(response), "type": type(response).__name__}


def _summarize_response(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    return {
        "top_level_keys": sorted(payload.keys()),
        "id": payload.get("id"),
        "object": payload.get("object"),
        "model": payload.get("model"),
        "usage": payload.get("usage"),
        "choice_count": len(choices) if isinstance(choices, list) else None,
        "first_choice_keys": sorted(first_choice.keys()) if isinstance(first_choice, dict) else None,
        "first_message_keys": sorted(message.keys()) if isinstance(message, dict) else None,
        "first_finish_reason": first_choice.get("finish_reason") if isinstance(first_choice, dict) else None,
        "first_message_content": message.get("content") if isinstance(message, dict) else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send a tiny OpenAI chat.completions request and print request/response details for reasoning debugging."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--model", help="Override OPENAI_MODEL/MODEL.")
    parser.add_argument("--base-url", help="Override OPENAI_BASE_URL/BASE_URL.")
    parser.add_argument("--api-key", help="Override OPENAI_API_KEY/API_KEY. Avoid passing this in shell history if possible.")
    parser.add_argument("--reasoning-effort", default="none", help="Value for chat.completions reasoning_effort. Use 'omit' to not send it.")
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout-sec", type=int, default=90)
    parser.add_argument("--raw", action="store_true", help="Print full response JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    dotenv_values = load_dotenv_values(args.env_file)
    provider = (_first_value(dotenv_values, ["LLM_PROVIDER"]) or "").strip().lower()

    api_key = args.api_key or _first_value(dotenv_values, ["OPENAI_API_KEY"])
    base_url = args.base_url or _first_value(dotenv_values, ["OPENAI_BASE_URL"])
    model = args.model or _first_value(dotenv_values, ["OPENAI_MODEL"])

    if provider in {"openai", "open_ai"}:
        api_key = api_key or _first_value(dotenv_values, ["API_KEY"])
        base_url = base_url or _first_value(dotenv_values, ["BASE_URL"])
        model = model or _first_value(dotenv_values, ["MODEL"])

    model = model or "gpt-5.1"
    if not api_key:
        print("Missing OPENAI_API_KEY. Set OPENAI_API_KEY or set LLM_PROVIDER=openai with API_KEY.", file=sys.stderr)
        return 2

    client_kwargs: dict[str, Any] = {"api_key": api_key, "timeout": args.timeout_sec}
    if base_url:
        client_kwargs["base_url"] = base_url

    request_options: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": 'Return exactly {"ok": true, "reasoning_debug": "short"}.'},
        ],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }
    if args.reasoning_effort != "omit":
        request_options["reasoning_effort"] = args.reasoning_effort

    print(
        json.dumps(
            {
                "client_config": {
                    "provider_from_env": provider or "<unset>",
                    "base_url": base_url or "<default OpenAI>",
                    "api_key": _masked_secret(api_key),
                    "model": model,
                },
                "request_debug": {
                    "keys": sorted(request_options.keys()),
                    "reasoning_effort": request_options.get("reasoning_effort", "<omitted>"),
                    "max_tokens": args.max_tokens,
                    "temperature": args.temperature,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    try:
        response = OpenAI(**client_kwargs).chat.completions.create(**request_options)
    except Exception as exc:  # noqa: BLE001 - this is a debug script.
        print(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "request_debug": {
                        "keys": sorted(request_options.keys()),
                        "reasoning_effort": request_options.get("reasoning_effort", "<omitted>"),
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    payload = _response_to_dict(response)
    print(json.dumps({"response_summary": _summarize_response(payload)}, ensure_ascii=False, indent=2))
    if args.raw:
        print(json.dumps({"raw_response": payload}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
