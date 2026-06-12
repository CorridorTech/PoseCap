"""Ports: the interfaces adapters implement. Defined here, owned by the domain."""

from typing import Protocol

from posecap_contracts import PoseFrame


class PoseStream(Protocol):
    """A live source of pose frames with latest-wins semantics.

    `latest()` returns the newest unconsumed frame, or None when nothing new
    has arrived — it never blocks. Stale frames are dropped by the
    implementation, not the caller.
    """

    def latest(self) -> PoseFrame | None: ...

    def close(self) -> None: ...
