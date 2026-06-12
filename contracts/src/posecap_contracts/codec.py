"""Encode and decode newline-delimited JSON pose frames.

Encoding is canonical — compact separators, sorted keys — so golden fixtures
can pin the wire format byte for byte.
"""

import json
from typing import cast

from .errors import ContractError, FrameDecodeError
from .frames import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    SCHEMA_VERSION,
    FrameStatus,
    PoseFrame,
    PosePayload,
)


def encode_pose_frame(frame: PoseFrame) -> str:
    """Return the canonical single-line JSON form, without a trailing newline.

    Raises ContractError when the frame breaks the status/pose invariant —
    the encoder must never emit a wire line the decoder would reject.
    """
    if (frame.status == "ok") != (frame.pose is not None):
        raise ContractError(f"status {frame.status!r} is inconsistent with pose presence")
    pose: dict[str, object] | None = None
    if frame.pose is not None:
        pose = {
            "global_orient": frame.pose.global_orient,
            "body_pose": frame.pose.body_pose,
            "left_hand_pose": frame.pose.left_hand_pose,
            "right_hand_pose": frame.pose.right_hand_pose,
            "jaw_pose": frame.pose.jaw_pose,
            "betas": frame.pose.betas,
            "expression": frame.pose.expression,
            "transl": frame.pose.transl,
        }
    document = {
        "schema_version": frame.schema_version,
        "seq": frame.seq,
        "captured_at": frame.captured_at,
        "status": frame.status,
        "pose": pose,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def decode_pose_frame(line: str) -> PoseFrame:
    """Parse and validate one wire line; raises FrameDecodeError on any violation."""
    raw = _parse_object(line)
    schema_version = _require_int(raw, "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise FrameDecodeError(f"unsupported schema_version: {schema_version}")
    seq = _require_int(raw, "seq")
    captured_at = _require_number(raw, "captured_at")
    status = _require_status(raw)
    pose_raw = raw.get("pose")
    if status == "no_person":
        if pose_raw is not None:
            raise FrameDecodeError("a no_person frame must not carry a pose")
        return PoseFrame(schema_version, seq, captured_at, status, None)
    if pose_raw is None:
        raise FrameDecodeError("an ok frame requires a pose")
    return PoseFrame(schema_version, seq, captured_at, status, _decode_payload(pose_raw))


def _parse_object(line: str) -> dict[str, object]:
    try:
        parsed: object = json.loads(line)
    except json.JSONDecodeError as exc:
        raise FrameDecodeError(f"invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise FrameDecodeError("frame must be a JSON object")
    items = cast("dict[object, object]", parsed)
    return {str(key): value for key, value in items.items()}


def _decode_payload(value: object) -> PosePayload:
    if not isinstance(value, dict):
        raise FrameDecodeError("pose must be a JSON object")
    items = cast("dict[object, object]", value)
    raw = {str(key): item for key, item in items.items()}
    return PosePayload(
        global_orient=_floats(raw, "global_orient", 3),
        body_pose=_matrix(raw, "body_pose", NUM_BODY_JOINTS),
        left_hand_pose=_matrix(raw, "left_hand_pose", NUM_HAND_JOINTS),
        right_hand_pose=_matrix(raw, "right_hand_pose", NUM_HAND_JOINTS),
        jaw_pose=_floats(raw, "jaw_pose", 3),
        betas=_floats(raw, "betas", NUM_BETAS),
        expression=_floats(raw, "expression", NUM_EXPRESSION),
        transl=_floats(raw, "transl", 3),
    )


def _require_int(raw: dict[str, object], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise FrameDecodeError(f"{key} must be an integer")
    return value


def _require_number(raw: dict[str, object], key: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise FrameDecodeError(f"{key} must be a number")
    return float(value)


def _require_status(raw: dict[str, object]) -> FrameStatus:
    value = raw.get("status")
    if value == "ok":
        return "ok"
    if value == "no_person":
        return "no_person"
    raise FrameDecodeError(f"status must be 'ok' or 'no_person', got: {value!r}")


def _floats(raw: dict[str, object], key: str, length: int) -> list[float]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise FrameDecodeError(f"{key} must be a list of {length} numbers")
    items = cast("list[object]", raw[key])
    if len(items) != length:
        raise FrameDecodeError(f"{key} must be a list of {length} numbers")
    result: list[float] = []
    for item in items:
        if isinstance(item, bool) or not isinstance(item, int | float):
            raise FrameDecodeError(f"{key} must contain only numbers")
        result.append(float(item))
    return result


def _matrix(raw: dict[str, object], key: str, rows: int) -> list[list[float]]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise FrameDecodeError(f"{key} must be a list of {rows} vectors")
    rows_raw = cast("list[object]", raw[key])
    if len(rows_raw) != rows:
        raise FrameDecodeError(f"{key} must be a list of {rows} vectors")
    wrapped = {f"{key}[{index}]": row for index, row in enumerate(rows_raw)}
    return [_floats(wrapped, name, 3) for name in wrapped]
