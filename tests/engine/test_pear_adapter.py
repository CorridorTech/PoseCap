from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from posecap_contracts import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    PosePayload,
)
from posecap_engine import pear_adapter
from posecap_engine.config import PEAR_MODELS_REVISION
from posecap_engine.errors import CaptureUnavailableError
from posecap_engine.pear_adapter import PearFrameSource, PearLiveConfig


def test_pear_frame_source_reports_missing_external_checkout(tmp_path: Path) -> None:
    source = PearFrameSource(tmp_path / "missing-pear", source=0)

    with pytest.raises(CaptureUnavailableError, match="PEAR checkout not found"):
        next(source.frames())


def test_pear_frame_source_emits_no_person_status_and_releases_capture(tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    capture = _FakeCapture()
    runtime = _FakeRuntime([None])
    source = PearFrameSource(
        pear_root,
        source=2,
        runtime_factory=lambda _config: runtime,
        capture_factory=lambda _config: capture,
        clock=lambda: 123.5,
    )

    frames = source.frames()
    try:
        frame = next(frames)
    finally:
        frames.close()

    assert (frame.schema_version, frame.seq, frame.captured_at, frame.status, frame.pose) == (
        1,
        0,
        123.5,
        "no_person",
        None,
    )
    assert runtime.seen_images == 1
    assert capture.released


def test_pear_frame_source_emits_ok_frame_after_no_person(tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    runtime = _FakeRuntime([None, _payload()])
    source = PearFrameSource(
        pear_root,
        source=0,
        runtime_factory=lambda _config: runtime,
        capture_factory=lambda _config: _FakeCapture(),
        clock=_FakeClock([10.0, 10.5]),
    )

    frames = source.frames()
    try:
        first = next(frames)
        second = next(frames)
    finally:
        frames.close()

    assert (first.seq, first.status, first.pose) == (0, "no_person", None)
    assert (second.seq, second.status) == (1, "ok")
    assert second.pose == _payload()


def test_pear_frame_source_fails_after_consecutive_camera_read_failures(
    tmp_path: Path,
) -> None:
    pear_root = _pear_checkout(tmp_path)
    capture = _FakeCapture([None, None])
    runtime = _FakeRuntime([_payload()])
    source = PearFrameSource(
        pear_root,
        source=2,
        runtime_factory=lambda _config: runtime,
        capture_factory=lambda _config: capture,
        max_camera_read_failures=2,
    )

    with pytest.raises(CaptureUnavailableError, match="camera index 2 did not return frames"):
        next(source.frames())

    assert capture.released
    assert capture.reads == 2
    assert runtime.seen_images == 0


def test_pear_frame_source_ends_stream_cleanly_at_video_eof(tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    capture = _FakeFiniteCapture(frame_count=2)
    runtime = _FakeRuntime([_payload(), _payload()])
    source = PearFrameSource(
        pear_root,
        source="assets/dance.mp4",
        runtime_factory=lambda _config: runtime,
        capture_factory=lambda _config: capture,
        clock=_FakeClock([1.0, 2.0]),
    )

    frames = list(source.frames())

    assert [frame.seq for frame in frames] == [0, 1]
    assert all(frame.status == "ok" for frame in frames)
    assert capture.released
    assert runtime.seen_images == 2


def test_video_file_capture_opens_path_reads_rgb_and_flags_eof() -> None:
    cv2 = _FakeCv2(frames=[np.zeros((2, 2, 3), dtype=np.uint8)])
    config = PearLiveConfig(pear_root=Path("pear"), source="assets/dance.mp4")

    capture = pear_adapter._VideoFileCapture(config, cv2)

    assert cv2.opened_with == "assets/dance.mp4"
    assert cv2.prop_sets == []
    assert not capture.exhausted
    assert capture.read_rgb() is not None
    assert capture.read_rgb() is None
    assert capture.exhausted


def test_video_file_capture_reports_unopenable_file() -> None:
    cv2 = _FakeCv2(frames=[], openable=False)
    config = PearLiveConfig(pear_root=Path("pear"), source="missing.mp4")

    with pytest.raises(CaptureUnavailableError, match="could not open video file missing.mp4"):
        pear_adapter._VideoFileCapture(config, cv2)

    assert cv2.capture_released


def test_open_live_capture_selects_by_source_type(monkeypatch: pytest.MonkeyPatch) -> None:
    cv2 = _FakeCv2(frames=[])
    monkeypatch.setattr(pear_adapter, "_import_optional", lambda _name, _display: cv2)

    file_capture = pear_adapter._open_live_capture(
        PearLiveConfig(pear_root=Path("pear"), source="assets/dance.mp4")
    )
    camera_capture = pear_adapter._open_live_capture(
        PearLiveConfig(pear_root=Path("pear"), source=0)
    )

    assert isinstance(file_capture, pear_adapter._VideoFileCapture)
    assert isinstance(camera_capture, pear_adapter._OpenCvLiveCapture)


def test_load_pear_runtime_requires_cuda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pear_root = _pear_checkout(tmp_path)
    modules = SimpleNamespace(
        torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    )
    monkeypatch.setattr(pear_adapter, "_load_pear_modules", lambda _pear_root: modules)

    with pytest.raises(CaptureUnavailableError, match="requires CUDA"):
        pear_adapter._load_pear_runtime(PearLiveConfig(pear_root=pear_root, source=0))


def test_load_pear_runtime_uses_pinned_weights_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pear_root = _pear_checkout(tmp_path)
    calls: dict[str, object] = {}
    loaded_layers: list[tuple[object, bool]] = []

    class FakeTorch:
        cuda = SimpleNamespace(is_available=lambda: True)

        def set_float32_matmul_precision(self, value: str) -> None:
            calls["matmul_precision"] = value

        def load(self, path: str, *, map_location: str, weights_only: bool) -> dict[str, object]:
            calls["torch_load"] = (path, map_location, weights_only)
            return {"backbone": object(), "head": object()}

    class FakeLayer:
        def load_state_dict(self, state: object, *, strict: bool) -> None:
            loaded_layers.append((state, strict))

    class FakeModel:
        def __init__(self, config: object) -> None:
            calls["model_config"] = config
            self.backbone = FakeLayer()
            self.head = FakeLayer()

        def cuda(self) -> "FakeModel":
            calls["model_cuda"] = True
            return self

        def eval(self) -> None:
            calls["model_eval"] = True

    def fake_hf_download(**kwargs: object) -> str:
        calls["hf_download"] = kwargs
        return "weights.pt"

    modules = pear_adapter._PearModules(
        torch=FakeTorch(),
        cv2=object(),
        transforms=SimpleNamespace(ToTensor=lambda: object()),
        yolo_class=lambda path: calls.setdefault("yolo_path", path),
        hf_hub_download=fake_hf_download,
        lightning=SimpleNamespace(
            fabric=SimpleNamespace(seed_everything=lambda seed: calls.setdefault("seed", seed))
        ),
        ehm_pipeline_class=FakeModel,
        config_dict_class=lambda **kwargs: kwargs,
        add_extra_cfgs=lambda config: {"wrapped": config},
    )
    monkeypatch.setattr(pear_adapter, "_load_pear_modules", lambda _pear_root: modules)

    pear_adapter._load_pear_runtime(PearLiveConfig(pear_root=pear_root, source=0))

    assert calls["hf_download"] == {
        "repo_id": "BestWJH/PEAR_models",
        "filename": "ehm_model_stage1.pt",
        "repo_type": "model",
        "revision": PEAR_MODELS_REVISION,
    }
    assert calls["torch_load"] == ("weights.pt", "cpu", True)
    assert calls["yolo_path"] == str(pear_root / "model_zoo" / "yolov8x.pt")


def test_load_pear_runtime_uses_ultralytics_model_name_when_local_yolo_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pear_root = _pear_checkout(tmp_path, with_yolo=False)
    calls: dict[str, object] = {}

    class FakeTorch:
        cuda = SimpleNamespace(is_available=lambda: True)

        def load(self, _path: str, *, map_location: str, weights_only: bool) -> dict[str, object]:
            assert (map_location, weights_only) == ("cpu", True)
            return {"backbone": object(), "head": object()}

    class FakeLayer:
        def load_state_dict(self, _state: object, *, strict: bool) -> None:
            assert strict is False

    class FakeModel:
        def __init__(self, _config: object) -> None:
            self.backbone = FakeLayer()
            self.head = FakeLayer()

        def cuda(self) -> "FakeModel":
            return self

        def eval(self) -> None:
            return None

    modules = pear_adapter._PearModules(
        torch=FakeTorch(),
        cv2=object(),
        transforms=SimpleNamespace(ToTensor=lambda: object()),
        yolo_class=lambda path: calls.setdefault("yolo_path", path),
        hf_hub_download=lambda **_kwargs: "weights.pt",
        lightning=SimpleNamespace(fabric=SimpleNamespace(seed_everything=lambda _seed: None)),
        ehm_pipeline_class=FakeModel,
        config_dict_class=lambda **kwargs: kwargs,
        add_extra_cfgs=lambda config: config,
    )
    monkeypatch.setattr(pear_adapter, "_load_pear_modules", lambda _pear_root: modules)

    pear_adapter._load_pear_runtime(PearLiveConfig(pear_root=pear_root, source=0))

    assert calls["yolo_path"] == "yolov8x.pt"


def test_load_pear_runtime_runs_upstream_initialization_from_pear_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pear_root = _pear_checkout(tmp_path)
    monkeypatch.chdir(tmp_path)
    relative_pear_root = Path("pear")
    starting_cwd = Path.cwd()
    calls: dict[str, object] = {}

    class FakeTorch:
        cuda = SimpleNamespace(is_available=lambda: True)

        def load(self, _path: str, *, map_location: str, weights_only: bool) -> dict[str, object]:
            assert (map_location, weights_only) == ("cpu", True)
            return {"backbone": object(), "head": object()}

    class FakeLayer:
        def load_state_dict(self, _state: object, *, strict: bool) -> None:
            assert strict is False

    class FakeModel:
        def __init__(self, _config: object) -> None:
            calls["model_cwd"] = Path.cwd()
            self.backbone = FakeLayer()
            self.head = FakeLayer()

        def cuda(self) -> "FakeModel":
            return self

        def eval(self) -> None:
            return None

    def fake_yolo(path: str) -> object:
        calls["yolo_cwd"] = Path.cwd()
        calls["yolo_path"] = path
        return object()

    modules = pear_adapter._PearModules(
        torch=FakeTorch(),
        cv2=object(),
        transforms=SimpleNamespace(ToTensor=lambda: object()),
        yolo_class=fake_yolo,
        hf_hub_download=lambda **_kwargs: "weights.pt",
        lightning=SimpleNamespace(fabric=SimpleNamespace(seed_everything=lambda _seed: None)),
        ehm_pipeline_class=FakeModel,
        config_dict_class=lambda **kwargs: kwargs,
        add_extra_cfgs=lambda config: config,
    )

    def fake_load_modules(load_root: Path) -> pear_adapter._PearModules:
        calls["load_root"] = load_root
        return modules

    monkeypatch.setattr(pear_adapter, "_load_pear_modules", fake_load_modules)

    pear_adapter._load_pear_runtime(PearLiveConfig(pear_root=relative_pear_root, source=0))

    assert calls["load_root"] == pear_root
    assert calls["model_cwd"] == pear_root
    assert calls["yolo_cwd"] == pear_root
    assert Path.cwd() == starting_cwd


def test_pose_payload_from_outputs_converts_pear_rotations_to_contract_payload() -> None:
    cv2 = pytest.importorskip("cv2")
    identity = np.eye(3, dtype=np.float32)
    outputs = {
        "body_param": {
            "global_pose": identity.reshape(1, 1, 3, 3),
            "body_pose": np.tile(identity, (1, NUM_BODY_JOINTS, 1, 1)),
            "left_hand_pose": np.tile(identity, (1, NUM_HAND_JOINTS, 1, 1)),
            "right_hand_pose": np.tile(identity, (1, NUM_HAND_JOINTS, 1, 1)),
            "shape": np.arange(NUM_BETAS + 2, dtype=np.float32).reshape(1, -1),
            "exp": np.arange(NUM_EXPRESSION, dtype=np.float32).reshape(1, -1),
        },
        "flame_param": {
            "jaw_params": np.asarray([[0.1, 0.2, 0.3]], dtype=np.float32),
        },
        "pd_cam": np.asarray(
            [
                [
                    [1.0, 0.0, 0.0, 4.0],
                    [0.0, 1.0, 0.0, 5.0],
                    [0.0, 0.0, 1.0, 6.0],
                    [0.0, 0.0, 0.0, 1.0],
                ]
            ],
            dtype=np.float32,
        ),
    }

    payload = pear_adapter._pose_payload_from_outputs(outputs, cv2)

    assert payload.global_orient == [0.0, 0.0, 0.0]
    assert len(payload.body_pose) == NUM_BODY_JOINTS
    assert len(payload.left_hand_pose) == NUM_HAND_JOINTS
    assert len(payload.right_hand_pose) == NUM_HAND_JOINTS
    assert payload.body_pose[0] == [0.0, 0.0, 0.0]
    assert payload.jaw_pose == pytest.approx([0.1, 0.2, 0.3])
    assert payload.betas == pytest.approx(list(range(NUM_BETAS)))
    assert payload.expression == pytest.approx(list(range(NUM_EXPRESSION)))
    assert payload.transl == pytest.approx([4.0, 5.0, 6.0])


def _pear_checkout(tmp_path: Path, *, with_yolo: bool = True) -> Path:
    pear_root = tmp_path / "pear"
    (pear_root / "models").mkdir(parents=True)
    (pear_root / "utils").mkdir()
    (pear_root / "configs").mkdir()
    (pear_root / "configs" / "infer.yaml").write_text("model: infer\n", encoding="utf-8")
    if with_yolo:
        (pear_root / "model_zoo").mkdir()
        (pear_root / "model_zoo" / "yolov8x.pt").write_text("weights", encoding="utf-8")
    return pear_root


def _payload() -> PosePayload:
    return PosePayload(
        global_orient=[0.0, 0.0, 0.0],
        body_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_BODY_JOINTS)],
        left_hand_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)],
        right_hand_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)],
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.0 for _ in range(NUM_BETAS)],
        expression=[0.0 for _ in range(NUM_EXPRESSION)],
        transl=[0.0, 0.0, 0.0],
    )


class _FakeCapture:
    def __init__(self, images: list[object | None] | None = None) -> None:
        self._images = images or [np.zeros((2, 2, 3), dtype=np.uint8)]
        self.exhausted = False
        self.reads = 0
        self.released = False

    def read_rgb(self) -> object | None:
        index = min(self.reads, len(self._images) - 1)
        self.reads += 1
        return self._images[index]

    def release(self) -> None:
        self.released = True


class _FakeFiniteCapture:
    """Mimics _VideoFileCapture: yields frame_count frames, then EOF with exhausted set."""

    def __init__(self, frame_count: int) -> None:
        self._remaining = frame_count
        self.exhausted = False
        self.released = False

    def read_rgb(self) -> object | None:
        if self._remaining <= 0:
            self.exhausted = True
            return None
        self._remaining -= 1
        return np.zeros((2, 2, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released = True


class _FakeCv2:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    COLOR_BGR2RGB = 4

    def __init__(self, frames: list[object], *, openable: bool = True) -> None:
        self._frames = list(frames)
        self._openable = openable
        self.opened_with: object | None = None
        self.prop_sets: list[tuple[int, object]] = []
        self.capture_released = False

    def VideoCapture(self, source: object) -> "_FakeCv2":  # noqa: N802 - mimics cv2 API
        self.opened_with = source
        return self

    def isOpened(self) -> bool:  # noqa: N802 - mimics cv2 API
        return self._openable

    def read(self) -> tuple[bool, object | None]:
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def set(self, prop: int, value: object) -> None:
        self.prop_sets.append((prop, value))

    def cvtColor(self, frame: object, code: int) -> object:  # noqa: N802 - mimics cv2 API
        return frame

    def release(self) -> None:
        self.capture_released = True


class _FakeRuntime:
    def __init__(self, outcomes: list[PosePayload | None]) -> None:
        self._outcomes = outcomes
        self.seen_images = 0

    def infer(self, rgb_image: object) -> PosePayload | None:
        assert rgb_image is not None
        outcome = self._outcomes[self.seen_images]
        self.seen_images += 1
        return outcome


class _FakeClock:
    def __init__(self, values: list[float]) -> None:
        self._values = values
        self._index = 0

    def __call__(self) -> float:
        value = self._values[self._index]
        self._index += 1
        return value
