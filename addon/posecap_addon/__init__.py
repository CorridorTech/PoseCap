"""PoseCap Blender extension package."""

from .stream_client import TcpPoseStreamClient

__all__ = ["TcpPoseStreamClient", "register", "unregister"]


def register() -> None:
    """Register Blender classes.

    Task 0004 starts with the pure stream client; bpy classes land with the
    UI/timer slice.
    """


def unregister() -> None:
    """Unregister Blender classes."""
