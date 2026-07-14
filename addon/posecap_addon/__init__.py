"""PoseCap Blender extension package."""

from . import panels
from .apply_timer import BpyArmaturePoseWriter, PoseApplyTimer, tag_view3d_redraw
from .backend_registry import (
    BackendRegistryIssue,
    BackendSelectionError,
    PoseBackendCatalog,
    ReadyPoseBackend,
    discover_installed_pose_backends,
    discover_pose_backends,
    resolve_installed_pose_backend,
)
from .engine_process import EngineEndpoint, EngineProcess, EngineStartupError, start_engine_stream
from .panels import SCENE_PROPERTY_NAME, draw_live_stream_panel
from .stream_client import TcpPoseStreamClient

__all__ = [
    "BpyArmaturePoseWriter",
    "BackendRegistryIssue",
    "BackendSelectionError",
    "EngineEndpoint",
    "EngineProcess",
    "EngineStartupError",
    "PoseApplyTimer",
    "PoseBackendCatalog",
    "ReadyPoseBackend",
    "SCENE_PROPERTY_NAME",
    "TcpPoseStreamClient",
    "draw_live_stream_panel",
    "discover_installed_pose_backends",
    "discover_pose_backends",
    "register",
    "resolve_installed_pose_backend",
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
