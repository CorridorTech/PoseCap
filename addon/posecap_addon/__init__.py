"""PoseCap Blender extension package."""

from .apply_timer import BpyArmaturePoseWriter, PoseApplyTimer, tag_view3d_redraw
from .engine_process import EngineEndpoint, EngineProcess, EngineStartupError, start_engine_stream
from .stream_client import TcpPoseStreamClient

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
    """Register Blender classes.

    Task 0004 starts with the pure stream client; bpy classes land with the
    UI/timer slice.
    """


def unregister() -> None:
    """Unregister Blender classes."""
