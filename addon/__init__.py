"""Blender extension entry point for PoseCap."""

from .posecap_addon import TcpPoseStreamClient
from .posecap_addon import register as _register
from .posecap_addon import unregister as _unregister

__all__ = ["TcpPoseStreamClient", "register", "unregister"]


def register() -> None:
    """Register the PoseCap Blender extension."""
    _register()


def unregister() -> None:
    """Unregister the PoseCap Blender extension."""
    _unregister()
