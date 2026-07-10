"""Guards for the installer packaging inputs (task 0006).

The installer's determinism rests on these files: the lockfiles must pin the
exact validated runtime matrix (ADR-0007) and the Inno template must keep every
token the renderer replaces. A drifted pin here means a clean machine installs
something the workstation never validated.
"""

import re
from pathlib import Path

_PACKAGING = Path(__file__).parents[1] / "packaging"


def _read(name: str) -> str:
    return (_PACKAGING / name).read_text(encoding="utf-8")


def test_torch_lock_pins_validated_cuda_matrix() -> None:
    lock = _read("requirements-torch.lock")
    assert "torch==2.4.1+cu124" in lock
    assert "torchvision==0.19.1+cu124" in lock


def test_pypi_lock_pins_every_line_exactly() -> None:
    lines = [
        line
        for line in _read("requirements-pypi.lock").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(lines) > 50
    for line in lines:
        assert re.fullmatch(r"[A-Za-z0-9._-]+==[A-Za-z0-9.+!]+", line), line
    assert not any(line.startswith("torch==") or line.startswith("torchvision==") for line in lines)
    assert not any("posecap" in line for line in lines)
    assert not any("pytorch3d" in line for line in lines)


def test_iss_template_tokens_match_renderer() -> None:
    template = _read("installer/posecap.iss.template")
    tokens = set(re.findall(r"@@([A-Z_]+)@@", template))
    renderer = _read("build_installer.ps1")
    rendered_tokens = set(re.findall(r"'@@([A-Z_]+)@@'", renderer))
    assert tokens == rendered_tokens, (
        f"token drift: template={sorted(tokens)} renderer={sorted(rendered_tokens)}"
    )


def test_bootstrap_never_touches_smplx_models() -> None:
    bootstrap = _read("installer/bootstrap_install.ps1")
    assert "smpl-x" not in bootstrap.lower().replace("smpl-x body models", "")
    assert "meshcapade.com" not in bootstrap.lower()
