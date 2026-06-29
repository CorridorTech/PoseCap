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

    build_extension = _load_build_extension_module()
    zip_path = build_extension.build_extension(
        repo_root=Path(__file__).parents[2],
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "stage",
    )
    extension_root = tmp_path / "extension"
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extension_root)

    smoke_script = tmp_path / "posecap_blender_smoke.py"
    smoke_script.write_text(_BLENDER_SMOKE_SCRIPT, encoding="utf-8")

    completed = subprocess.run(
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

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "posecap blender smoke ok" in completed.stdout


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
    import sys
    from pathlib import Path

    extension_root = Path(sys.argv[sys.argv.index("--") + 1])
    sys.path.insert(0, str(extension_root))
    for wheel_path in sorted((extension_root / "wheels").glob("*.whl")):
        sys.path.insert(0, str(wheel_path))

    import bpy
    from posecap_contracts import (
        NUM_BETAS,
        NUM_BODY_JOINTS,
        NUM_EXPRESSION,
        NUM_HAND_JOINTS,
        SCHEMA_VERSION,
        PoseFrame,
        PosePayload,
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

    def payload() -> PosePayload:
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

    posecap_extension.register()
    posecap_extension.unregister()
    posecap_extension.unregister()
    posecap_extension.register()
    try:
        bpy.ops.object.armature_add()
        armature = bpy.context.object
        bpy.ops.object.mode_set(mode="EDIT")
        armature.data.edit_bones[0].name = "pelvis"
        bpy.ops.object.mode_set(mode="OBJECT")

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
    finally:
        posecap_extension.unregister()
        posecap_extension.unregister()

    print("posecap blender smoke ok")
    """
).strip()
