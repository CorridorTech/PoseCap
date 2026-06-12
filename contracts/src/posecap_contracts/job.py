"""Job status document for batch and single-capture work.

One JSON document per job, written via temp file + atomic rename; replaces the
POC's `_progress.txt` / `_failed.txt` sidecar pair.
"""

import json
from dataclasses import dataclass
from typing import Literal, cast

from .errors import JobStatusDecodeError

JobState = Literal["queued", "running", "done", "failed"]

_VALID_STATES: frozenset[str] = frozenset({"queued", "running", "done", "failed"})


@dataclass(frozen=True)
class JobStatus:
    """Progress is a fraction in [0.0, 1.0]; message is human-readable."""

    state: JobState
    progress: float
    message: str


def encode_job_status(status: JobStatus) -> str:
    """Return the canonical single-line JSON form of a job status document."""
    document = {
        "state": status.state,
        "progress": status.progress,
        "message": status.message,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def decode_job_status(text: str) -> JobStatus:
    """Parse and validate a job status document; raises JobStatusDecodeError on violations."""
    raw = _parse_object(text)
    state = _require_state(raw)
    progress = _require_progress(raw)
    message = raw.get("message")
    if not isinstance(message, str):
        raise JobStatusDecodeError("message must be a string")
    return JobStatus(state=state, progress=progress, message=message)


def _parse_object(text: str) -> dict[str, object]:
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JobStatusDecodeError(f"invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise JobStatusDecodeError("job status must be a JSON object")
    items = cast("dict[object, object]", parsed)
    return {str(key): value for key, value in items.items()}


def _require_state(raw: dict[str, object]) -> JobState:
    value = raw.get("state")
    if isinstance(value, str) and value in _VALID_STATES:
        return cast("JobState", value)
    raise JobStatusDecodeError(f"state must be one of {sorted(_VALID_STATES)}, got: {value!r}")


def _require_progress(raw: dict[str, object]) -> float:
    value = raw.get("progress")
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise JobStatusDecodeError("progress must be a number")
    progress = float(value)
    if progress < 0.0 or progress > 1.0:
        raise JobStatusDecodeError(f"progress must be within [0.0, 1.0], got: {progress}")
    return progress
