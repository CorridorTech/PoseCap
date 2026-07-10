"""Live source-preview window for the engine.

Grounded on how Blender webcam-mocap tools actually show the feed: a separate
OpenCV window (BlendArMocap uses cv2.imshow; the Corridor POC previewed the
camera engine-side, never inside a Blender panel). bpy.utils.previews is a
thumbnail cache and cannot do live video — this replaces that dead end.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any


class PreviewWindow:
    """Show each captured frame in an OpenCV window; close on teardown."""

    def __init__(self, cv2: Any, *, title: str = "PoseCap source preview") -> None:
        self._cv2 = cv2
        self._title = title
        self._opened = False

    def offer(self, rgb_image: Any) -> None:
        bgr = self._cv2.cvtColor(rgb_image, self._cv2.COLOR_RGB2BGR)
        if not self._opened:
            # Keep it on top so it is visible over a maximized Blender instead
            # of opening behind it.
            with suppress(Exception):
                self._cv2.namedWindow(self._title, self._cv2.WINDOW_NORMAL)
                self._cv2.setWindowProperty(self._title, self._cv2.WND_PROP_TOPMOST, 1.0)
        self._cv2.imshow(self._title, bgr)
        # waitKey pumps the highgui event loop so the window paints and stays
        # responsive; 1 ms keeps it off the capture rate.
        self._cv2.waitKey(1)
        self._opened = True

    def close(self) -> None:
        if not self._opened:
            return
        self._opened = False
        with suppress(Exception):
            self._cv2.destroyWindow(self._title)
        with suppress(Exception):
            self._cv2.waitKey(1)
