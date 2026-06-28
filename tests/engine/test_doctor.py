import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from posecap_engine import doctor
from posecap_engine.config import PEAR_REVISION
from posecap_engine.doctor import run_doctor


def test_doctor_reports_missing_runtime_pieces_without_traceback(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        doctor.importlib.util,
        "find_spec",
        lambda module_name: SimpleNamespace() if module_name == "cv2" else None,
    )

    report = run_doctor(
        pear_root=tmp_path / "missing-pear",
        command_runner=lambda _command: _completed(stdout="RTX 3080, 610.62, 10240 MiB\n"),
    )

    checks = _checks_by_name(report)
    assert report["ok"] is False
    assert checks["nvidia_smi"]["status"] == "ok"
    assert checks["import:torch"]["status"] == "error"
    assert checks["import:trimesh"]["message"] == (
        "trimesh is missing; required for PEAR mesh/model geometry helpers."
    )
    assert checks["import:plotly"]["message"] == (
        "plotly is missing; required for PEAR debug visualization imports."
    )
    assert checks["torch_cuda"]["message"] == (
        "PyTorch is not installed, so CUDA availability cannot be checked."
    )
    pear_message = checks["pear_checkout"]["message"]
    assert isinstance(pear_message, str)
    assert pear_message.startswith("PEAR checkout not found")
    assert "traceback" not in doctor.encode_doctor_report(report).lower()


def test_doctor_reports_required_import_runtime_failures(monkeypatch, tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _module_name: SimpleNamespace())

    def fake_import_module(module_name: str) -> SimpleNamespace:
        if module_name == "cv2":
            raise OSError("DLL load failed while importing cv2")
        if module_name == "torch":
            return _fake_torch()
        return SimpleNamespace()

    monkeypatch.setattr(doctor.importlib, "import_module", fake_import_module)

    report = run_doctor(
        pear_root=pear_root,
        command_runner=lambda command: _fake_command(command, pear_revision=PEAR_REVISION),
    )

    check = _checks_by_name(report)["import:cv2"]
    assert report["ok"] is False
    assert check["status"] == "error"
    assert check["message"] == (
        "cv2 failed during import; required for OpenCV camera and crop processing."
    )
    details = cast(dict[str, object], check["details"])
    assert details["error"] == "DLL load failed while importing cv2"


def test_doctor_reports_external_pear_import_runtime_failures(monkeypatch, tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _module_name: SimpleNamespace())

    def fake_import_module(module_name: str) -> SimpleNamespace:
        if module_name == "models.pipeline.ehm_pipeline":
            raise RuntimeError("PEAR pipeline import failed")
        if module_name == "torch":
            return _fake_torch()
        return SimpleNamespace()

    monkeypatch.setattr(doctor.importlib, "import_module", fake_import_module)

    report = run_doctor(
        pear_root=pear_root,
        command_runner=lambda command: _fake_command(command, pear_revision=PEAR_REVISION),
    )

    check = _checks_by_name(report)["import:models.pipeline.ehm_pipeline"]
    assert report["ok"] is False
    assert check["status"] == "error"
    assert check["message"] == (
        "models.pipeline.ehm_pipeline failed during import; required for PEAR EHM pipeline."
    )


def test_doctor_reports_torch_cuda_import_runtime_failures(monkeypatch, tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _module_name: SimpleNamespace())

    def fake_import_module(module_name: str) -> SimpleNamespace:
        if module_name == "torch":
            raise OSError("DLL load failed while importing torch")
        return SimpleNamespace()

    monkeypatch.setattr(doctor.importlib, "import_module", fake_import_module)

    report = run_doctor(
        pear_root=pear_root,
        command_runner=lambda command: _fake_command(command, pear_revision=PEAR_REVISION),
    )

    check = _checks_by_name(report)["torch_cuda"]
    assert report["ok"] is False
    assert check["status"] == "error"
    assert check["message"] == "PyTorch could not report CUDA availability."


def test_doctor_reports_import_discovery_failures(monkeypatch, tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)

    def fake_find_spec(module_name: str) -> SimpleNamespace:
        if module_name == "models.pipeline.ehm_pipeline":
            raise RuntimeError("parent package import failed")
        return SimpleNamespace()

    monkeypatch.setattr(doctor.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda module_name: _fake_torch() if module_name == "torch" else SimpleNamespace(),
    )

    report = run_doctor(
        pear_root=pear_root,
        command_runner=lambda command: _fake_command(command, pear_revision=PEAR_REVISION),
    )

    check = _checks_by_name(report)["import:models.pipeline.ehm_pipeline"]
    assert report["ok"] is False
    assert check["status"] == "error"
    assert check["message"] == (
        "models.pipeline.ehm_pipeline failed during import discovery; "
        "required for PEAR EHM pipeline."
    )


def test_doctor_verifies_pinned_pear_revision(monkeypatch, tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _module_name: SimpleNamespace())
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda module_name: _fake_torch() if module_name == "torch" else SimpleNamespace(),
    )

    report = run_doctor(
        pear_root=pear_root,
        command_runner=lambda command: _fake_command(command, pear_revision=PEAR_REVISION),
    )

    checks = _checks_by_name(report)
    assert checks["pear_checkout"]["status"] == "ok"
    assert checks["pear_assets"]["status"] == "error"
    assert checks["hf_weights"]["status"] == "warn"


def test_doctor_reports_wrong_pear_revision(monkeypatch, tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _module_name: SimpleNamespace())
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda module_name: _fake_torch() if module_name == "torch" else SimpleNamespace(),
    )

    report = run_doctor(
        pear_root=pear_root,
        command_runner=lambda command: _fake_command(command, pear_revision="0" * 40),
    )

    check = _checks_by_name(report)["pear_checkout"]
    assert check["status"] == "error"
    details = cast(dict[str, object], check["details"])
    assert details["expected_revision"] == PEAR_REVISION


def test_doctor_reports_exact_runtime_versions(monkeypatch, tmp_path: Path) -> None:
    pear_root = _pear_checkout(tmp_path)
    modules = {
        "torch": _fake_torch(torch_version="2.4.1+cu124", cuda_version="12.4"),
        "torchvision": SimpleNamespace(__version__="0.19.1+cu124"),
        "pytorch3d": SimpleNamespace(__version__="0.7.9"),
    }
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _module_name: SimpleNamespace())
    monkeypatch.setattr(
        doctor.importlib,
        "import_module",
        lambda module_name: modules.get(module_name, SimpleNamespace()),
    )

    report = run_doctor(
        pear_root=pear_root,
        command_runner=lambda command: _fake_command(command, pear_revision=PEAR_REVISION),
    )

    check = _checks_by_name(report)["runtime_versions"]
    assert check["status"] == "ok"
    details = cast(dict[str, object], check["details"])
    assert cast(dict[str, object], details["torch"]) == {
        "version": "2.4.1+cu124",
        "cuda": "12.4",
    }
    assert cast(dict[str, object], details["torchvision"])["version"] == "0.19.1+cu124"
    assert cast(dict[str, object], details["pytorch3d"])["version"] == "0.7.9"


def _pear_checkout(tmp_path: Path) -> Path:
    pear_root = tmp_path / "pear"
    (pear_root / "models").mkdir(parents=True)
    (pear_root / "utils").mkdir()
    (pear_root / "configs").mkdir()
    (pear_root / "configs" / "infer.yaml").write_text("model: infer\n", encoding="utf-8")
    (pear_root / "model_zoo").mkdir()
    (pear_root / "model_zoo" / "yolov8x.pt").write_text("weights", encoding="utf-8")
    return pear_root


def _checks_by_name(report: dict[str, object]) -> dict[str, dict[str, object]]:
    checks = cast(list[dict[str, object]], report["checks"])
    return {str(check["name"]): check for check in checks}


def _completed(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def _fake_command(command: list[str], *, pear_revision: str) -> subprocess.CompletedProcess[str]:
    if command[0] == "nvidia-smi":
        return _completed(stdout="RTX 3080, 610.62, 10240 MiB\n")
    if command[0] == "git":
        return _completed(stdout=f"{pear_revision}\n")
    return _completed(returncode=1, stderr="unexpected command")


def _fake_torch(
    *,
    torch_version: str = "2.4.1",
    cuda_version: str = "12.4",
) -> SimpleNamespace:
    return SimpleNamespace(
        __version__=torch_version,
        version=SimpleNamespace(cuda=cuda_version),
        cuda=SimpleNamespace(is_available=lambda: True, device_count=lambda: 1),
    )
