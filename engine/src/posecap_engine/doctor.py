"""Environment doctor for PEAR-backed engine runtime."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from posecap_contracts import REQUIRED_MODEL_ASSETS

from .config import PEAR_MODELS_REVISION, PEAR_REVISION
from .errors import EngineError
from .pear_adapter import (
    _PEAR_MODEL_FILENAME,
    _PEAR_MODEL_REPO_ID,
    _prepend_sys_path,
    _validate_external_checkout,
)

POSECAP_PEAR_ROOT_ENV = "POSECAP_PEAR_ROOT"

CheckStatus = Literal["ok", "warn", "error"]

_REQUIRED_IMPORTS = (
    ("cv2", "OpenCV camera and crop processing"),
    ("torch", "PyTorch PEAR inference"),
    ("torchvision", "PEAR image tensor transforms"),
    ("ultralytics", "YOLO person detector"),
    ("huggingface_hub", "pinned PEAR weight download"),
    ("lightning", "PEAR seed/runtime helpers"),
    ("timm", "PEAR ViT backbone dependency"),
    ("omegaconf", "PEAR config loading"),
    ("roma", "PEAR rotation utilities"),
    ("einops", "PEAR tensor reshaping"),
    ("colored", "PEAR logging utility"),
    ("rich", "PEAR progress/logging utility"),
    ("trimesh", "PEAR mesh/model geometry helpers"),
    ("plotly", "PEAR debug visualization imports"),
    ("pytorch3d", "PEAR SMPL-X transform and renderer dependency"),
)

_WINDOWS_REQUIRED_IMPORTS = (("tzdata", "Windows timezone data used during PEAR live startup"),)

_PEAR_IMPORTS = (
    ("models.pipeline.ehm_pipeline", "PEAR EHM pipeline"),
    ("utils.general_utils", "PEAR general utils"),
)

_RUNTIME_VERSION_MODULES = ("torch", "torchvision", "pytorch3d")

# Single source of truth for the required licensed files: the shared manifest.
_LICENSED_ASSET_PATHS = tuple(Path(*asset.target_path) for asset in REQUIRED_MODEL_ASSETS)


@dataclass(frozen=True)
class DoctorCheck:
    """One machine-readable runtime readiness check."""

    name: str
    status: CheckStatus
    message: str
    details: dict[str, object]


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def run_doctor(
    *,
    pear_root: Path | None,
    download_weights: bool = False,
    command_runner: CommandRunner | None = None,
) -> dict[str, object]:
    """Return JSON-serializable readiness results for the PEAR runtime."""
    resolved_pear_root = pear_root or _pear_root_from_environment()
    runner = command_runner or _run_command
    checks = [
        _check_python(),
        _check_runtime_versions(),
        _check_nvidia_smi(runner),
        *_check_required_imports(),
        _check_torch_cuda(),
        _check_pear_checkout(resolved_pear_root, runner),
        *_check_pear_imports(resolved_pear_root),
        _check_licensed_assets(resolved_pear_root),
        _check_hf_weights(download_weights),
    ]
    return {
        "ok": all(check.status != "error" for check in checks),
        "pear_root": str(resolved_pear_root) if resolved_pear_root is not None else None,
        "checks": [asdict(check) for check in checks],
    }


def encode_doctor_report(report: dict[str, object]) -> str:
    """Encode a doctor report as canonical JSON for CLI output."""
    return json.dumps(report, sort_keys=True)


def _pear_root_from_environment() -> Path | None:
    raw_value = os.environ.get(POSECAP_PEAR_ROOT_ENV)
    if raw_value is None or raw_value.strip() == "":
        return None
    return Path(raw_value)


def _check_python() -> DoctorCheck:
    version = ".".join(str(part) for part in sys.version_info[:3])
    status: CheckStatus = "ok" if sys.version_info[:2] == (3, 11) else "warn"
    message = "Python runtime is available."
    if status == "warn":
        message = "Python works for tests, but PEAR HITL should be validated on Python 3.11."
    return DoctorCheck("python", status, message, {"version": version})


def _check_runtime_versions() -> DoctorCheck:
    details: dict[str, object] = {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "python_executable": sys.executable,
    }
    missing: list[str] = []
    import_errors: dict[str, str] = {}
    for module_name in _RUNTIME_VERSION_MODULES:
        if importlib.util.find_spec(module_name) is None:
            missing.append(module_name)
            continue
        try:
            module = importlib.import_module(module_name)
        except (ImportError, OSError, RuntimeError) as exc:
            import_errors[module_name] = str(exc)
            continue
        details[module_name] = _module_details(module_name, module)

    if missing or import_errors:
        return DoctorCheck(
            "runtime_versions",
            "error",
            "Runtime package versions could not be fully reported.",
            {**details, "missing": missing, "import_errors": import_errors},
        )
    return DoctorCheck(
        "runtime_versions",
        "ok",
        "Runtime package versions are available.",
        details,
    )


def _module_details(module_name: str, module: object) -> dict[str, object]:
    details: dict[str, object] = {"version": _module_version(module)}
    if module_name == "torch":
        version_module = getattr(module, "version", None)
        details["cuda"] = _optional_string(getattr(version_module, "cuda", None))
    return details


def _module_version(module: object) -> str | None:
    return _optional_string(getattr(module, "__version__", None))


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _check_nvidia_smi(command_runner: CommandRunner) -> DoctorCheck:
    try:
        completed = command_runner(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ]
        )
    except OSError as exc:
        return DoctorCheck(
            "nvidia_smi",
            "error",
            "NVIDIA driver tools were not found; install an NVIDIA driver before PEAR live mode.",
            {"error": str(exc)},
        )
    if completed.returncode != 0:
        return DoctorCheck(
            "nvidia_smi",
            "error",
            "NVIDIA driver tools did not report a usable GPU.",
            {"stderr": completed.stderr.strip()},
        )
    return DoctorCheck(
        "nvidia_smi",
        "ok",
        "NVIDIA driver tools report at least one GPU.",
        {"gpus": _non_empty_lines(completed.stdout)},
    )


def _check_required_imports() -> list[DoctorCheck]:
    imports = _REQUIRED_IMPORTS
    if sys.platform == "win32":
        imports = imports + _WINDOWS_REQUIRED_IMPORTS
    return _check_imports(imports)


def _check_pear_imports(pear_root: Path | None) -> list[DoctorCheck]:
    if pear_root is None:
        return []
    try:
        _validate_external_checkout(pear_root)
    except EngineError:
        return []
    _prepend_sys_path(pear_root)
    return _check_imports(_PEAR_IMPORTS)


def _check_imports(imports: tuple[tuple[str, str], ...]) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    for module_name, purpose in imports:
        try:
            spec = importlib.util.find_spec(module_name)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            checks.append(
                DoctorCheck(
                    f"import:{module_name}",
                    "error",
                    f"{module_name} failed during import discovery; required for {purpose}.",
                    {"module": module_name, "purpose": purpose, "error": str(exc)},
                )
            )
            continue
        if spec is None:
            checks.append(
                DoctorCheck(
                    f"import:{module_name}",
                    "error",
                    f"{module_name} is missing; required for {purpose}.",
                    {"module": module_name, "purpose": purpose},
                )
            )
            continue
        try:
            importlib.import_module(module_name)
        except (ImportError, OSError, RuntimeError) as exc:
            checks.append(
                DoctorCheck(
                    f"import:{module_name}",
                    "error",
                    f"{module_name} failed during import; required for {purpose}.",
                    {"module": module_name, "purpose": purpose, "error": str(exc)},
                )
            )
            continue
        checks.append(
            DoctorCheck(
                f"import:{module_name}",
                "ok",
                f"{module_name} can be imported.",
                {"module": module_name},
            )
        )
    return checks


def _check_torch_cuda() -> DoctorCheck:
    if importlib.util.find_spec("torch") is None:
        return DoctorCheck(
            "torch_cuda",
            "error",
            "PyTorch is not installed, so CUDA availability cannot be checked.",
            {},
        )
    try:
        torch = importlib.import_module("torch")
        cuda_available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if cuda_available else 0
    except (AttributeError, ImportError, OSError, RuntimeError) as exc:
        return DoctorCheck(
            "torch_cuda",
            "error",
            "PyTorch could not report CUDA availability.",
            {"error": str(exc)},
        )
    if not cuda_available:
        return DoctorCheck(
            "torch_cuda",
            "error",
            "PyTorch is installed but CUDA is not available; PEAR has no CPU live path.",
            {"device_count": device_count},
        )
    return DoctorCheck(
        "torch_cuda",
        "ok",
        "PyTorch reports CUDA available.",
        {"device_count": device_count},
    )


def _check_pear_checkout(pear_root: Path | None, command_runner: CommandRunner) -> DoctorCheck:
    if pear_root is None:
        return DoctorCheck(
            "pear_checkout",
            "error",
            f"Set {POSECAP_PEAR_ROOT_ENV} or pass --pear-root to the external PEAR checkout.",
            {
                "expected_revision": PEAR_REVISION,
                "clone": (
                    "git clone https://github.com/Pixel-Talk/PEAR.git <path> && "
                    f"git -C <path> checkout {PEAR_REVISION}"
                ),
            },
        )
    try:
        _validate_external_checkout(pear_root)
    except EngineError as exc:
        return DoctorCheck(
            "pear_checkout",
            "error",
            str(exc),
            {"pear_root": str(pear_root), "expected_revision": PEAR_REVISION},
        )

    revision_check = _git_revision_check(pear_root, command_runner)
    if revision_check is not None:
        return revision_check
    return DoctorCheck(
        "pear_checkout",
        "ok",
        "External PEAR checkout is present at the pinned revision.",
        {"pear_root": str(pear_root), "expected_revision": PEAR_REVISION},
    )


def _git_revision_check(pear_root: Path, command_runner: CommandRunner) -> DoctorCheck | None:
    try:
        completed = command_runner(["git", "-C", str(pear_root), "rev-parse", "HEAD"])
    except OSError as exc:
        return DoctorCheck(
            "pear_checkout",
            "warn",
            "PEAR checkout shape is valid, but git was unavailable to verify the revision.",
            {"pear_root": str(pear_root), "error": str(exc), "expected_revision": PEAR_REVISION},
        )
    if completed.returncode != 0:
        return DoctorCheck(
            "pear_checkout",
            "warn",
            "PEAR checkout shape is valid, but git could not verify the revision.",
            {
                "pear_root": str(pear_root),
                "stderr": completed.stderr.strip(),
                "expected_revision": PEAR_REVISION,
            },
        )
    actual_revision = completed.stdout.strip()
    if actual_revision != PEAR_REVISION:
        return DoctorCheck(
            "pear_checkout",
            "error",
            "PEAR checkout is not at the pinned revision.",
            {
                "pear_root": str(pear_root),
                "actual_revision": actual_revision,
                "expected_revision": PEAR_REVISION,
            },
        )
    return None


def _check_licensed_assets(pear_root: Path | None) -> DoctorCheck:
    if pear_root is None or not pear_root.exists():
        return DoctorCheck(
            "pear_assets",
            "error",
            "PEAR licensed asset paths cannot be checked until the external checkout exists.",
            {"missing": [str(path) for path in _LICENSED_ASSET_PATHS]},
        )
    missing = [path for path in _LICENSED_ASSET_PATHS if not (pear_root / path).exists()]
    if missing:
        return DoctorCheck(
            "pear_assets",
            "error",
            "Licensed SMPL/SMPL-X/FLAME assets are missing; download from official "
            "sources and never commit them.",
            {"pear_root": str(pear_root), "missing": [str(path) for path in missing]},
        )
    return DoctorCheck(
        "pear_assets",
        "ok",
        "Required PEAR asset paths are present in the external checkout.",
        {"pear_root": str(pear_root)},
    )


def _check_hf_weights(download_weights: bool) -> DoctorCheck:
    if importlib.util.find_spec("huggingface_hub") is None:
        return DoctorCheck(
            "hf_weights",
            "error",
            "huggingface_hub is missing, so pinned PEAR weights cannot be checked.",
            {"revision": PEAR_MODELS_REVISION},
        )
    try:
        huggingface_hub = importlib.import_module("huggingface_hub")
        if not download_weights:
            # Probe the cache instead of assuming the worst: the installer already
            # fetches these weights (`doctor --download-weights`), so on an installed
            # machine they are present and the first Start Stream only warms up. The
            # repo/file/revision match pear_adapter's loader, so a cache hit means
            # the runtime will load without a download.
            cached = huggingface_hub.try_to_load_from_cache(
                repo_id=_PEAR_MODEL_REPO_ID,
                filename=_PEAR_MODEL_FILENAME,
                repo_type="model",
                revision=PEAR_MODELS_REVISION,
            )
            if isinstance(cached, str):
                return DoctorCheck(
                    "hf_weights",
                    "ok",
                    "AI model weights are ready (already downloaded).",
                    {"revision": PEAR_MODELS_REVISION, "path": cached},
                )
            return DoctorCheck(
                "hf_weights",
                "warn",
                "AI model weights are not in the cache yet — they download "
                "automatically on the first Start Stream (~2.6 GB, one time).",
                {"revision": PEAR_MODELS_REVISION},
            )
        path = huggingface_hub.hf_hub_download(
            repo_id=_PEAR_MODEL_REPO_ID,
            filename=_PEAR_MODEL_FILENAME,
            repo_type="model",
            revision=PEAR_MODELS_REVISION,
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        return DoctorCheck(
            "hf_weights",
            "error",
            "Pinned PEAR weights could not be verified.",
            {"revision": PEAR_MODELS_REVISION, "error": str(exc)},
        )
    return DoctorCheck(
        "hf_weights",
        "ok",
        "Pinned PEAR weights are available in the Hugging Face cache.",
        {"revision": PEAR_MODELS_REVISION, "path": str(path)},
    )


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, check=False, text=True)


def _non_empty_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]
