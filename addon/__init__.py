"""Blender extension entry point for PoseCap."""

from .posecap_addon import (
    EngineEndpoint,
    EngineProcess,
    EngineStartupError,
    TcpPoseStreamClient,
    start_engine_stream,
)
from .posecap_addon import (
    register as _register,
)
from .posecap_addon import (
    unregister as _unregister,
)

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
    """Register the PoseCap Blender extension."""
    _register()


def unregister() -> None:
    """Unregister the PoseCap Blender extension."""
    _unregister()
