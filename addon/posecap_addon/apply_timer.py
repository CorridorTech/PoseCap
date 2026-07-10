"""Main-thread pose application timer for the Blender addon."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import numpy as np
from posecap_contracts import PoseFrame
from posecap_core import (
    KEYFRAME_DATA_PATH,
    LimbFilter,
    PoseApplication,
    PoseStream,
    plan_pose_application,
)

from .instrumentation import ApplyTimeInstrumentation

WarningCallback = Callable[[str], None]
RecoveryCallback = Callable[[], None]


class PoseWriter(Protocol):
    """Main-thread adapter that writes a planned pose to a target armature."""

    def is_valid(self) -> bool: ...

    def apply(self, plan: PoseApplication, *, insert_keyframes: bool) -> None: ...

    def tag_redraw(self) -> None: ...


class PoseApplyTimer:
    """Consume latest-wins pose frames and apply them on Blender's timer thread."""

    def __init__(
        self,
        stream: PoseStream,
        writer: PoseWriter,
        *,
        limb_filter: LimbFilter | None = None,
        interval_seconds: float = 1.0 / 60.0,
        apply_orientation_fix: bool = True,
        apply_world_position: bool = False,
        insert_keyframes: bool = False,
        on_warning: WarningCallback | None = None,
        on_recovery: RecoveryCallback | None = None,
        instrumentation: ApplyTimeInstrumentation | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._stream = stream
        self._writer = writer
        self._limb_filter = limb_filter or LimbFilter()
        self._interval_seconds = interval_seconds
        self._apply_orientation_fix = apply_orientation_fix
        self._apply_world_position = apply_world_position
        self._translation_origin: np.ndarray | None = None
        self._insert_keyframes = insert_keyframes
        self._on_warning = on_warning
        self._on_recovery = on_recovery
        self._instrumentation = instrumentation
        self._previous_quaternions: dict[str, np.ndarray] = {}
        self._reported_invalid_target = False
        self._running = True

    def tick(self) -> float | None:
        """Apply the newest frame, then return the next timer delay."""
        if not self._running:
            return None
        frame = self._stream.latest()
        if frame is None:
            return self._interval_seconds
        instrumentation = self._instrumentation
        if instrumentation is None:
            self._apply_frame(frame)
            return self._interval_seconds
        started_at = instrumentation.mark_start()
        applied = self._apply_frame(frame)
        if applied:
            instrumentation.record_since(started_at)
        return self._interval_seconds

    def stop(self) -> None:
        """Stop the timer and close its stream."""
        self._running = False
        self._stream.close()

    def _apply_frame(self, frame: PoseFrame) -> bool:
        if frame.status == "no_person" or frame.pose is None:
            return False
        if not self._writer.is_valid():
            self._warn_invalid_target()
            return False
        recovered = self._reported_invalid_target
        self._reported_invalid_target = False
        if self._apply_world_position and self._translation_origin is None:
            self._translation_origin = np.asarray(frame.pose.transl, dtype=np.float64)
        plan = plan_pose_application(
            frame.pose,
            self._limb_filter,
            previous_quaternions=self._previous_quaternions,
            apply_orientation_fix=self._apply_orientation_fix,
            apply_world_position=self._apply_world_position,
            translation_origin=self._translation_origin,
        )
        self._writer.apply(plan, insert_keyframes=self._insert_keyframes)
        self._writer.tag_redraw()
        self._previous_quaternions = {
            rotation.bone_name: rotation.quaternion for rotation in plan.rotations
        }
        if recovered and self._on_recovery is not None:
            self._on_recovery()
        return True

    def _warn_invalid_target(self) -> None:
        if self._reported_invalid_target:
            return
        self._reported_invalid_target = True
        if self._on_warning is not None:
            self._on_warning("target armature is unavailable")


class BpyArmaturePoseWriter:
    """Duck-typed Blender armature writer for a planned pose application."""

    def __init__(self, armature: Any, *, redraw: Callable[[], None] | None = None) -> None:
        self._armature = armature
        self._redraw = redraw

    def is_valid(self) -> bool:
        return self._pose_bones() is not None

    def apply(self, plan: PoseApplication, *, insert_keyframes: bool) -> None:
        bones = self._pose_bones()
        if bones is None:
            return
        self._clear_bones(bones, plan)
        for rotation in plan.rotations:
            bone = _bone_by_name(bones, rotation.bone_name)
            if bone is not None:
                _write_quaternion(bone, rotation.quaternion, insert_keyframes=insert_keyframes)
        if plan.world_offset is not None:
            self._armature.location = tuple(float(value) for value in plan.world_offset)

    def tag_redraw(self) -> None:
        if self._redraw is not None:
            self._redraw()

    def _pose_bones(self) -> Any | None:
        try:
            pose = self._armature.pose
            return pose.bones
        except (AttributeError, ReferenceError):
            return None

    def _clear_bones(self, bones: Any, plan: PoseApplication) -> None:
        if plan.clear_bones is None:
            for bone in bones:
                _write_quaternion(bone, _IDENTITY_QUATERNION, insert_keyframes=False)
            return
        for bone_name in plan.clear_bones:
            bone = _bone_by_name(bones, bone_name)
            if bone is not None:
                _write_quaternion(bone, _IDENTITY_QUATERNION, insert_keyframes=False)


_IDENTITY_QUATERNION = np.asarray([1.0, 0.0, 0.0, 0.0])


def _bone_by_name(bones: Any, name: str) -> Any | None:
    get = bones.get if hasattr(bones, "get") else None
    if callable(get):
        return get(name)
    try:
        return bones[name]
    except (KeyError, TypeError):
        return None


def _write_quaternion(bone: Any, quaternion: np.ndarray, *, insert_keyframes: bool) -> None:
    bone.rotation_mode = "QUATERNION"
    bone.rotation_quaternion = tuple(float(value) for value in quaternion)
    if insert_keyframes:
        bone.keyframe_insert(data_path=KEYFRAME_DATA_PATH)


def tag_view3d_redraw(context: Any) -> None:
    """Tag every visible 3D viewport area for redraw."""
    window_manager = context.window_manager
    for window in window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
