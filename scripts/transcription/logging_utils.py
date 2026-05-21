from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


WORKFLOW_LOGGER_NAME = "videochat.workflow.pipeline"


def format_elapsed_minutes_seconds(elapsed_ms: int) -> str:
    total_seconds = max(0, elapsed_ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds}s"


def log_transcription_event(event: str, **fields: object) -> None:
    logger = logging.getLogger(WORKFLOW_LOGGER_NAME)
    if not logger.handlers:
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"{timestamp} | {event}"]
    for key, value in fields.items():
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        lines.append(f"  {key}: {rendered}")
    logger.info("\n".join(lines))
