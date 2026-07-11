"""Behavior tests for panel text wrapping.

The N-panel is narrow; a long status or error message must wrap so a
non-technical user reads the whole thing instead of a middle-truncated
"The downloaded …m the official site."
"""

from __future__ import annotations

from types import SimpleNamespace

from posecap_addon.panel_text import (
    DEFAULT_WRAP_CHARS,
    draw_wrapped_label,
    region_wrap_chars,
    wrap_lines,
)


class _FakeLayout:
    def __init__(self) -> None:
        self.labels: list[tuple[str, str]] = []

    def label(self, *, text: str, icon: str = "NONE") -> None:
        self.labels.append((text, icon))


def test_wrap_lines_keeps_every_word_within_the_width() -> None:
    text = "The downloaded archive does not contain SMPL_NEUTRAL.pkl. Please retry."

    lines = wrap_lines(text, 24)

    assert len(lines) > 1, "a long message must span multiple lines"
    assert all(len(line) <= 24 for line in lines)
    assert " ".join(lines) == " ".join(text.split()), "no word is dropped or altered"


def test_wrap_lines_never_returns_empty() -> None:
    assert wrap_lines("", 20) == [""]


def test_draw_wrapped_label_emits_the_full_message_across_labels() -> None:
    layout = _FakeLayout()
    message = "The downloaded archive does not contain SMPL_NEUTRAL.pkl. Please retry."

    draw_wrapped_label(layout, message, chars=24, icon="ERROR")

    drawn = " ".join(text for text, _icon in layout.labels)
    assert drawn == " ".join(message.split()), "the whole message is readable"
    assert len(layout.labels) > 1
    assert layout.labels[0][1] == "ERROR", "the icon rides the first line"
    assert layout.labels[1][1] == "BLANK1", "continuation lines stay aligned"


def test_region_wrap_chars_falls_back_without_a_region() -> None:
    assert region_wrap_chars(None, 1.0) == DEFAULT_WRAP_CHARS
    assert region_wrap_chars(SimpleNamespace(width=0), 1.0) == DEFAULT_WRAP_CHARS


def test_region_wrap_chars_scales_with_width() -> None:
    narrow = region_wrap_chars(SimpleNamespace(width=260), 1.0)
    wide = region_wrap_chars(SimpleNamespace(width=520), 1.0)

    assert wide > narrow, "a wider panel fits more characters per line"
    assert narrow >= 14
