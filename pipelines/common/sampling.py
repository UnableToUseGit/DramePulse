from __future__ import annotations


def build_sample_timestamps(
    *,
    duration_sec: float,
    sample_interval_sec: float,
    start_sec: float = 0.0,
    max_frames: int | None = None,
) -> list[float]:
    if duration_sec <= 0:
        return []
    if sample_interval_sec <= 0:
        raise ValueError("sample_interval_sec must be positive")
    if start_sec < 0:
        raise ValueError("start_sec must be non-negative")

    timestamps: list[float] = []
    current = start_sec
    while current < duration_sec:
        timestamps.append(round(current, 3))
        current = round(current + sample_interval_sec, 3)
    if max_frames is not None and len(timestamps) > max_frames:
        if max_frames <= 0:
            raise ValueError("max_frames must be positive")
        if max_frames == 1:
            return [round(start_sec, 3)]
        end_sec = max(start_sec, duration_sec - 0.001)
        step = (end_sec - start_sec) / float(max_frames - 1)
        return [round(start_sec + index * step, 3) for index in range(max_frames)]
    return timestamps
