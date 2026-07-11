"""Panel text helpers.

Blender's ``layout.label`` does not wrap: a message longer than the N-panel is
wide is middle-truncated to "The downloaded …m the official site.", which hides
the very words a non-technical user needs (the fix in an error, the file that is
missing). These helpers wrap a message across as many labels as it takes so the
whole thing is always readable, at whatever width the panel happens to be.
"""

from __future__ import annotations

import textwrap
from typing import Any

# Used when the draw has no region to measure (headless runs, unit tests). Sized
# for the default N-panel: narrow enough never to truncate there.
DEFAULT_WRAP_CHARS = 30

# Conservative pixels-per-character for Blender's UI font: erring high wraps a
# line early (harmless) instead of a character short (truncates).
_PIXELS_PER_CHAR = 8.5
_ROW_PADDING_PIXELS = 28.0
_MIN_WRAP_CHARS = 14


def region_wrap_chars(region: Any, ui_scale: float) -> int:
    """Estimate how many characters fit on one panel line at this region width.

    Falls back to ``DEFAULT_WRAP_CHARS`` when the region width or UI scale is
    unavailable, so the caller never has to special-case a missing region.
    """
    width = float(getattr(region, "width", 0) or 0)
    if width <= 0.0 or ui_scale <= 0.0:
        return DEFAULT_WRAP_CHARS
    usable = width - _ROW_PADDING_PIXELS
    return max(_MIN_WRAP_CHARS, int(usable / (_PIXELS_PER_CHAR * ui_scale)))


def draw_wrapped_label(
    layout: Any,
    text: str,
    *,
    chars: int = DEFAULT_WRAP_CHARS,
    icon: str = "NONE",
) -> None:
    """Draw ``text`` across as many labels as needed so nothing truncates.

    The icon rides the first line; continuation lines sit under the text with a
    blank icon so the block stays visually aligned. Emits plain labels (no
    column) to stay compatible with every panel layout.
    """
    first_icon = icon
    for line in wrap_lines(text, chars):
        layout.label(text=line, icon=first_icon)
        first_icon = "BLANK1"


def wrap_lines(text: str, chars: int) -> list[str]:
    """Word-wrap ``text`` to lines of at most ``chars`` characters.

    Preserves explicit newlines and never returns an empty list, so a status
    message always draws at least one (possibly empty) label.
    """
    width = max(1, chars)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=width) or [""])
    return lines or [""]
