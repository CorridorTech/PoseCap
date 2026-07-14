import importlib.util
import os
import shutil
import subprocess
import textwrap
import zipfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def test_blender_background_register_unregister_and_simulated_frame_apply(
    tmp_path: Path,
) -> None:
    blender = _blender_executable()
    if blender is None:
        pytest.skip("set POSECAP_BLENDER or put blender on PATH to run e2e smoke")

    completed = _run_blender_script(
        blender,
        tmp_path,
        script_source=_BLENDER_SMOKE_SCRIPT,
        script_name="posecap_blender_smoke.py",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "posecap blender conversion smoke ok" in completed.stdout


def test_blender_panel_survives_out_of_order_and_repeated_user_workflows(
    tmp_path: Path,
) -> None:
    blender = _blender_executable()
    if blender is None:
        pytest.skip("set POSECAP_BLENDER or put blender on PATH to run e2e smoke")

    completed = _run_blender_script(
        blender,
        tmp_path,
        script_source=_BLENDER_PANEL_STRESS_SCRIPT,
        script_name="posecap_blender_panel_stress.py",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "posecap panel workflow stress ok" in completed.stdout
    if os.environ.get("POSECAP_E2E_FBX"):
        assert "posecap real fbx workflow ok" in completed.stdout


def _run_blender_script(
    blender: Path,
    tmp_path: Path,
    *,
    script_source: str,
    script_name: str,
) -> subprocess.CompletedProcess[str]:
    build_extension = _load_build_extension_module()
    zip_path = build_extension.build_extension(
        repo_root=Path(__file__).parents[2],
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "stage",
    )
    extension_root = tmp_path / "extension"
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extension_root)

    smoke_script = tmp_path / script_name
    smoke_script.write_text(script_source, encoding="utf-8")

    return subprocess.run(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--python",
            str(smoke_script),
            "--",
            str(extension_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _blender_executable() -> Path | None:
    configured = os.environ.get("POSECAP_BLENDER")
    if configured:
        return Path(configured)
    discovered = shutil.which("blender")
    if discovered is None:
        return None
    return Path(discovered)


def _load_build_extension_module():
    module_path = Path(__file__).parents[2] / "tools" / "build_extension.py"
    spec = importlib.util.spec_from_file_location("build_extension", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BLENDER_SMOKE_SCRIPT = textwrap.dedent(
    """
    from __future__ import annotations

    import importlib.util
    import math
    import os
    import socket
    import sys
    import threading
    import time
    from pathlib import Path
    from types import SimpleNamespace

    extension_root = Path(sys.argv[sys.argv.index("--") + 1])
    sys.path.insert(0, str(extension_root))
    for wheel_path in sorted((extension_root / "wheels").glob("*.whl")):
        sys.path.insert(0, str(wheel_path))

    import bpy
    from mathutils import Vector
    from posecap_contracts import (
        NUM_BETAS,
        NUM_BODY_JOINTS,
        NUM_EXPRESSION,
        NUM_HAND_JOINTS,
        SCHEMA_VERSION,
        PoseFrame,
        PosePayload,
        encode_pose_frame,
    )
    from posecap_core import (
        BODY_JOINT_NAMES,
        LEFT_HAND_JOINT_NAMES,
        RIGHT_HAND_JOINT_NAMES,
        mixamo_preset,
    )

    extension_spec = importlib.util.spec_from_file_location(
        "posecap_extension_smoke",
        extension_root / "__init__.py",
        submodule_search_locations=[str(extension_root)],
    )
    if extension_spec is None or extension_spec.loader is None:
        raise RuntimeError("could not load PoseCap extension entry point")
    posecap_extension = importlib.util.module_from_spec(extension_spec)
    sys.modules[extension_spec.name] = posecap_extension
    extension_spec.loader.exec_module(posecap_extension)

    class SingleFrameStream:
        def __init__(self, frame: PoseFrame) -> None:
            self._frame = frame
            self.closed = False

        def latest(self) -> PoseFrame | None:
            frame = self._frame
            self._frame = None
            return frame

        def close(self) -> None:
            self.closed = True

    class LoopbackEngine:
        def __init__(self, host: str, port: int) -> None:
            self.endpoint = SimpleNamespace(host=host, port=port)
            self.running = True

        def stop(self, *, timeout_seconds: float) -> None:
            del timeout_seconds
            self.running = False

    class RecordingLayout:
        def __init__(self, labels=None, operators=None) -> None:
            self.enabled = True
            self.alert = False
            self.labels = [] if labels is None else labels
            self.operators = [] if operators is None else operators

        def row(self, **_kwargs):
            return RecordingLayout(self.labels, self.operators)

        def column(self, **_kwargs):
            return RecordingLayout(self.labels, self.operators)

        def box(self):
            return RecordingLayout(self.labels, self.operators)

        def label(self, *, text: str, **_kwargs) -> None:
            self.labels.append(text)

        def prop(self, *_args, **_kwargs) -> None:
            return None

        def operator(self, operator_id: str, **_kwargs):
            self.operators.append(operator_id)
            return SimpleNamespace()

        def template_list(self, *_args, **_kwargs) -> None:
            return None

        def separator(self) -> None:
            return None

    class ContextWithRemovedActiveObject:
        def __init__(self, context, removed_active_object) -> None:
            self._context = context
            self.active_object = removed_active_object

        def __getattr__(self, name: str):
            return getattr(self._context, name)

    class ContextWithBrokenScene:
        preferences = None

        @property
        def scene(self):
            raise RuntimeError("synthetic panel failure")

    def payload(
        *,
        left_elbow_angle: float = 0.0,
        left_index_angle: float = 0.0,
        right_thumb_angle: float = 0.0,
    ) -> PosePayload:
        body_pose = [[0.0, 0.0, 0.0] for _ in range(NUM_BODY_JOINTS)]
        body_pose[BODY_JOINT_NAMES.index("left_elbow")] = [0.0, 0.0, left_elbow_angle]
        left_hand_pose = [[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)]
        left_hand_pose[LEFT_HAND_JOINT_NAMES.index("left_index1")] = [
            0.0,
            0.0,
            left_index_angle,
        ]
        right_hand_pose = [[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)]
        right_hand_pose[RIGHT_HAND_JOINT_NAMES.index("right_thumb3")] = [
            right_thumb_angle,
            0.0,
            0.0,
        ]
        return PosePayload(
            global_orient=[0.0, 0.0, 0.0],
            body_pose=body_pose,
            left_hand_pose=left_hand_pose,
            right_hand_pose=right_hand_pose,
            jaw_pose=[0.0, 0.0, 0.0],
            betas=[0.0 for _ in range(NUM_BETAS)],
            expression=[0.0 for _ in range(NUM_EXPRESSION)],
            transl=[0.0, 0.0, 0.0],
        )

    def synthetic_mixamo_armature():
        preset = mixamo_preset("mixamorig:", include_hands=True)
        armature_data = bpy.data.armatures.new("SyntheticMixamo")
        armature = bpy.data.objects.new("SyntheticMixamo", armature_data)
        bpy.context.collection.objects.link(armature)
        bpy.context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        positions = {
            "mixamorig:LeftArm": (0.0, 0.0, 0.0),
            "mixamorig:LeftForeArm": (10.0, 0.0, 0.0),
            "mixamorig:LeftHand": (20.0, 0.0, 0.0),
            "mixamorig:RightArm": (0.0, -2.0, 0.0),
            "mixamorig:RightForeArm": (-10.0, -2.0, 0.0),
            "mixamorig:RightHand": (-20.0, -2.0, 0.0),
        }
        bones = {}
        for index, name in enumerate(sorted(preset.mapping.values())):
            bone = armature_data.edit_bones.new(name)
            bone.head = Vector(positions.get(name, (float(index), 4.0, 0.0)))
            bone.tail = bone.head + Vector((0.0, 0.0, 1.0))
            bones[name] = bone
        for child, parent in (
            ("mixamorig:LeftForeArm", "mixamorig:LeftArm"),
            ("mixamorig:LeftHand", "mixamorig:LeftForeArm"),
            ("mixamorig:RightForeArm", "mixamorig:RightArm"),
            ("mixamorig:RightHand", "mixamorig:RightForeArm"),
        ):
            bones[child].parent = bones[parent]
        for side in ("Left", "Right"):
            for finger in ("Index", "Middle", "Pinky", "Ring", "Thumb"):
                parent = f"mixamorig:{side}Hand"
                for joint in range(1, 4):
                    child = f"mixamorig:{side}Hand{finger}{joint}"
                    bones[child].parent = bones[parent]
                    parent = child
        bpy.ops.object.mode_set(mode="OBJECT")

        mesh_data = bpy.data.meshes.new("SyntheticMixamoMesh")
        mesh_data.from_pydata([(0.0, 0.0, 0.0)], [], [])
        mesh = bpy.data.objects.new("SyntheticMixamoMesh", mesh_data)
        bpy.context.collection.objects.link(mesh)
        modifier = mesh.modifiers.new("Armature", "ARMATURE")
        modifier.object = armature
        return armature

    def fbx_roundtrip(armature):
        bpy.ops.object.select_all(action="DESELECT")
        exported = [armature]
        exported.extend(
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
            and any(
                modifier.type == "ARMATURE" and modifier.object == armature
                for modifier in obj.modifiers
            )
        )
        for obj in exported:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = armature
        fbx_path = Path(bpy.app.tempdir) / "posecap-synthetic-mixamo.fbx"
        assert bpy.ops.export_scene.fbx(
            filepath=str(fbx_path),
            use_selection=True,
            add_leaf_bones=False,
        ) == {"FINISHED"}
        removed_active_object = armature
        bpy.data.objects.remove(armature, do_unlink=True)
        bpy.context.view_layer.update()
        assert bpy.context.scene.posecap.target_armature is None

        stale_layout = RecordingLayout()
        panel_class.draw(
            SimpleNamespace(layout=stale_layout),
            ContextWithRemovedActiveObject(bpy.context, removed_active_object),
        )
        assert any(label.startswith("PoseCap ") for label in stale_layout.labels)

        before = set(bpy.data.objects)
        assert bpy.ops.import_scene.fbx(filepath=str(fbx_path)) == {"FINISHED"}
        imported = [obj for obj in bpy.data.objects if obj not in before]
        imported_armatures = [obj for obj in imported if obj.type == "ARMATURE"]
        assert len(imported_armatures) == 1
        bpy.context.view_layer.update()
        assert bpy.context.scene.posecap.target_armature == imported_armatures[0]

        imported_layout = RecordingLayout()
        panel_class.draw(SimpleNamespace(layout=imported_layout), bpy.context)
        assert any(label.startswith("PoseCap ") for label in imported_layout.labels)
        return imported_armatures[0]

    def assert_panel_failure_is_actionable():
        original_local_app_data = os.environ.get("LOCALAPPDATA")
        try:
            os.environ["LOCALAPPDATA"] = str(Path(bpy.app.tempdir) / "posecap-e2e-localappdata")
            layout = RecordingLayout()
            panel_class.draw(SimpleNamespace(layout=layout), ContextWithBrokenScene())
            assert "PoseCap could not refresh this panel." in layout.labels
            assert "posecap.create_support_bundle" in layout.operators
            assert "posecap.open_logs" in layout.operators
        finally:
            if original_local_app_data is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = original_local_app_data

    original_scene_update_handlers = tuple(bpy.app.handlers.depsgraph_update_post)
    posecap_extension.register()
    posecap_extension.unregister()
    posecap_extension.unregister()
    posecap_extension.register()
    panels = sys.modules["posecap_extension_smoke.posecap_addon.panels"]
    scene_update_handlers = [
        handler
        for handler in bpy.app.handlers.depsgraph_update_post
        if all(handler is not original for original in original_scene_update_handlers)
    ]
    assert len(scene_update_handlers) == 1
    scene_update_handler = scene_update_handlers[0]
    panel_class = next(
        cls
        for cls in reversed(bpy.types.Panel.__subclasses__())
        if cls.__name__ == "POSECAP_PT_LiveStream"
    )
    try:
        assert_panel_failure_is_actionable()
        bpy.ops.object.armature_add()
        armature = bpy.context.object
        bpy.ops.object.mode_set(mode="EDIT")
        armature.data.edit_bones[0].name = "pelvis"
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
        settings = bpy.context.scene.posecap
        assert settings.target_armature == armature

        pose_bone = armature.pose.bones["pelvis"]
        pose_bone.rotation_mode = "XYZ"
        stream = SingleFrameStream(
            PoseFrame(SCHEMA_VERSION, 1, 100.0, "ok", payload())
        )
        timer = posecap_extension.PoseApplyTimer(
            stream,
            posecap_extension.BpyArmaturePoseWriter(armature),
            interval_seconds=0.25,
        )

        assert timer.tick() == 0.25
        assert pose_bone.rotation_mode == "QUATERNION"
        timer.stop()
        assert stream.closed

        bpy.data.objects.remove(armature, do_unlink=True)
        bpy.context.view_layer.update()
        assert settings.target_armature is None

        synthetic = fbx_roundtrip(synthetic_mixamo_armature())
        bpy.context.view_layer.objects.active = synthetic
        settings.target_armature = synthetic
        settings.character_preset = "AUTO"
        assert bpy.ops.posecap.convert_character() == {"FINISHED"}
        assert not bpy.ops.posecap.start_stream.poll()
        converted_elbow = synthetic.pose.bones["left_elbow"]
        converted_index = synthetic.pose.bones["left_index1"]
        converted_thumb = synthetic.pose.bones["right_thumb3"]
        converted_elbow.rotation_mode = "XYZ"
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        host, port = listener.getsockname()
        frame = PoseFrame(
            SCHEMA_VERSION,
            2,
            101.0,
            "ok",
            payload(
                left_elbow_angle=0.5,
                left_index_angle=0.25,
                right_thumb_angle=0.75,
            ),
        )

        def serve_one_frame() -> None:
            with listener:
                connection, _address = listener.accept()
                with connection:
                    connection.sendall((encode_pose_frame(frame) + "\\n").encode("utf-8"))

        threading.Thread(target=serve_one_frame, daemon=True).start()
        panels.start_engine_stream = lambda _command: LoopbackEngine(host, port)
        panels.models_missing = lambda _root: False
        settings.pear_root = "synthetic-pear-root"
        assert bpy.ops.posecap.start_stream.poll()
        assert bpy.ops.posecap.start_stream() == {"FINISHED"}
        session = panels._ACTIVE_SESSION
        assert session is not None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            session.timer_callback()
            if (
                abs(converted_elbow.rotation_quaternion.z - math.sin(0.25)) < 1e-6
                and abs(converted_index.rotation_quaternion.z - math.sin(0.125)) < 1e-6
                and abs(converted_thumb.rotation_quaternion.x - math.sin(0.375)) < 1e-6
            ):
                break
            time.sleep(0.01)
        assert converted_elbow.rotation_mode == "QUATERNION"
        assert abs(converted_elbow.rotation_quaternion.w - math.cos(0.25)) < 1e-6
        assert abs(converted_elbow.rotation_quaternion.z - math.sin(0.25)) < 1e-6
        assert abs(converted_index.rotation_quaternion.w - math.cos(0.125)) < 1e-6
        assert abs(converted_index.rotation_quaternion.z - math.sin(0.125)) < 1e-6
        assert abs(converted_thumb.rotation_quaternion.w - math.cos(0.375)) < 1e-6
        assert abs(converted_thumb.rotation_quaternion.x - math.sin(0.375)) < 1e-6
        assert settings.lifecycle_state == "STREAMING"
        assert bpy.ops.posecap.stop_stream() == {"FINISHED"}
        assert settings.lifecycle_state == "STOPPED"
    finally:
        posecap_extension.unregister()
        posecap_extension.unregister()
        assert scene_update_handler not in bpy.app.handlers.depsgraph_update_post

    print("posecap blender conversion smoke ok")
    """
).strip()


_BLENDER_PANEL_STRESS_SCRIPT = textwrap.dedent(
    """
    from __future__ import annotations

    import importlib.util
    import os
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    extension_root = Path(sys.argv[sys.argv.index("--") + 1])
    sys.path.insert(0, str(extension_root))
    for wheel_path in sorted((extension_root / "wheels").glob("*.whl")):
        sys.path.insert(0, str(wheel_path))

    import bpy

    extension_spec = importlib.util.spec_from_file_location(
        "posecap_extension_stress",
        extension_root / "__init__.py",
        submodule_search_locations=[str(extension_root)],
    )
    if extension_spec is None or extension_spec.loader is None:
        raise RuntimeError("could not load PoseCap extension entry point")
    posecap_extension = importlib.util.module_from_spec(extension_spec)
    sys.modules[extension_spec.name] = posecap_extension
    extension_spec.loader.exec_module(posecap_extension)

    class RecordingLayout:
        def __init__(self, labels=None, operators=None) -> None:
            self.enabled = True
            self.alert = False
            self.labels = [] if labels is None else labels
            self.operators = [] if operators is None else operators

        def row(self, **_kwargs):
            return RecordingLayout(self.labels, self.operators)

        def column(self, **_kwargs):
            return RecordingLayout(self.labels, self.operators)

        def box(self):
            return RecordingLayout(self.labels, self.operators)

        def label(self, *, text: str, **_kwargs) -> None:
            self.labels.append(text)

        def prop(self, *_args, **_kwargs) -> None:
            return None

        def operator(self, operator_id: str, **_kwargs):
            self.operators.append(operator_id)
            return SimpleNamespace()

        def template_list(self, *_args, **_kwargs) -> None:
            return None

        def separator(self) -> None:
            return None

    def panel_class():
        return next(
            cls
            for cls in reversed(bpy.types.Panel.__subclasses__())
            if cls.__name__ == "POSECAP_PT_LiveStream"
            and cls.__module__.startswith("posecap_extension_stress")
        )

    def draw_panel(stage: str) -> None:
        layout = RecordingLayout()
        panel_class().draw(SimpleNamespace(layout=layout), bpy.context)
        assert any(label.startswith("PoseCap ") for label in layout.labels), stage
        assert "PoseCap could not refresh this panel." not in layout.labels, stage
        assert {"posecap.start_stream", "posecap.stop_stream"}.issubset(
            layout.operators
        ), stage
        assert "Character Setup" in layout.labels, stage
        if "Character ready for capture" not in layout.labels:
            assert "posecap.convert_character" in layout.operators, stage

    def create_armature(name: str):
        bpy.ops.object.select_all(action="DESELECT")
        armature_data = bpy.data.armatures.new(name)
        armature = bpy.data.objects.new(name, armature_data)
        bpy.context.collection.objects.link(armature)
        bpy.context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bone = armature_data.edit_bones.new("pelvis")
        bone.head = (0.0, 0.0, 0.0)
        bone.tail = (0.0, 0.0, 1.0)
        bpy.ops.object.mode_set(mode="OBJECT")
        return armature

    def delete_armatures() -> None:
        for obj in tuple(bpy.context.scene.objects):
            if obj.type == "ARMATURE":
                bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.view_layer.update()

    def import_armature(fbx_path: Path):
        before = set(bpy.data.objects)
        assert bpy.ops.import_scene.fbx(filepath=str(fbx_path)) == {"FINISHED"}
        bpy.context.view_layer.update()
        imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == "ARMATURE"]
        assert len(imported) == 1
        return imported[0]

    def posecap_handlers():
        return [
            handler
            for handler in bpy.app.handlers.depsgraph_update_post
            if getattr(handler, "__module__", "").startswith("posecap_extension_stress")
        ]

    seed = create_armature("PoseCapStressSeed")
    fbx_path = extension_root.parent / "posecap-panel-stress.fbx"
    assert bpy.ops.export_scene.fbx(
        filepath=str(fbx_path),
        use_selection=True,
        add_leaf_bones=False,
    ) == {"FINISHED"}
    bpy.data.objects.remove(seed, do_unlink=True)
    bpy.context.view_layer.update()

    posecap_extension.register()
    try:
        assert len(posecap_handlers()) == 1

        draw_panel("empty scene before import")
        assert not bpy.ops.posecap.start_stream.poll()
        try:
            bpy.ops.posecap.convert_character()
        except RuntimeError as exc:
            assert "Pick a target armature first" in str(exc)
        else:
            raise AssertionError("out-of-order conversion should be rejected")

        imported_before_draw = import_armature(fbx_path)
        assert bpy.context.scene.posecap.target_armature == imported_before_draw
        assert not bpy.ops.posecap.start_stream.poll()
        draw_panel("import before opening panel")

        delete_armatures()
        assert bpy.context.scene.posecap.target_armature is None
        draw_panel("delete imported target")

        draw_panel("open panel before import")
        imported_after_draw = import_armature(fbx_path)
        assert bpy.context.scene.posecap.target_armature == imported_after_draw
        draw_panel("import after opening panel")

        second_armature = import_armature(fbx_path)
        bpy.context.scene.posecap.target_armature = imported_after_draw
        bpy.context.view_layer.objects.active = second_armature
        bpy.context.view_layer.update()
        assert bpy.context.scene.posecap.target_armature == imported_after_draw
        draw_panel("manual choice survives another import")

        delete_armatures()
        for cycle in range(30):
            armature = create_armature(f"PoseCapStress{cycle:02d}")
            bpy.context.view_layer.update()
            assert bpy.context.scene.posecap.target_armature == armature, cycle
            draw_panel(f"stress import cycle {cycle}")
            bpy.data.objects.remove(armature, do_unlink=True)
            bpy.context.view_layer.update()
            assert bpy.context.scene.posecap.target_armature is None, cycle
            draw_panel(f"stress delete cycle {cycle}")

        assert len(posecap_handlers()) == 1
        bpy.ops.wm.read_factory_settings(use_empty=True)
        assert len(posecap_handlers()) == 1
        imported_after_file_load = import_armature(fbx_path)
        assert bpy.context.scene.posecap.target_armature == imported_after_file_load
        draw_panel("new file then import")
        delete_armatures()

        real_fbx_value = os.environ.get("POSECAP_E2E_FBX", "").strip()
        if real_fbx_value:
            real_fbx = Path(real_fbx_value)
            assert real_fbx.is_file()
            imported_real = import_armature(real_fbx)
            assert bpy.context.scene.posecap.target_armature == imported_real
            draw_panel("real FBX import")
            assert bpy.ops.posecap.convert_character() == {"FINISHED"}
            draw_panel("real FBX conversion")
            delete_armatures()
            print("posecap real fbx workflow ok")

        for cycle in range(5):
            posecap_extension.unregister()
            posecap_extension.unregister()
            assert posecap_handlers() == [], cycle
            posecap_extension.register()
            assert len(posecap_handlers()) == 1, cycle
            draw_panel(f"addon reload cycle {cycle}")
    finally:
        posecap_extension.unregister()
        posecap_extension.unregister()

    assert posecap_handlers() == []
    print("posecap panel workflow stress ok")
    """
).strip()
