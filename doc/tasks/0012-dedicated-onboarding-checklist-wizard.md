# Task 0012: Dedicated first-run onboarding — Getting Started checklist + model wizard

**Status:** in-progress
**Created:** 2026-07-11
**Owner:** alexandremendoncaalvaro
**Execution:** agent (TDD) + HITL (clean-machine)
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md

## Context

Field feedback (Dean/Emmet, task 0010) and a fresh clean-install walkthrough
(2026-07-11) both show the same failure: a non-technical user opens PoseCap and
does not know what to do. The current onboarding is a **conditional panel section**
(`draw_body_models_section`, shown only when `models_missing`) that:

- the user must first discover (3D View → N → PoseCap tab), and
- silently disappears when a state check is off — e.g. on a clean install the
  panel's `models_missing` check resolved PEAR Root with a weaker fallback than
  the engine, so the setup guidance never appeared (fixed 2026-07-11 by
  `_panel_pear_root`, but the fragility of "appears/hides by state" remains).

Ale's directive: the onboarding must **guide** — dedicated, intuitive, never
silently absent. Decision (2026-07-11): **always-visible Getting Started checklist
at the top of the panel + a dedicated modal wizard for the model step.**

Grounded (`/ad-ground`, 2026-07-11): Blender-idiomatic dedicated wizard =
`WindowManager.invoke_props_dialog(self, width=...)` + `Operator.draw()` (one step
per screen). Add-on guidelines: setup guidance must be obvious, not hunted. The
credential-download mechanism already exists and works (task 0010,
`model_setup.py`) — this task is the guiding EXPERIENCE around it, not new
download plumbing.

## Acceptance Criteria

- [ ] The PoseCap panel shows a **Getting Started** checklist at the top whenever
      onboarding is incomplete: ① Body models installed ② Target character ready
      ③ Ready to capture — each with a ✓/✗ state and, when incomplete, a clear CTA.
      It renders unconditionally (never hidden by a single state-resolution edge).
- [ ] When every step is complete the checklist collapses and the normal stream
      controls are the panel's face.
- [ ] The ① CTA opens a **dedicated modal wizard** (`invoke_props_dialog`) that
      guides license → create account → enter credentials → download → done, one
      step per screen, reusing the existing `model_setup` install pipeline.
- [ ] Models-installed detection uses the same PEAR Root resolution as the engine
      (installer default fallback) — verified on a real clean install.
- [ ] HITL clean-machine: a first-run user reaches a working stream guided only by
      the on-screen checklist + wizard, without reading external docs (closes the
      open task 0010 AC).

## Plan

- [ ] `onboarding.py` — pure step model (`onboarding_steps`, `onboarding_complete`)
      + `draw_getting_started` section. TDD.
- [ ] Wire the checklist at the top of `_draw_main_panel`; collapse when complete.
- [ ] Modal wizard operator (`invoke_props_dialog` + `draw`) over the existing
      `model_setup` pipeline; step state on WindowManager. TDD the step logic.
- [ ] HITL clean-machine capture (with the win.6+ build) end to end.
- [ ] Full gate + /ad-commit + /ad-review.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-11 — Created

Grounded design + decision above. Supersedes the "conditional section" onboarding
of task 0010 as the primary first-run surface (0010's download pipeline is reused,
not replaced). Reference: `/ad-ground` output this session; `invoke_props_dialog`
pattern (interplanety), Blender add-on guidelines.

## Definition of Done

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
