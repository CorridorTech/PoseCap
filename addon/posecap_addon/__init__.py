"""PoseCap Blender extension package."""

from . import panels
from .apply_timer import BpyArmaturePoseWriter, PoseApplyTimer, tag_view3d_redraw
from .engine_process import EngineEndpoint, EngineProcess, EngineStartupError, start_engine_stream
from .panels import SCENE_PROPERTY_NAME, draw_live_stream_panel
from .stream_client import TcpPoseStreamClient

__all__ = [
    "BpyArmaturePoseWriter",
    "EngineEndpoint",
    "EngineProcess",
    "EngineStartupError",
    "PoseApplyTimer",
    "SCENE_PROPERTY_NAME",
    "TcpPoseStreamClient",
    "draw_live_stream_panel",
    "register",
    "start_engine_stream",
    "tag_view3d_redraw",
    "unregister",
]


def register() -> None:
    """Register Blender classes."""
    panels.register()


def unregister() -> None:
    """Unregister Blender classes."""
    panels.unregister()
