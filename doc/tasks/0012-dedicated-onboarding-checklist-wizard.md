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

- [x] The PoseCap panel shows a **Getting Started** checklist at the top whenever
      onboarding is incomplete: ① Body models installed ② Target character ready
      ③ Ready to capture — each with a ✓/✗ state and, when incomplete, a clear CTA.
      It renders unconditionally (never hidden by a single state-resolution edge).
- [x] When every step is complete the checklist collapses and the normal stream
      controls are the panel's face.
- [x] The ① CTA opens a **dedicated guided dialog** (`invoke_props_dialog`) that
      lays out the whole one-time setup on one screen — orient → create accounts
      (browser links) → enter credentials → OK downloads — reusing the existing
      `model_setup` install pipeline. (Single screen over a multi-step modal:
      grounded decision 2026-07-11, see Notes — matches the praised BlenderKit
      pattern, NN/g wizard guidance for short tasks, and the Blender API idiom.)
- [x] Models-installed detection uses the same PEAR Root resolution as the engine
      (installer default fallback) — code unified in `pear_root.py`; clean-install
      verification is the HITL step below.
- [ ] HITL clean-machine: a first-run user reaches a working stream guided only by
      the on-screen checklist + wizard, without reading external docs (closes the
      open task 0010 AC).

## Plan

- [x] `onboarding.py` — pure step model (`onboarding_steps`, `onboarding_complete`)
      + `draw_getting_started` section. TDD. (`417b0ce`)
- [x] Wire the checklist at the top of `_draw_main_panel`; collapse when complete.
- [x] Guided-dialog operator (`invoke_props_dialog` + `draw`) over the existing
      `model_setup` pipeline. TDD the invoke/draw/execute logic.
- [x] Consolidate the three PEAR Root resolvers into one `pear_root.py`; give
      `model_setup` the installer-default fallback it lacked (clean-install bug).
- [ ] HITL clean-machine capture (with the win.6+ build) end to end.
- [x] Full gate + /ad-review (both axes; findings addressed).

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-11 — Created

Grounded design + decision above. Supersedes the "conditional section" onboarding
of task 0010 as the primary first-run surface (0010's download pipeline is reused,
not replaced). Reference: `/ad-ground` output this session; `invoke_props_dialog`
pattern (interplanety), Blender add-on guidelines.

### 2026-07-11 — Wizard shape: single guided dialog (grounded, decided)

The remaining slices landed: checklist wired into `_draw_main_panel` (top, until
`onboarding_complete`); guided-dialog operator `posecap.setup_body_models_wizard`
(`invoke_props_dialog` + `draw` + `execute`) over the existing `model_setup`
credential-install pipeline; and the three PEAR Root resolvers consolidated into
`addon/posecap_addon/pear_root.py` — `model_setup_panel._resolve_pear_root` now
gets the env + installer-default fallback it lacked, so the wizard no longer fails
"Set the PEAR Root first" on a clean install.

**Decision — single guided dialog, not a one-step-per-screen modal wizard.** AC ③
originally said "one step per screen"; grounded research (Ale's call to embase, not
guess) settled it the other way, on our real metric (easy for non-technical /
praise-worthy-intuitive / robust):

- **Praised competitors don't multi-step this.** BlenderKit — explicitly praised for
  "seamless onboarding [for] even beginners" and a "frictionless in-editor
  experience" — offloads account creation to the browser and keeps the in-app step
  a single minimal action. Rokoko Studio Live (the closest analog: mocap→Blender,
  login required) uses a simple login form, not a modal wizard. Our dialog mirrors
  BlenderKit: browser buttons for the three MPI account sites + credentials on one
  screen.
- **NN/g wizard guidance.** Wizards pay off for "complex processes… longer or
  higher-commitment tasks where a single page would feel overwhelming." This setup
  is two inputs + three links — a short task; the step ceremony is unwarranted.
- **Blender API idiom.** `invoke_props_dialog` cannot be combined with modal
  execution (Blender T48196); the documented best practice is a single
  comprehensive dialog. A true chained multi-step modal fights the API.
- **Hard constraint.** The MPI download endpoint is password-POST (see
  `model_setup._request_for`), not OAuth, so credentials must be typed in-app —
  BlenderKit's zero-typing OAuth path isn't available to us.

Review (`/ad-review`, two-axis fresh context): Standards Blocker fixed — setup
cancels now route through `Operator.report({'ERROR'}, …)` (a popup that closes on
`execute()` made the old status-label-only feedback invisible). Standards Concern
resolved by keeping `POSECAP_OT_SetupBodyModels` as the documented non-modal /
headless (`blender --background`) install entry the wizard wraps. Sources:
BlenderKit (github.com/BlenderKit/BlenderKit), Rokoko plugin
(github.com/Rokoko/rokoko-studio-live-blender), NN/g "Wizards"
(nngroup.com/articles/wizards), Blender T48196.

Landed `9f9f51f` on `main`, CI green. Real-Blender EFFECT check (Blender 5.0,
`--background`): the updated extension enables, the panel + wizard operator
`posecap.setup_body_models_wizard` + scene/WM props all register, and the
checklist logic + the installer-default resolver fallback both compute correctly
in real `bpy`. The new onboarding code was synced into the installed extension
(`…/Blender/5.0/extensions/user_default/posecap`) so the checklist is live for a
visual look. **Open:** AC ⑤ — the visual clean-machine walkthrough is Ale's to
eyeball (GUI-drive was declined this session); everything else is verified.

## Definition of Done

- [x] Local tests pass (full gate green; 306 tests + ruff/format/pyright ×2/
      import-linter). CI green on `main` (`9f9f51f`).
- [x] Code review completed (two-axis fresh-context `/ad-review`; Standards
      Blocker + Concern addressed, Spec decision grounded — see Notes).
- [x] No orphan `TODO`/`FIXME` introduced.
- [ ] Status updated to `done` and Notes log closes the task — held on the one
      open AC: the **visual** clean-machine walkthrough (Ale's eyeball). Real
      Blender headless already verified registration + the onboarding logic.
