"""Media-level invariants for the author-approved video regression fixtures."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import NotRequired, TypedDict, cast

import pytest

pytestmark = [pytest.mark.integration]

_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "video"
_AUTHOR_APPROVED_FIXTURES = (
    "ale_t_pose_1280x720_30fps.mp4",
    "ale_upper_body_dynamic_1280x720_30fps.mp4",
    "ale_full_body_dance_1280x720_30fps.mp4",
    "ale_spin_1280x720_30fps.mp4",
)
_MAX_FIXTURE_BYTES = 5 * 1024 * 1024


class _StreamProbe(TypedDict):
    codec_type: str
    width: int
    height: int
    r_frame_rate: str
    nb_read_frames: str


class _FormatProbe(TypedDict):
    duration: str
    tags: NotRequired[dict[str, str]]


class _Probe(TypedDict):
    streams: list[_StreamProbe]
    format: _FormatProbe


@pytest.mark.parametrize("fixture_name", _AUTHOR_APPROVED_FIXTURES)
def test_author_approved_fixture_is_small_video_only_and_frame_exact(
    fixture_name: str,
) -> None:
    ffprobe = shutil.which("ffprobe")
    assert ffprobe is not None, "ffprobe is required to validate video fixture media invariants"

    fixture = _FIXTURE_DIR / fixture_name
    assert fixture.stat().st_size < _MAX_FIXTURE_BYTES

    probe = _probe(ffprobe, fixture)
    streams = probe["streams"]
    assert len(streams) == 1
    stream = streams[0]
    assert stream["codec_type"] == "video"
    assert stream["width"] == 1280
    assert stream["height"] == 720
    assert stream["r_frame_rate"] == "30/1"
    assert stream["nb_read_frames"] == "240"
    assert float(probe["format"]["duration"]) == pytest.approx(8.0)

    tags = probe["format"].get("tags", {})
    assert "creation_time" not in tags
    assert "timecode" not in tags


def _probe(ffprobe: str, fixture: Path) -> _Probe:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate,nb_read_frames:format=duration:format_tags",
            "-of",
            "json",
            str(fixture),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return cast(_Probe, json.loads(completed.stdout))
