import numpy as np
import pytest
from posecap_addon.apply_timer import BpyArmaturePoseWriter, PoseApplyTimer, tag_view3d_redraw
from posecap_addon.instrumentation import ApplyTimeInstrumentation
from posecap_contracts import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    SCHEMA_VERSION,
    PoseFrame,
    PosePayload,
)
from posecap_core import KEYFRAME_DATA_PATH, BoneRotation, PoseApplication


def test_pose_apply_timer_applies_latest_ok_frame_and_reschedules() -> None:
    stream = _FakeStream(
        [
            PoseFrame(SCHEMA_VERSION, 1, 100.0, "ok", _payload()),
        ]
    )
    writer = _FakeWriter()
    timer = PoseApplyTimer(stream, writer, interval_seconds=0.25)

    assert timer.tick() == 0.25

    assert len(writer.applied) == 1
    assert writer.applied[0][0].bone_name == "pelvis"
    assert writer.redraws == 1


def test_pose_apply_timer_holds_last_pose_on_no_person_frame() -> None:
    stream = _FakeStream(
        [
            PoseFrame(SCHEMA_VERSION, 2, 100.5, "no_person", None),
        ]
    )
    writer = _FakeWriter()
    timer = PoseApplyTimer(stream, writer, interval_seconds=0.25)

    assert timer.tick() == 0.25

    assert writer.applied == []
    assert writer.redraws == 0


def test_pose_apply_timer_records_apply_time_for_applied_frame() -> None:
    stream = _FakeStream(
        [
            PoseFrame(SCHEMA_VERSION, 1, 100.0, "ok", _payload()),
        ]
    )
    writer = _FakeWriter()
    logger = _FakeLogger()
    instrumentation = ApplyTimeInstrumentation(
        logger=logger,
        clock=_ManualClock([0.0, 10.0, 10.025]),
        interval_seconds=0.01,
    )
    timer = PoseApplyTimer(
        stream,
        writer,
        interval_seconds=0.25,
        instrumentation=instrumentation,
    )

    assert timer.tick() == 0.25

    message, args = logger.infos[0]
    assert message == "pose_apply_time frames=%d avg_ms=%.3f max_ms=%.3f"
    assert args[0] == 1
    assert args[1] == pytest.approx(25.0)
    assert args[2] == pytest.approx(25.0)


def test_pose_apply_timer_warns_once_for_invalid_target_then_resumes() -> None:
    stream = _FakeStream(
        [
            PoseFrame(SCHEMA_VERSION, 1, 100.0, "ok", _payload()),
            PoseFrame(SCHEMA_VERSION, 2, 100.5, "ok", _payload()),
            PoseFrame(SCHEMA_VERSION, 3, 101.0, "ok", _payload()),
        ]
    )
    writer = _FakeWriter(valid_states=[False, False, True])
    warnings: list[str] = []
    timer = PoseApplyTimer(stream, writer, interval_seconds=0.25, on_warning=warnings.append)

    assert timer.tick() == 0.25
    assert timer.tick() == 0.25
    assert timer.tick() == 0.25

    assert warnings == ["target armature is unavailable"]
    assert len(writer.applied) == 1
    assert writer.redraws == 1


def test_bpy_armature_pose_writer_sets_quaternion_and_keyframes() -> None:
    armature = _FakeArmature(["left_hip"])
    writer = BpyArmaturePoseWriter(armature, redraw=lambda: armature.redraws.append("redraw"))
    plan = PoseApplication(
        clear_bones=frozenset({"left_hip"}),
        rotations=(BoneRotation("left_hip", np.asarray([0.5, 0.5, 0.5, 0.5])),),
    )

    assert writer.is_valid()
    writer.apply(plan, insert_keyframes=True)
    writer.tag_redraw()

    bone = armature.pose.bones["left_hip"]
    assert bone.rotation_mode == "QUATERNION"
    assert bone.rotation_quaternion == (0.5, 0.5, 0.5, 0.5)
    assert bone.keyframes == [KEYFRAME_DATA_PATH]
    assert armature.redraws == ["redraw"]


def test_bpy_armature_pose_writer_preserves_existing_keyframes_when_not_recording() -> None:
    armature = _FakeArmature(["left_hip"])
    bone = armature.pose.bones["left_hip"]
    bone.keyframes.extend([KEYFRAME_DATA_PATH, KEYFRAME_DATA_PATH])
    writer = BpyArmaturePoseWriter(armature)
    plan = PoseApplication(
        clear_bones=frozenset({"left_hip"}),
        rotations=(BoneRotation("left_hip", np.asarray([0.5, 0.5, 0.5, 0.5])),),
    )

    before_count = len(bone.keyframes)

    writer.apply(plan, insert_keyframes=False)

    assert bone.rotation_mode == "QUATERNION"
    assert bone.rotation_quaternion == (0.5, 0.5, 0.5, 0.5)
    assert len(bone.keyframes) == before_count
    assert bone.keyframes == [KEYFRAME_DATA_PATH, KEYFRAME_DATA_PATH]


def test_bpy_armature_pose_writer_treats_removed_armature_as_invalid() -> None:
    writer = BpyArmaturePoseWriter(_RemovedArmature())

    assert not writer.is_valid()


def test_tag_view3d_redraw_marks_only_3d_view_areas() -> None:
    view = _FakeArea("VIEW_3D")
    text = _FakeArea("TEXT_EDITOR")
    context = _FakeContext([view, text])

    tag_view3d_redraw(context)

    assert view.redraws == 1
    assert text.redraws == 0


class _FakeStream:
    def __init__(self, frames: list[PoseFrame]) -> None:
        self._frames = frames

    def latest(self) -> PoseFrame | None:
        if not self._frames:
            return None
        return self._frames.pop(0)

    def close(self) -> None:
        return None


class _FakeWriter:
    def __init__(self, *, valid_states: list[bool] | None = None) -> None:
        self.applied: list[tuple] = []
        self.redraws = 0
        self._valid_states = valid_states or [True]
        self._valid_checks = 0

    def is_valid(self) -> bool:
        index = min(self._valid_checks, len(self._valid_states) - 1)
        self._valid_checks += 1
        return self._valid_states[index]

    def apply(self, plan, *, insert_keyframes: bool) -> None:
        self.applied.append(plan.rotations)

    def tag_redraw(self) -> None:
        self.redraws += 1


class _FakeLogger:
    def __init__(self) -> None:
        self.infos: list[tuple[str, tuple[object, ...]]] = []

    def info(self, message: str, *args: object) -> None:
        self.infos.append((message, args))


class _ManualClock:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def __call__(self) -> float:
        if not self._values:
            raise AssertionError("clock exhausted")
        return self._values.pop(0)


class _FakeArmature:
    def __init__(self, bone_names: list[str]) -> None:
        self.pose = _FakePose(bone_names)
        self.redraws: list[str] = []


class _RemovedArmature:
    @property
    def pose(self):
        raise ReferenceError("StructRNA of type Object has been removed")


class _FakeContext:
    def __init__(self, areas: list["_FakeArea"]) -> None:
        self.window_manager = _FakeWindowManager(areas)


class _FakeWindowManager:
    def __init__(self, areas: list["_FakeArea"]) -> None:
        self.windows = [_FakeWindow(areas)]


class _FakeWindow:
    def __init__(self, areas: list["_FakeArea"]) -> None:
        self.screen = _FakeScreen(areas)


class _FakeScreen:
    def __init__(self, areas: list["_FakeArea"]) -> None:
        self.areas = areas


class _FakeArea:
    def __init__(self, area_type: str) -> None:
        self.type = area_type
        self.redraws = 0

    def tag_redraw(self) -> None:
        self.redraws += 1


class _FakePose:
    def __init__(self, bone_names: list[str]) -> None:
        self.bones = _FakeBones(bone_names)


class _FakeBones:
    def __init__(self, bone_names: list[str]) -> None:
        self._bones = {name: _FakeBone(name) for name in bone_names}

    def __iter__(self):
        return iter(self._bones.values())

    def __getitem__(self, name: str):
        return self._bones[name]

    def get(self, name: str):
        return self._bones.get(name)


class _FakeBone:
    def __init__(self, name: str) -> None:
        self.name = name
        self.rotation_mode = "XYZ"
        self.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        self.keyframes: list[str] = []

    def keyframe_insert(self, *, data_path: str) -> None:
        self.keyframes.append(data_path)


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
