"""Temporary-source native retargeting for non-destructive character binding.

The source armature is PoseCap-owned and exists only while capture runs.  It
uses the proven legacy normalization on a copy of the target's armature data;
the user's armature receives only Blender-evaluated pose channels from it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from posecap_core import PoseApplication, PoseBinding, SkeletonPreset, needs_t_pose_re_rest

from .apply_timer import BpyArmaturePoseWriter
from .character_setup import convert_armature


class MatrixRetargetPoseWriter:
    """Drive an untouched target through PoseCap-owned Copy Transforms constraints."""

    def __init__(
        self,
        bpy_module: Any,
        target: Any,
        binding: PoseBinding,
        *,
        redraw: Callable[[], None] | None = None,
    ) -> None:
        self._bpy = bpy_module
        self._target = target
        self._binding = binding
        self._redraw = redraw
        self._source = _create_source(bpy_module, target, binding)
        self._source_writer = BpyArmaturePoseWriter(self._source)
        self._constraints = _create_constraints(target, self._source, binding)

    def is_valid(self) -> bool:
        return self._source_writer.is_valid() and BpyArmaturePoseWriter(self._target).is_valid()

    def apply(self, plan: PoseApplication, *, insert_keyframes: bool) -> None:
        self._source_writer.apply(plan, insert_keyframes=False)
        if insert_keyframes:
            self._bpy.context.view_layer.update()
            _keyframe_visual_pose(self._target, self._binding)
        if plan.world_offset is not None:
            self._target.location = tuple(float(value) for value in plan.world_offset)

    def tag_redraw(self) -> None:
        if self._redraw is not None:
            self._redraw()

    def close(self) -> None:
        """Remove the sole PoseCap-owned intermediary and its copied data."""
        source = self._source
        self._source = None
        _remove_constraints(self._constraints)
        self._constraints = ()
        if source is None:
            return
        data = source.data
        self._bpy.data.objects.remove(source, do_unlink=True)
        if data.users == 0:
            self._bpy.data.armatures.remove(data)


def requires_matrix_retarget(target: Any, binding: PoseBinding) -> bool:
    """Whether this bind pose needs the transient chain-aware evaluator.

    A measured T-pose can use the binding's direct rest compensation.  A
    non-T bind pose still needs Blender to carry connected-bone translation
    through the converted temporary source.
    """
    preset = _source_preset(binding)
    try:
        world = target.matrix_world
        arm_lines = {
            side: (
                tuple(world @ target.pose.bones[preset.mapping[f"{side}_shoulder"]].head),
                tuple(world @ target.pose.bones[preset.mapping[f"{side}_elbow"]].head),
            )
            for side in ("left", "right")
        }
    except (AttributeError, KeyError, ReferenceError, TypeError):
        # A stale or incomplete target must retain the prior conservative
        # runtime path; normal stream validation will report it to the user.
        return True
    return needs_t_pose_re_rest(
        preset,
        {"l": arm_lines["left"], "r": arm_lines["right"]},
    )


def _create_source(bpy_module: Any, target: Any, binding: PoseBinding) -> Any:
    source_data = target.data.copy()
    source = bpy_module.data.objects.new(".PoseCap Intermediary", source_data)
    bpy_module.context.collection.objects.link(source)
    source.matrix_world = target.matrix_world.copy()
    try:
        _activate_only(bpy_module, source)
        convert_armature(
            bpy_module,
            source,
            _source_preset(binding),
            require_deforming_mesh=False,
        )
    except Exception:
        bpy_module.data.objects.remove(source, do_unlink=True)
        if source_data.users == 0:
            bpy_module.data.armatures.remove(source_data)
        raise
    source.hide_render = True
    source.hide_set(True)
    _activate_only(bpy_module, target)
    bpy_module.context.view_layer.update()
    settings = getattr(bpy_module.context.scene, "posecap", None)
    if settings is not None:
        settings.target_armature = target
    return source


def _source_preset(binding: PoseBinding) -> SkeletonPreset:
    mapping = {source_name: bone.target_bone_name for source_name, bone in binding.bones.items()}
    return SkeletonPreset(
        name="posecap-intermediary",
        label="PoseCap intermediary",
        mapping=mapping,
        arm_chains={
            side: tuple(
                (mapping[parent], mapping[child])
                for parent, child in chain
                if parent in mapping and child in mapping
            )
            for side, chain in {
                "l": (
                    ("left_shoulder", "left_elbow"),
                    ("left_elbow", "left_wrist"),
                ),
                "r": (
                    ("right_shoulder", "right_elbow"),
                    ("right_elbow", "right_wrist"),
                ),
            }.items()
        },
        # The intermediary has no durable family label, but every source
        # armature can be measured before conversion.  Treat a T-pose as a
        # verified condition rather than forcing a second rest-pose rewrite:
        # this matches the legacy Mixamo path while still re-resting an
        # A-pose or custom drooped bind pose.
        already_t_pose=True,
    )


def _activate_only(bpy_module: Any, armature: Any) -> None:
    bpy_module.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy_module.context.view_layer.objects.active = armature


def _create_constraints(
    target: Any, source: Any, binding: PoseBinding
) -> tuple[tuple[Any, Any], ...]:
    constraints = []
    for source_name, bound in binding.bones.items():
        target_bone = target.pose.bones.get(bound.target_bone_name)
        if target_bone is None or source_name not in source.pose.bones:
            continue
        constraint = target_bone.constraints.new("COPY_TRANSFORMS")
        constraint.name = "PoseCap temporary retarget"
        constraint.target = source
        constraint.subtarget = source_name
        constraint.owner_space = "POSE"
        constraint.target_space = "POSE"
        constraints.append((target_bone, constraint))
    return tuple(constraints)


def _remove_constraints(constraints: tuple[tuple[Any, Any], ...]) -> None:
    for bone, constraint in constraints:
        try:
            bone.constraints.remove(constraint)
        except (AttributeError, KeyError, ReferenceError):
            continue


def _keyframe_visual_pose(target: Any, binding: PoseBinding) -> None:
    for bound in binding.bones.values():
        bone = target.pose.bones.get(bound.target_bone_name)
        if bone is not None:
            bone.keyframe_insert(data_path="rotation_quaternion", options={"INSERTKEY_VISUAL"})
