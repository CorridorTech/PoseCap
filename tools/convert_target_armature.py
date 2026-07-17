"""Dev/CI CLI for the character converter (the user path is the panel operator).

The conversion engine lives in addon/posecap_addon/character_setup.py so the
Blender extension ships it; this shim loads that module by file path (it works
inside ``blender --background`` from a repo checkout without the extension
installed) and keeps the historical CLI surface.

Run inside Blender:

    blender --background character.blend --python tools/convert_target_armature.py \
        -- --output converted.blend [--mapping mapping.json] [--skip-tpose]
        [--bone-length 10.0] [--probe-tolerance 0.05]

The default mapping targets the Unreal Engine humanoid skeleton. A custom
mapping JSON maps SMPL-X joint names to armature bone names. Validated
2026-07-10 on two Fortnite armatures (M_MED_Rebirth_Soldier, M_MED_Donut).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CHARACTER_SETUP_PATH = _REPO_ROOT / "addon" / "posecap_addon" / "character_setup.py"


def _ensure_workspace_packages_importable() -> None:
    """Front-load the workspace ``core/`` and ``contracts/`` source roots on sys.path.

    character_setup now imports posecap_core; inside ``blender --background``
    from a repo checkout the extension is not installed, so those source roots
    must be importable before the module is loaded. Insert unconditionally at the
    front (not guarded on posecap_core resolving): Blender exposes an installed
    extension's *vendored* posecap_core on sys.path even under --factory-startup,
    and that copy can be a stale build — the dev CLI must run the current
    workspace code, so the workspace roots have to shadow it. Idempotent: a root
    already present is not re-added. Harmless in the test env, where the workspace
    source is what posecap_core already resolves to.
    """
    for package in ("core", "contracts"):
        source_root = str(_REPO_ROOT / package / "src")
        if source_root not in sys.path:
            sys.path.insert(0, source_root)


def _load_character_setup():
    _ensure_workspace_packages_importable()
    spec = importlib.util.spec_from_file_location("posecap_character_setup", _CHARACTER_SETUP_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {_CHARACTER_SETUP_PATH}")
    module = importlib.util.module_from_spec(spec)
    # dataclass creation resolves the defining module through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_character_setup = _load_character_setup()

ConversionError = _character_setup.ConversionError
SMPLX_BODY_JOINTS = _character_setup.SMPLX_BODY_JOINTS
DEFAULT_UE_MAPPING = _character_setup.UE_MAPPING
ARM_TARGETS = _character_setup.ARM_TARGETS
PROBE_RELATIVE_TOLERANCE = _character_setup.PROBE_RELATIVE_TOLERANCE
validate_mapping = _character_setup.validate_mapping
probe_expectations = _character_setup.probe_expectations


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an armature to the PoseCap target convention."
    )
    parser.add_argument("--output", required=True, help="Path for the converted .blend")
    parser.add_argument(
        "--mapping", help="JSON file mapping SMPL-X joint names to armature bone names"
    )
    parser.add_argument(
        "--skip-tpose",
        action="store_true",
        help="Skip the A-pose to T-pose re-rest (armature is already T-pose)",
    )
    parser.add_argument(
        "--bone-length",
        type=float,
        default=10.0,
        help="Reoriented bone length in armature units (visual only)",
    )
    parser.add_argument(
        "--probe-tolerance",
        type=float,
        default=PROBE_RELATIVE_TOLERANCE,
        help="Relative tolerance for the self-verification probes",
    )
    return parser.parse_args(argv)


def _script_args() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return []


def _preset(args: argparse.Namespace):
    preset = _character_setup.ue_preset()
    if args.mapping:
        mapping = dict(preset.mapping)
        mapping.update(json.loads(Path(args.mapping).read_text(encoding="utf-8")))
        preset = _character_setup.SkeletonPreset(
            name="custom",
            label="Custom mapping",
            mapping=mapping,
            arm_chains=preset.arm_chains,
            already_t_pose=preset.already_t_pose,
        )
    missing = validate_mapping(preset.mapping)
    if missing:
        sys.exit(f"mapping is missing SMPL-X joints: {', '.join(missing)}")
    return preset


def main() -> None:  # pragma: no cover - exercised inside Blender only
    import bpy

    args = parse_args(_script_args())
    preset = _preset(args)
    arm_obj = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if arm_obj is None:
        sys.exit("no armature object in this .blend")
    try:
        result = _character_setup.convert_armature(
            bpy,
            arm_obj,
            preset,
            re_rest_t_pose=False if args.skip_tpose else None,
            bone_length=args.bone_length,
            probe_tolerance=args.probe_tolerance,
        )
    except ConversionError as exc:
        sys.exit(str(exc))
    for line in result.probe_lines:
        print(line)

    # keep external texture references valid at the new save location
    bpy.ops.file.make_paths_absolute()
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.output).resolve()))
    print(f"converted armature saved: {args.output}")


if __name__ == "__main__":
    main()
