"""PoseCap Blender extension package."""

from .engine_process import EngineEndpoint, EngineProcess, EngineStartupError, start_engine_stream
from .stream_client import TcpPoseStreamClient

__all__ = [
    "EngineEndpoint",
    "EngineProcess",
    "EngineStartupError",
    "TcpPoseStreamClient",
    "register",
    "start_engine_stream",
    "unregister",
]


def register() -> None:
    """Register Blender classes.

    Task 0004 starts with the pure stream client; bpy classes land with the
    UI/timer slice.
    """


def unregister() -> None:
    """Unregister Blender classes."""
