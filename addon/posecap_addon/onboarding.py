"""First-run Getting Started onboarding: a step model + a draw adapter.

The checklist is the panel's first-run face — it renders unconditionally so a
non-technical user is always guided and the guidance never silently disappears
by a state-resolution edge (the failure mode of the old conditional section).
Each step reports done/not-done and, while incomplete, a call-to-action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The wizard operator is built in the next slice; the checklist references it now
# so the models CTA is wired the moment the operator lands.
_MODELS_WIZARD_OPERATOR = "posecap.setup_body_models_wizard"


@dataclass(frozen=True)
class OnboardingStep:
    """One Getting Started row: a labelled state with an optional call-to-action."""

    key: str
    label: str
    done: bool
    action_operator: str | None = None
    action_label: str | None = None


def onboarding_steps(*, models_ready: bool, character_ready: bool) -> tuple[OnboardingStep, ...]:
    """The three first-run steps, in order, with their done state and CTA."""
    return (
        OnboardingStep(
            key="models",
            label="Install the body models",
            done=models_ready,
            action_operator=None if models_ready else _MODELS_WIZARD_OPERATOR,
            action_label=None if models_ready else "Set Up",
        ),
        OnboardingStep(
            key="character",
            label="Choose a target character",
            done=character_ready,
        ),
        OnboardingStep(
            key="ready",
            label="Ready to capture",
            done=models_ready and character_ready,
        ),
    )


def onboarding_complete(steps: tuple[OnboardingStep, ...]) -> bool:
    """True when every step is done — the checklist collapses at that point."""
    return all(step.done for step in steps)


def draw_getting_started(layout: Any, steps: tuple[OnboardingStep, ...]) -> None:
    """Draw the checklist box: one row per step, ticked or with its CTA."""
    box = layout.box()
    box.label(text="Getting Started with PoseCap", icon="INFO")
    for step in steps:
        row = box.row()
        row.label(text=step.label, icon="CHECKMARK" if step.done else "DOT")
        if not step.done and step.action_operator is not None:
            row.operator(step.action_operator, text=step.action_label or "")
