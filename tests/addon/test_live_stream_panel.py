"""Behavior tests for the live-stream panel's Pose Backend selector."""

import json
from pathlib import Path

import posecap_addon.live_stream_panel as live_stream_panel
import pytest
from posecap_addon import draw_live_stream_panel
from posecap_addon.ui_state import LifecycleState


class _FakeLayout:
    """Records what the panel drew, mirroring the double in ``test_ui_state``."""

    def __init__(self, *, labels: list[str] | None = None) -> None:
        self.enabled = True
        self.alert = False
        self._labels: list[str] = [] if labels is None else labels

    def row(self, *, align: bool = False) -> "_FakeLayout":
        del align
        return _FakeLayout(labels=self._labels)

    def column(self) -> "_FakeLayout":
        return self.row()

    def box(self) -> "_FakeLayout":
        return self.row()

    def label(self, *, text: str, icon: str = "NONE") -> None:
        del icon
        self._labels.append(text)

    def prop(self, _data: object, property_name: str, **_kwargs: object) -> None:
        del property_name

    def operator(self, operator_id: str, *, text: str = "", icon: str = "NONE") -> None:
        del operator_id, text, icon

    @property
    def labels(self) -> list[str]:
        return self._labels


class _Settings:
    """Protocol-shaped settings double; only ``pose_backend_id`` varies here.

    The class-level annotations are what let it satisfy the settings protocol:
    without them ``lifecycle_state`` infers as ``str``, not the literal type.
    """

    lifecycle_state: LifecycleState
    status_message: str
    target_armature: object | None

    def __init__(self, *, pose_backend_id: str = "__automatic__") -> None:
        self.pose_backend_id = pose_backend_id
        self.lifecycle_state = "STOPPED"
        self.status_message = ""
        self.target_armature = None
        self.camera_index = 0
        self.pear_root = ""
        self.apply_orientation_fix = True
        self.camera_pitch = 0.0
        self.world_position_experimental = False
        self.pose_smoothing = True
        self.show_advanced = False
        self.show_support = False
        self.pose_smoothing_min_cutoff = 1.0
        self.pose_smoothing_beta = 0.5
        self.record_live_mocap = False
        self.detection_confidence = 0.3
        self.detector_model = "yolov8s"
        self.capture_width = 1280
        self.capture_height = 720
        self.apply_arms = True
        self.apply_legs = True
        self.apply_torso = True
        self.character_preset = "AUTO"
        self.character_mapping_json = ""
        self.source_kind = "CAMERA"
        self.video_source = ""
        self.preview_enabled = False


def _write_backend(registry: Path, backend_id: str, display_name: str, accelerator: str) -> None:
    backend_dir = registry / backend_id
    backend_dir.mkdir(parents=True)
    executable = registry / f"{backend_id}.exe"
    executable.touch()
    (backend_dir / "backend.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": backend_id,
                "display_name": display_name,
                "command": [str(executable), "live"],
                "protocol_versions": [1],
                "capabilities": ["body"],
                "compatibility": {
                    "operating_systems": ["windows"],
                    "accelerators": [accelerator],
                    "account": "No account required",
                    "license": "Apache-2.0",
                },
            }
        ),
        encoding="utf-8",
    )


def _two_ready_backends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = tmp_path / "PoseCap" / "backends"
    _write_backend(registry, "pear", "PEAR (NVIDIA CUDA)", "nvidia-cuda")
    _write_backend(registry, "mediapipe", "MediaPipe Lite (CPU)", "cpu")
    monkeypatch.setattr(live_stream_panel.os, "environ", {"LOCALAPPDATA": str(tmp_path)})


def test_panel_names_the_automatic_pick_instead_of_demanding_a_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task 0038: the hint must state what Automatic actually does.

    With two ready backends and no explicit selection the panel used to say
    "Choose a Pose Backend before starting capture." -- a demand the resolver
    no longer makes. It must now name the backend Automatic resolved to.
    """
    _two_ready_backends(tmp_path, monkeypatch)
    layout = _FakeLayout()

    draw_live_stream_panel(layout, _Settings())

    assert "Automatic uses PEAR (NVIDIA CUDA)." in layout.labels
    assert not any("Choose a Pose Backend" in label for label in layout.labels)


def test_panel_stays_quiet_once_the_user_picked_a_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit choice needs no automatic-pick hint."""
    _two_ready_backends(tmp_path, monkeypatch)
    layout = _FakeLayout()

    draw_live_stream_panel(layout, _Settings(pose_backend_id="mediapipe"))

    assert not any("Automatic uses" in label for label in layout.labels)
