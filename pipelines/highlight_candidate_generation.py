from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Protocol, Sequence


class TextLlmClientProtocol(Protocol):
    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 2400,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class Utterance:
    utterance_id: str
    start_time: float
    end_time: float
    text: str
    speaker_id: str | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _round_time(value: float) -> float:
    return round(float(value), 3)


def load_utterances_from_transcription(path: Path) -> list[Utterance]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_response = payload.get("raw_response") if isinstance(payload, dict) else None
    chunks = raw_response.get("chunks", []) if isinstance(raw_response, dict) else []
    utterances: list[Utterance] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        offset_seconds = float(chunk.get("offset_seconds") or 0.0)
        raw_result = chunk.get("raw_result") or {}
        transcripts = raw_result.get("transcripts", []) if isinstance(raw_result, dict) else []
        for transcript in transcripts:
            if not isinstance(transcript, dict):
                continue
            sentences = transcript.get("sentences") or []
            for sentence in sentences:
                if not isinstance(sentence, dict):
                    continue
                text = str(sentence.get("text") or "").strip()
                if not text:
                    continue
                start = offset_seconds + float(sentence.get("begin_time") or 0.0) / 1000.0
                end = offset_seconds + float(sentence.get("end_time") or 0.0) / 1000.0
                if end <= start:
                    continue
                utterances.append(
                    Utterance(
                        utterance_id=f"u_{len(utterances) + 1:03d}",
                        start_time=_round_time(start),
                        end_time=_round_time(end),
                        text=text,
                        speaker_id=str(sentence["speaker_id"]) if "speaker_id" in sentence else None,
                    )
                )
    return utterances


def load_scenes(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenes = payload.get("scenes", []) if isinstance(payload, dict) else []
    normalized: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        try:
            start_time = float(scene["start_time"])
            end_time = float(scene["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if end_time <= start_time:
            continue
        normalized.append(
            {
                "scene_id": str(scene.get("scene_id") or f"s_{index:03d}"),
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "index": int(scene.get("index") or index),
                "clip_path": scene.get("clip_path"),
            }
        )
    return normalized


def format_utterance_timeline(utterances: Sequence[Utterance]) -> str:
    lines = ["UTTERANCES:"]
    for utterance in utterances:
        speaker = f" speaker={utterance.speaker_id}" if utterance.speaker_id is not None else ""
        lines.append(
            f"- {utterance.utterance_id} [{utterance.start_time:.3f}-{utterance.end_time:.3f}]{speaker}: {utterance.text}"
        )
    return "\n".join(lines)


def build_system_prompt() -> str:
    return (
        "You identify candidate highlight cues in short dramas. "
        "A cue is one utterance that may be located inside a shot carrying an emotional or narrative value shift. "
        "Use the timestamped utterances only. Return JSON only."
    )


def build_user_prompt(video_id: str, utterances: Sequence[Utterance]) -> str:
    return "\n".join(
        [
            f"VIDEO_ID: {video_id}",
            "Task: recall utterances that may sit inside a highlight shot.",
            "Definition: a highlight shot is not an entire conflict scene. It is one shot that carries an emotional/value shift: the situation, relationship, revealed information, or audience expectation changes.",
            "Candidate types include: reversal, face_slap, conflict, identity_reveal, truth_reveal, sweet_moment, danger_crisis, emotional_break, choice_suspense.",
            "Output JSON shape:",
            '{"cues":[{"utterance_id":"u_001","highlight_type":"truth_reveal","summary":"...","reason":"...","confidence":0.8}]}',
            "Rules:",
            "- Prefer high recall. It is acceptable to include uncertain candidates if grounded in utterances.",
            "- Do not return a whole conflict or a long text span.",
            "- Return the single utterance_id most likely to sit inside the highlight shot.",
            "- The visual stage will map that utterance time to a PySceneDetect scene and audit it.",
            "- Keep each candidate concise and grounded.",
            format_utterance_timeline(utterances),
        ]
    )


def parse_candidate_cues(raw: dict[str, Any], *, utterances: Sequence[Utterance]) -> list[dict[str, Any]]:
    items = raw.get("cues", []) if isinstance(raw, dict) else []
    if not isinstance(items, list):
        return []
    utterance_by_id = {utterance.utterance_id: utterance for utterance in utterances}
    cues: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        utterance_id = str(item.get("utterance_id") or "").strip()
        utterance = utterance_by_id.get(utterance_id)
        if utterance is None:
            continue
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            continue
        if not 0.0 <= confidence <= 1.0:
            continue
        cue_time = _round_time((utterance.start_time + utterance.end_time) / 2.0)
        cues.append(
            {
                "cue_id": f"cue_{len(cues) + 1:03d}",
                "utterance_id": utterance.utterance_id,
                "cue_time": cue_time,
                "utterance": asdict(utterance),
                "highlight_type": str(item.get("highlight_type", "")).strip() or "unknown",
                "summary": str(item.get("summary", "")).strip(),
                "reason": str(item.get("reason", "")).strip(),
                "confidence": confidence,
                "source_rank": index,
            }
        )
    return cues


def _overlaps(start_a: float, end_a: float, start_b: float, end_b: float) -> bool:
    return start_a < end_b and start_b < end_a


def map_cue_to_scene(
    cue: dict[str, Any],
    scenes: Sequence[dict[str, Any]],
    *,
    context_size: int = 1,
) -> dict[str, Any]:
    cue_time = float(cue["cue_time"])
    target_index = None
    for index, scene in enumerate(scenes):
        if float(scene["start_time"]) <= cue_time < float(scene["end_time"]):
            target_index = index
            break
    if target_index is None and scenes:
        target_index = min(
            range(len(scenes)),
            key=lambda index: min(
                abs(cue_time - float(scenes[index]["start_time"])),
                abs(cue_time - float(scenes[index]["end_time"])),
            ),
        )
    if target_index is None:
        return {
            "target_scene": None,
            "context_scene_ids": [],
            "context_start_time": _round_time(cue_time),
            "context_end_time": _round_time(cue_time),
        }

    left = max(0, target_index - context_size)
    right = min(len(scenes) - 1, target_index + context_size)
    selected = list(scenes[left : right + 1])
    return {
        "target_scene": dict(scenes[target_index]),
        "context_scene_ids": [str(scene["scene_id"]) for scene in selected],
        "context_start_time": _round_time(float(selected[0]["start_time"])),
        "context_end_time": _round_time(float(selected[-1]["end_time"])),
    }


def _context_subtitles(utterances: Sequence[Utterance], start_time: float, end_time: float) -> str:
    lines = []
    for utterance in utterances:
        if _overlaps(utterance.start_time, utterance.end_time, start_time, end_time):
            lines.append(f"[{utterance.start_time:.3f}-{utterance.end_time:.3f}] {utterance.text}")
    return "\n".join(lines)


class HighlightCandidatePipeline:
    def __init__(
        self,
        *,
        llm_client: TextLlmClientProtocol,
        context_size: int = 1,
        max_output_tokens: int = 2400,
    ) -> None:
        self.llm_client = llm_client
        self.context_size = context_size
        self.max_output_tokens = max_output_tokens

    def run(
        self,
        *,
        video_id: str,
        transcription_path: Path,
        scene_detection_path: Path,
        output_root: Path,
    ) -> Path:
        utterances = load_utterances_from_transcription(transcription_path)
        scenes = load_scenes(scene_detection_path)
        raw = self.llm_client.generate_json_multimodal(
            system_prompt=build_system_prompt(),
            user_prompt=build_user_prompt(video_id, utterances),
            max_tokens=self.max_output_tokens,
        )
        cues = parse_candidate_cues(raw, utterances=utterances)
        scene_cues: list[dict[str, Any]] = []
        for cue in cues:
            mapped = map_cue_to_scene(
                cue,
                scenes,
                context_size=self.context_size,
            )
            scene_cues.append(
                {
                    "cue_id": cue["cue_id"],
                    "utterance_id": cue["utterance_id"],
                    "cue_time": cue["cue_time"],
                    "target_scene": mapped["target_scene"],
                    "context_scene_ids": mapped["context_scene_ids"],
                    "context_start_time": mapped["context_start_time"],
                    "context_end_time": mapped["context_end_time"],
                    "context_subtitles": _context_subtitles(
                        utterances, float(mapped["context_start_time"]), float(mapped["context_end_time"])
                    ),
                }
            )

        output_dir = output_root / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "highlight_candidates.json"
        payload = {
            "video_id": video_id,
            "created_at": _now_iso(),
            "source": {
                "transcription_path": str(transcription_path),
                "scene_detection_path": str(scene_detection_path),
            },
            "utterances": [asdict(utterance) for utterance in utterances],
            "scenes": list(scenes),
            "candidate_cues": cues,
            "candidate_scene_cues": scene_cues,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path
