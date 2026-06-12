import json
from pathlib import Path

import pytest
from conftest import make_no_person_frame, make_ok_frame
from corridorrig_contracts import (
    FrameDecodeError,
    decode_pose_frame,
    encode_pose_frame,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_ok_frame_round_trip() -> None:
    frame = make_ok_frame()
    assert decode_pose_frame(encode_pose_frame(frame)) == frame


def test_no_person_frame_round_trip() -> None:
    frame = make_no_person_frame()
    assert decode_pose_frame(encode_pose_frame(frame)) == frame


def test_encoding_is_canonical_single_line() -> None:
    encoded = encode_pose_frame(make_ok_frame())
    assert "\n" not in encoded
    assert encoded == json.dumps(json.loads(encoded), sort_keys=True, separators=(",", ":"))


def test_golden_fixture_ok_frame_pins_wire_format() -> None:
    fixture = (FIXTURES / "pose_frame_ok.json").read_text(encoding="utf-8").strip()
    frame = decode_pose_frame(fixture)
    assert frame == make_ok_frame()
    assert encode_pose_frame(frame) == fixture


def test_golden_fixture_no_person_frame_pins_wire_format() -> None:
    fixture = (FIXTURES / "pose_frame_no_person.json").read_text(encoding="utf-8").strip()
    frame = decode_pose_frame(fixture)
    assert frame == make_no_person_frame()
    assert encode_pose_frame(frame) == fixture


def test_rejects_invalid_json() -> None:
    with pytest.raises(FrameDecodeError, match="invalid JSON"):
        decode_pose_frame("{not json")


def test_rejects_non_object() -> None:
    with pytest.raises(FrameDecodeError, match="JSON object"):
        decode_pose_frame("[1,2,3]")


def test_rejects_unsupported_schema_version() -> None:
    line = encode_pose_frame(make_ok_frame()).replace('"schema_version":1', '"schema_version":99')
    with pytest.raises(FrameDecodeError, match="schema_version"):
        decode_pose_frame(line)


def test_rejects_unknown_status() -> None:
    line = encode_pose_frame(make_no_person_frame()).replace("no_person", "maybe")
    with pytest.raises(FrameDecodeError, match="status"):
        decode_pose_frame(line)


def test_rejects_ok_frame_without_pose() -> None:
    line = encode_pose_frame(make_no_person_frame()).replace("no_person", "ok")
    with pytest.raises(FrameDecodeError, match="requires a pose"):
        decode_pose_frame(line)


def test_rejects_no_person_frame_with_pose() -> None:
    line = encode_pose_frame(make_ok_frame()).replace('"status":"ok"', '"status":"no_person"')
    with pytest.raises(FrameDecodeError, match="must not carry"):
        decode_pose_frame(line)


def test_rejects_wrong_body_pose_length() -> None:
    document = json.loads(encode_pose_frame(make_ok_frame()))
    document["pose"]["body_pose"] = document["pose"]["body_pose"][:-1]
    with pytest.raises(FrameDecodeError, match="body_pose"):
        decode_pose_frame(json.dumps(document))


def test_rejects_wrong_vector_width() -> None:
    document = json.loads(encode_pose_frame(make_ok_frame()))
    document["pose"]["global_orient"] = [0.1, 0.2]
    with pytest.raises(FrameDecodeError, match="global_orient"):
        decode_pose_frame(json.dumps(document))


def test_rejects_non_numeric_values() -> None:
    document = json.loads(encode_pose_frame(make_ok_frame()))
    document["pose"]["jaw_pose"] = [0.0, "x", 0.0]
    with pytest.raises(FrameDecodeError, match="jaw_pose"):
        decode_pose_frame(json.dumps(document))


def test_rejects_boolean_masquerading_as_number() -> None:
    document = json.loads(encode_pose_frame(make_ok_frame()))
    document["captured_at"] = True
    with pytest.raises(FrameDecodeError, match="captured_at"):
        decode_pose_frame(json.dumps(document))


def test_rejects_missing_required_key() -> None:
    document = json.loads(encode_pose_frame(make_ok_frame()))
    del document["seq"]
    with pytest.raises(FrameDecodeError, match="seq"):
        decode_pose_frame(json.dumps(document))
