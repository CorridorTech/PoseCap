"""Keyframe manager: mark key poses to keep, then bake away the rest.

Live recording lays down a dense key per streamed frame. This manager holds a
sparse set of "key pose" frames the user wants to retain; Bake & Retain visually
bakes the pose range and deletes every intermediate key, leaving clean sparse
keyframes (POC parity). All F-curve access goes through the single
version-compatible `keyframe_io.fcurves_for` helper.

The key-pose list lives on the Scene (persists in the .blend, unlike the POC's
WindowManager list) as `posecap_key_poses` + `posecap_key_poses_index`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .keyframe_io import fcurves_for

KEY_POSES_PROPERTY = "posecap_key_poses"
KEY_POSES_INDEX_PROPERTY = "posecap_key_poses_index"
_ROTATION_PATH_SUFFIX = "rotation_quaternion"


def key_pose_frames(key_poses: Any) -> list[int]:
    """The marked key-pose frames, in collection order."""
    return [int(item.frame) for item in key_poses]


def set_key_pose_frames(key_poses: Any, frames: Iterable[int]) -> None:
    """Replace the collection with the unique frames, ascending.

    bpy CollectionProperty has no in-place sort, so the POC clears and re-adds;
    this keeps the list deduplicated and ordered after every edit.
    """
    ordered = sorted({int(frame) for frame in frames})
    key_poses.clear()
    for frame in ordered:
        key_poses.add().frame = frame


def keyed_frames(obj: Any) -> list[int]:
    """Every integer frame carrying a rotation_quaternion key on `obj`."""
    frames: list[int] = []
    for fcurve in fcurves_for(obj):
        if not str(getattr(fcurve, "data_path", "")).endswith(_ROTATION_PATH_SUFFIX):
            continue
        for keyframe_point in fcurve.keyframe_points:
            frames.append(round(keyframe_point.co.x))
    return frames


def retain_only(fcurves: Iterable[Any], keep_frames: set[int]) -> int:
    """Delete every key not on a keep frame; smooth the survivors. Returns count.

    Iterates keyframe_points back to front so removals do not shift the indices
    of points still to be visited.
    """
    deleted = 0
    for fcurve in fcurves:
        points = fcurve.keyframe_points
        for index in range(len(points) - 1, -1, -1):
            keyframe_point = points[index]
            if round(keyframe_point.co.x) in keep_frames:
                _smooth(keyframe_point)
                continue
            points.remove(keyframe_point)
            deleted += 1
    return deleted


def build_keyframe_manager_classes(bpy_module: Any) -> tuple[type[Any], ...]:
    """Build the key-pose item, list UI, and manager operators."""

    class POSECAP_PG_KeyPoseItem(bpy_module.types.PropertyGroup):
        __slots__ = ()

    POSECAP_PG_KeyPoseItem.__annotations__ = {
        "frame": bpy_module.props.IntProperty(name="Frame", default=0),
    }

    class POSECAP_UL_KeyPoseList(bpy_module.types.UIList):
        def draw_item(
            self,
            _context: Any,
            layout: Any,
            _data: Any,
            item: Any,
            _icon: Any,
            _active_data: Any,
            _active_propname: Any,
            _index: int = 0,
        ) -> None:
            layout.label(text=f"Frame {item.frame}", icon="KEYFRAME_HLT")

    class POSECAP_OT_AddKeyPose(bpy_module.types.Operator):
        bl_idname = "posecap.add_key_pose"
        bl_label = "Add Key Pose"
        bl_description = "Mark the current frame as a key pose to keep"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any) -> set[str]:
            return _add_current_frame(context)

    class POSECAP_OT_RemoveKeyPose(bpy_module.types.Operator):
        bl_idname = "posecap.remove_key_pose"
        bl_label = "Remove Key Pose"
        bl_description = "Remove the selected key pose"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any) -> set[str]:
            return _remove_selected(context)

    class POSECAP_OT_ClearKeyPoses(bpy_module.types.Operator):
        bl_idname = "posecap.clear_key_poses"
        bl_label = "Clear All Key Poses"
        bl_description = "Clear every marked key pose"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any) -> set[str]:
            context.scene.posecap_key_poses.clear()
            return {"FINISHED"}

    class POSECAP_OT_AddAllActiveKeyframes(bpy_module.types.Operator):
        bl_idname = "posecap.add_all_active_keyframes"
        bl_label = "Add All Active Keyframes"
        bl_description = "Mark every existing keyframe of the target armature as a key pose"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any) -> set[str]:
            return _add_all_active(self, context)

    class POSECAP_OT_BakeRetainKeyPoses(bpy_module.types.Operator):
        bl_idname = "posecap.bake_and_retain_key_poses"
        bl_label = "Bake & Retain Key Poses"
        bl_description = "Bake the pose range, then delete every keyframe not on a marked key pose"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any) -> set[str]:
            return _bake_and_retain(self, context, bpy_module)

    return (
        POSECAP_PG_KeyPoseItem,
        POSECAP_UL_KeyPoseList,
        POSECAP_OT_AddKeyPose,
        POSECAP_OT_RemoveKeyPose,
        POSECAP_OT_ClearKeyPoses,
        POSECAP_OT_AddAllActiveKeyframes,
        POSECAP_OT_BakeRetainKeyPoses,
    )


def draw_keyframe_manager_section(layout: Any, scene: Any) -> None:
    """Draw the key-pose list and cleanup actions."""
    box = layout.box()
    box.label(text="Keyframe Manager", icon="KEYFRAME")
    row = box.row()
    row.template_list(
        "POSECAP_UL_KeyPoseList", "", scene, KEY_POSES_PROPERTY, scene, KEY_POSES_INDEX_PROPERTY
    )
    side = row.column(align=True)
    side.operator("posecap.add_key_pose", icon="ADD", text="")
    side.operator("posecap.remove_key_pose", icon="REMOVE", text="")
    box.operator("posecap.add_all_active_keyframes", icon="FILE_CACHE")
    box.operator("posecap.clear_key_poses", icon="TRASH")
    box.operator("posecap.bake_and_retain_key_poses", icon="CHECKBOX_HLT")
    box.label(text="Bake & Retain deletes intermediate keys", icon="ERROR")


def _add_current_frame(context: Any) -> set[str]:
    key_poses = context.scene.posecap_key_poses
    frame = int(context.scene.frame_current)
    set_key_pose_frames(key_poses, [*key_pose_frames(key_poses), frame])
    return {"FINISHED"}


def _remove_selected(context: Any) -> set[str]:
    scene = context.scene
    key_poses = scene.posecap_key_poses
    index = int(getattr(scene, KEY_POSES_INDEX_PROPERTY, 0))
    if not 0 <= index < len(key_poses):
        return {"CANCELLED"}
    key_poses.remove(index)
    setattr(scene, KEY_POSES_INDEX_PROPERTY, max(0, min(index, len(key_poses) - 1)))
    return {"FINISHED"}


def _add_all_active(operator: Any, context: Any) -> set[str]:
    armature = _target_armature(context)
    if armature is None:
        operator.report({"WARNING"}, "Set the target armature first.")
        return {"CANCELLED"}
    key_poses = context.scene.posecap_key_poses
    set_key_pose_frames(key_poses, [*key_pose_frames(key_poses), *keyed_frames(armature)])
    return {"FINISHED"}


def _bake_and_retain(operator: Any, context: Any, bpy_module: Any) -> set[str]:
    armature = _target_armature(context)
    if armature is None:
        operator.report({"WARNING"}, "Set the target armature first.")
        return {"CANCELLED"}
    frames = set(key_pose_frames(context.scene.posecap_key_poses))
    if not frames:
        operator.report({"WARNING"}, "No key poses marked to retain.")
        return {"CANCELLED"}
    try:
        _visual_bake(context, bpy_module, armature, min(frames), max(frames))
    except Exception as error:  # bpy edge: nla.bake failure must not leak a traceback
        operator.report({"ERROR"}, f"Bake failed: {error}")
        return {"CANCELLED"}
    deleted = retain_only(fcurves_for(armature), frames)
    operator.report({"INFO"}, f"Retained {len(frames)} key poses; deleted {deleted} keys.")
    return {"FINISHED"}


def _visual_bake(context: Any, bpy_module: Any, armature: Any, first: int, last: int) -> None:
    """Visually bake the pose range on `armature`, restoring active/mode after.

    nla.bake needs the armature active and in pose mode with bones selected, so
    this stages that context and puts it back (POC operators/keyframes.py:149-166).
    The restore runs in a finally so a bake failure cannot strand the armature in
    pose mode.
    """
    view_layer = context.view_layer
    previous_active = view_layer.objects.active
    previous_mode = getattr(armature, "mode", "OBJECT")
    view_layer.objects.active = armature
    try:
        bpy_module.ops.object.mode_set(mode="POSE")
        bpy_module.ops.pose.select_all(action="SELECT")
        bpy_module.ops.nla.bake(
            frame_start=first,
            frame_end=last,
            step=1,
            only_selected=True,
            visual_keying=True,
            clear_constraints=True,
            use_current_action=True,
            bake_types={"POSE"},
        )
    finally:
        bpy_module.ops.object.mode_set(mode=previous_mode)
        view_layer.objects.active = previous_active


def _target_armature(context: Any) -> Any | None:
    settings = getattr(context.scene, "posecap", None)
    armature = getattr(settings, "target_armature", None)
    if armature is None:
        return None
    if getattr(armature, "type", None) != "ARMATURE":
        return None
    return armature


def _smooth(keyframe_point: Any) -> None:
    keyframe_point.interpolation = "BEZIER"
    keyframe_point.handle_left_type = "AUTO_CLAMPED"
    keyframe_point.handle_right_type = "AUTO_CLAMPED"
