"""Behavior tests for the keyframe manager (key-pose list + cleanup operators).

Live recording lays down a dense key per streamed frame. The manager marks a
sparse set of key poses to keep, then Bake & Retain deletes the intermediate
keys — turning noisy mocap into clean sparse keyframes (POC parity). The
collection math and the retain decision are pure enough to test with fakes; the
`nla.bake` op is HITL-verified in Blender.
"""

from __future__ import annotations

from types import SimpleNamespace

from posecap_addon.keyframe_manager import (
    build_keyframe_manager_classes,
    draw_keyframe_manager_section,
    key_pose_frames,
    keyed_frames,
    retain_only,
    set_key_pose_frames,
)


class _DrawLayout:
    def __init__(self, sink: dict | None = None) -> None:
        self._sink = sink if sink is not None else {"operators": [], "lists": [], "labels": []}

    def box(self) -> _DrawLayout:
        return _DrawLayout(self._sink)

    def row(self, **_kwargs: object) -> _DrawLayout:
        return _DrawLayout(self._sink)

    def column(self, **_kwargs: object) -> _DrawLayout:
        return _DrawLayout(self._sink)

    def label(self, *, text: str, icon: str = "NONE") -> None:
        self._sink["labels"].append(text)

    def operator(self, operator_id: str, **_kwargs: object) -> None:
        self._sink["operators"].append(operator_id)

    def template_list(self, *args: object, **_kwargs: object) -> None:
        self._sink["lists"].append(args)

    @property
    def operators(self) -> list[str]:
        return self._sink["operators"]

    @property
    def lists(self) -> list:
        return self._sink["lists"]


class _FakeOperatorBase:
    def __init__(self) -> None:
        self.reports: list[tuple[set[str], str]] = []

    def report(self, level: set[str], message: str) -> None:
        self.reports.append((level, message))


class _FakeKeyPoses:
    """Mimics a bpy CollectionProperty of items carrying a `frame` int."""

    def __init__(self) -> None:
        self._items: list[SimpleNamespace] = []

    def add(self) -> SimpleNamespace:
        item = SimpleNamespace(frame=0)
        self._items.append(item)
        return item

    def clear(self) -> None:
        self._items.clear()

    def remove(self, index: int) -> None:
        del self._items[index]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __getitem__(self, index: int) -> SimpleNamespace:
        return self._items[index]


class _KeyframePoint:
    def __init__(self, x: float) -> None:
        self.co = SimpleNamespace(x=float(x))
        self.interpolation = "CONSTANT"
        self.handle_left_type = "FREE"
        self.handle_right_type = "FREE"


class _KeyframePoints:
    def __init__(self, xs: list[float]) -> None:
        self._points = [_KeyframePoint(x) for x in xs]

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, index: int) -> _KeyframePoint:
        return self._points[index]

    def __iter__(self):
        return iter(self._points)

    def remove(self, point: _KeyframePoint) -> None:
        self._points.remove(point)


class _FCurve:
    def __init__(self, data_path: str, xs: list[float]) -> None:
        self.data_path = data_path
        self.keyframe_points = _KeyframePoints(xs)


def _armature(fcurves: list[_FCurve]) -> SimpleNamespace:
    return SimpleNamespace(
        type="ARMATURE",
        mode="OBJECT",
        animation_data=SimpleNamespace(action=SimpleNamespace(fcurves=fcurves), action_slot=None),
    )


def _fake_bpy() -> tuple[SimpleNamespace, list[dict]]:
    bake_calls: list[dict] = []

    class _Nla:
        def bake(self, **kwargs: object) -> None:
            bake_calls.append(kwargs)

    ops = SimpleNamespace(
        nla=_Nla(),
        object=SimpleNamespace(mode_set=lambda **_kwargs: None),
        pose=SimpleNamespace(select_all=lambda **_kwargs: None),
    )
    bpy_module = SimpleNamespace(
        types=SimpleNamespace(Operator=_FakeOperatorBase, PropertyGroup=object, UIList=object),
        props=SimpleNamespace(IntProperty=lambda **kwargs: ("IntProperty", kwargs)),
        ops=ops,
    )
    return bpy_module, bake_calls


def _classes(bpy_module: SimpleNamespace) -> dict[str, type]:
    return {cls.__name__: cls for cls in build_keyframe_manager_classes(bpy_module)}


def _context(
    key_poses: _FakeKeyPoses,
    *,
    frame_current: int = 0,
    index: int = 0,
    armature: object | None = "unset",
) -> SimpleNamespace:
    target = _armature([]) if armature == "unset" else armature
    scene = SimpleNamespace(
        posecap_key_poses=key_poses,
        posecap_key_poses_index=index,
        frame_current=frame_current,
        posecap=SimpleNamespace(target_armature=target),
    )
    view_layer = SimpleNamespace(objects=SimpleNamespace(active=None))
    return SimpleNamespace(scene=scene, view_layer=view_layer)


def test_set_key_pose_frames_dedups_and_sorts() -> None:
    key_poses = _FakeKeyPoses()

    set_key_pose_frames(key_poses, [30, 10, 10, 20])

    assert key_pose_frames(key_poses) == [10, 20, 30]


def test_add_key_pose_marks_the_current_frame_without_duplicating() -> None:
    key_poses = _FakeKeyPoses()
    set_key_pose_frames(key_poses, [10])
    bpy_module, _ = _fake_bpy()
    add_cls = _classes(bpy_module)["POSECAP_OT_AddKeyPose"]

    add_cls().execute(_context(key_poses, frame_current=25))
    add_cls().execute(_context(key_poses, frame_current=25))

    assert key_pose_frames(key_poses) == [10, 25]


def test_clear_key_poses_empties_the_list() -> None:
    key_poses = _FakeKeyPoses()
    set_key_pose_frames(key_poses, [1, 2, 3])
    bpy_module, _ = _fake_bpy()

    _classes(bpy_module)["POSECAP_OT_ClearKeyPoses"]().execute(_context(key_poses))

    assert key_pose_frames(key_poses) == []


def test_remove_key_pose_drops_selected_and_clamps_index() -> None:
    key_poses = _FakeKeyPoses()
    set_key_pose_frames(key_poses, [10, 20, 30])
    bpy_module, _ = _fake_bpy()
    context = _context(key_poses, index=2)

    result = _classes(bpy_module)["POSECAP_OT_RemoveKeyPose"]().execute(context)

    assert result == {"FINISHED"}
    assert key_pose_frames(key_poses) == [10, 20]
    assert context.scene.posecap_key_poses_index == 1


def test_add_all_active_marks_every_existing_rotation_key() -> None:
    key_poses = _FakeKeyPoses()
    armature = _armature(
        [
            _FCurve('pose.bones["pelvis"].rotation_quaternion', [5, 10, 15]),
            _FCurve('pose.bones["pelvis"].location', [7]),  # ignored
        ]
    )
    bpy_module, _ = _fake_bpy()
    context = _context(key_poses, armature=armature)

    result = _classes(bpy_module)["POSECAP_OT_AddAllActiveKeyframes"]().execute(context)

    assert result == {"FINISHED"}
    assert key_pose_frames(key_poses) == [5, 10, 15]


def test_add_all_active_warns_and_cancels_without_a_target_armature() -> None:
    key_poses = _FakeKeyPoses()
    bpy_module, _ = _fake_bpy()

    operator = _classes(bpy_module)["POSECAP_OT_AddAllActiveKeyframes"]()
    result = operator.execute(_context(key_poses, armature=None))

    assert result == {"CANCELLED"}
    assert operator.reports and operator.reports[0][0] == {"WARNING"}


def test_bake_and_retain_cancels_when_no_key_poses_marked() -> None:
    key_poses = _FakeKeyPoses()
    bpy_module, bake_calls = _fake_bpy()

    operator = _classes(bpy_module)["POSECAP_OT_BakeRetainKeyPoses"]()
    result = operator.execute(_context(key_poses))

    assert result == {"CANCELLED"}
    assert bake_calls == []
    assert operator.reports and operator.reports[0][0] == {"WARNING"}


def test_bake_and_retain_bakes_the_span_and_deletes_non_key_frames() -> None:
    key_poses = _FakeKeyPoses()
    set_key_pose_frames(key_poses, [10, 30])
    fcurve = _FCurve('pose.bones["pelvis"].rotation_quaternion', [10, 20, 30, 40])
    armature = _armature([fcurve])
    bpy_module, bake_calls = _fake_bpy()

    result = _classes(bpy_module)["POSECAP_OT_BakeRetainKeyPoses"]().execute(
        _context(key_poses, armature=armature)
    )

    assert result == {"FINISHED"}
    assert bake_calls[0]["frame_start"] == 10 and bake_calls[0]["frame_end"] == 30
    assert [round(kp.co.x) for kp in fcurve.keyframe_points] == [10, 30]


def test_bake_and_retain_reports_error_and_restores_state_when_bake_fails() -> None:
    key_poses = _FakeKeyPoses()
    set_key_pose_frames(key_poses, [10, 30])
    fcurve = _FCurve('pose.bones["pelvis"].rotation_quaternion', [10, 20, 30])
    armature = _armature([fcurve])
    bpy_module, _ = _fake_bpy()

    def boom(**_kwargs: object) -> None:
        raise RuntimeError("bake context is incorrect")

    bpy_module.ops.nla.bake = boom
    context = _context(key_poses, armature=armature)
    context.view_layer.objects.active = "previous"

    operator = _classes(bpy_module)["POSECAP_OT_BakeRetainKeyPoses"]()
    result = operator.execute(context)

    assert result == {"CANCELLED"}
    assert operator.reports and operator.reports[-1][0] == {"ERROR"}
    # The finally restores the active object even though the bake raised.
    assert context.view_layer.objects.active == "previous"
    # No keys were deleted — retain never ran after the failed bake.
    assert [round(kp.co.x) for kp in fcurve.keyframe_points] == [10, 20, 30]


def test_retain_only_keeps_marked_frames_and_smooths_them() -> None:
    fcurve = _FCurve("rotation_quaternion", [1, 2, 3, 4])

    deleted = retain_only([fcurve], {2, 4})

    assert deleted == 2
    assert [round(kp.co.x) for kp in fcurve.keyframe_points] == [2, 4]
    for kp in fcurve.keyframe_points:
        assert kp.interpolation == "BEZIER"
        assert kp.handle_left_type == "AUTO_CLAMPED"


def test_keyed_frames_reads_rotation_quaternion_curves_only() -> None:
    armature = _armature(
        [
            _FCurve('pose.bones["a"].rotation_quaternion', [3, 6]),
            _FCurve('pose.bones["a"].location', [9]),
        ]
    )

    assert sorted(keyed_frames(armature)) == [3, 6]


def test_draw_section_lists_key_poses_and_offers_every_manager_action() -> None:
    layout = _DrawLayout()

    draw_keyframe_manager_section(layout, SimpleNamespace())

    assert layout.lists, "the key-pose list is rendered"
    for operator_id in (
        "posecap.add_key_pose",
        "posecap.remove_key_pose",
        "posecap.add_all_active_keyframes",
        "posecap.clear_key_poses",
        "posecap.bake_and_retain_key_poses",
    ):
        assert operator_id in layout.operators
