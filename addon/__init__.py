"""Blender extension entry point for PoseCap."""

from .posecap_addon import (
    BpyArmaturePoseWriter,
    EngineEndpoint,
    EngineProcess,
    EngineStartupError,
    PoseApplyTimer,
    TcpPoseStreamClient,
    start_engine_stream,
    tag_view3d_redraw,
)
from .posecap_addon import (
    register as _register,
)
from .posecap_addon import (
    unregister as _unregister,
)

__all__ = [
    "BpyArmaturePoseWriter",
    "EngineEndpoint",
    "EngineProcess",
    "EngineStartupError",
    "PoseApplyTimer",
    "TcpPoseStreamClient",
    "register",
    "start_engine_stream",
    "tag_view3d_redraw",
    "unregister",
]


def register() -> None:
    """Register the PoseCap Blender extension."""
    _register()


def unregister() -> None:
    """Unregister the PoseCap Blender extension."""
    _unregister()
