"""Detect an NVIDIA driver on Linux.

Windows detects NVIDIA presence for its installer wizard by checking for
nvapi64.dll (packaging/installer/posecap.iss.template's NvidiaDriverPresent);
that file has no Linux equivalent. `nvidia-smi` -- which install_pear.ps1
already uses as its own runtime health check, not just a presence probe -- is
the portable Linux signal, so this module doubles as both the wizard-less
default-component-selection check and the install-time driver check.
"""

from __future__ import annotations

import shutil
import subprocess


def nvidia_driver_present() -> bool:
    """Return whether a healthy NVIDIA driver is detectable via nvidia-smi."""
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return False
    try:
        result = subprocess.run([nvidia_smi], capture_output=True, check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
