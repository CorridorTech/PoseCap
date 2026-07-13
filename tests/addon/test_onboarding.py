"""Behavior tests for the first-run Getting Started onboarding.

The onboarding must GUIDE a non-technical user and never silently disappear: the
checklist renders unconditionally from a pure step model (models -> character ->
ready), each step carrying a done state and, when incomplete, a call to action.
The draw is a thin bpy adapter tested with a fake layout.
"""

from __future__ import annotations

from posecap_addon.onboarding import (
    draw_getting_started,
    onboarding_complete,
    onboarding_steps,
)


class _DrawLayout:
    def __init__(self) -> None:
        self.labels: list[tuple[str, str]] = []
        self.operators: list[str] = []

    def box(self) -> _DrawLayout:
        return self

    def row(self, **_kwargs: object) -> _DrawLayout:
        return self

    def label(self, *, text: str, icon: str = "NONE") -> None:
        self.labels.append((text, icon))

    def operator(self, operator_id: str, *, text: str = "", **_kwargs: object) -> None:
        self.operators.append(operator_id)


def test_onboarding_steps_are_models_then_character_then_ready() -> None:
    steps = onboarding_steps(models_ready=False, character_ready=False)

    assert [step.key for step in steps] == ["models", "character", "ready"]
    assert [step.done for step in steps] == [False, False, False]


def test_ready_step_is_done_only_when_models_and_character_are_ready() -> None:
    assert not onboarding_steps(models_ready=True, character_ready=False)[-1].done
    assert not onboarding_steps(models_ready=False, character_ready=True)[-1].done
    assert onboarding_steps(models_ready=True, character_ready=True)[-1].done


def test_onboarding_complete_only_when_every_step_done() -> None:
    assert not onboarding_complete(onboarding_steps(models_ready=True, character_ready=False))
    assert onboarding_complete(onboarding_steps(models_ready=True, character_ready=True))


def test_draw_getting_started_offers_a_cta_for_the_incomplete_models_step() -> None:
    layout = _DrawLayout()

    draw_getting_started(layout, onboarding_steps(models_ready=False, character_ready=False))

    assert "posecap.setup_body_models_wizard" in layout.operators
    assert any("body models" in text.lower() for text, _icon in layout.labels)


def test_draw_getting_started_shows_all_three_setup_steps() -> None:
    layout = _DrawLayout()

    draw_getting_started(layout, onboarding_steps(models_ready=False, character_ready=False))

    labels = [text for text, _icon in layout.labels]
    assert any(text.startswith("1. Body models") for text in labels)
    assert any(text.startswith("2. Target character") for text in labels)
    assert any(text.startswith("3. Ready to capture") for text in labels)


def test_draw_getting_started_has_no_cta_when_every_step_is_done() -> None:
    layout = _DrawLayout()

    draw_getting_started(layout, onboarding_steps(models_ready=True, character_ready=True))

    assert layout.operators == []
