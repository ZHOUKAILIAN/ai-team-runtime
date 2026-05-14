from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .models import StageRunRecord


def stage_run_timing(run: StageRunRecord) -> dict[str, Any]:
    steps = [dict(item) for item in run.steps]
    step_times = [step.get("at") for step in steps]
    first_at = _first_timestamp(step_times) or _first_timestamp([run.created_at])
    last_at = _last_timestamp(step_times) or _last_timestamp([run.updated_at])
    by_step = _step_timestamps(steps)

    return {
        "run_id": run.run_id,
        "stage": run.stage,
        "attempt": run.attempt,
        "state": run.state,
        "worker": run.worker,
        "started_at": first_at.isoformat() if first_at is not None else "",
        "completed_at": last_at.isoformat() if last_at is not None else "",
        "total_seconds": _seconds_between(first_at, last_at),
        "setup_seconds": _seconds_between(by_step.get("contract_built"), by_step.get("executor_started")),
        "executor_seconds": _seconds_between(by_step.get("executor_started"), by_step.get("executor_completed")),
        "postprocess_seconds": _seconds_between(by_step.get("executor_completed"), last_at),
        "gate_seconds": _seconds_between(by_step.get("result_submitted"), by_step.get("gate_evaluated")),
        "state_advance_seconds": _seconds_between(by_step.get("gate_evaluated"), by_step.get("state_advanced")),
        "last_step": str(steps[-1].get("step", "")) if steps else "",
        "last_step_status": str(steps[-1].get("status", "")) if steps else "",
        "steps": _step_timings(steps),
    }


def stage_run_timings(runs: Iterable[StageRunRecord]) -> list[dict[str, Any]]:
    return [stage_run_timing(run) for run in sorted(runs, key=_run_sort_key)]


def format_duration(seconds: object) -> str:
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "n/a"
    if seconds < 1:
        return f"{seconds:.3f}s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(int(round(seconds)), 60)
    if minutes < 60:
        return f"{minutes}m{remainder:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m{remainder:02d}s"


def _step_timings(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first_at: datetime | None = None
    previous_at: datetime | None = None
    for step in steps:
        at = _parse_timestamp(step.get("at"))
        if first_at is None:
            first_at = at
        rows.append(
            {
                "step": str(step.get("step", "")),
                "status": str(step.get("status", "")),
                "at": at.isoformat() if at is not None else "",
                "elapsed_seconds": _seconds_between(first_at, at),
                "since_previous_seconds": _seconds_between(previous_at, at),
            }
        )
        if at is not None:
            previous_at = at
    return rows


def _step_timestamps(steps: list[dict[str, Any]]) -> dict[str, datetime]:
    timestamps: dict[str, datetime] = {}
    for step in steps:
        name = str(step.get("step", ""))
        at = _parse_timestamp(step.get("at"))
        if name and at is not None:
            timestamps[name] = at
    return timestamps


def _run_sort_key(run: StageRunRecord) -> tuple[str, int, str]:
    return (run.created_at or run.run_id, run.attempt, run.stage)


def _first_timestamp(values: list[object]) -> datetime | None:
    timestamps = [value for value in (_parse_timestamp(item) for item in values) if value is not None]
    return min(timestamps) if timestamps else None


def _last_timestamp(values: list[object]) -> datetime | None:
    timestamps = [value for value in (_parse_timestamp(item) for item in values) if value is not None]
    return max(timestamps) if timestamps else None


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round(max((end - start).total_seconds(), 0.0), 3)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
