# Task 0033: Fix armature conversion for custom Mixamo characters

**Status:** in-progress
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:**
**Board ref:**

## Context

Field report (2026-07-17, screenshot relayed by the maintainer): converting
the armature for PoseCap on custom Mixamo-rigged characters "lifts one arm up
high and messes everything up", on both the Auto and the Mixamo preset, and
fails with `probe raise_z failed: error 0.1873 > tolerance 0.0058`. Default
Mixamo characters convert fine. The reporter confirmed v1.0.5 fixed their
previous issue, so this is the next blocker in their pipeline.

Code reading against the symptom (addon/posecap_addon/character_setup.py):
`convert_armature` re-rests the arm chains into a T-pose (`_re_rest_tpose`)
and applies the result as the new rest pose before renaming/reorienting; the
self-verification (`_verify`) then rotates `left_shoulder` 90 degrees and
compares the elbow's world displacement against an analytic expectation, with
tolerance = 5% of the measured arm length. The reported tolerance 0.0058
implies an arm length of ~0.116 world units — a centimeter-scaled import is
likely in play — and the visible lifted arm matches a mis-aligned arm chain
being permanently applied as rest. Custom Mixamo auto-rigged characters can
differ from the default ones in bone rolls, twist/extra bones inside the arm
chain, object scale, and non-T bind poses; any of these can break the
head-to-child-head direction assumption in `_re_rest_tpose`'s `align`.
Unverified until reproduced — these are ranked starting hypotheses, not a
diagnosis.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] A reproduction exists: a custom Mixamo-rigged character (auto-rigged
      non-default mesh) whose conversion currently fails the `raise_z` probe,
      captured as a licensed-clean test fixture or a scripted armature
      equivalent.
- [x] Root cause identified through the disciplined loop (`ad-diagnose`):
      ranked falsifiable hypotheses, one-variable instrumentation, evidence
      recorded in Notes.
- [ ] Conversion of the reproduction case succeeds: probes pass and the
      character's rest pose is visually correct (no lifted arm), without
      regressing default Mixamo, UE, or the existing task 0008 validation
      matrix.
- [x] The failure message, when conversion still legitimately fails, tells a
      non-technical user what to do next (today's probe message is
      diagnostics-grade, not user-grade).
- [ ] The reporter is answered through the original channel with the outcome
      and the release that carries the fix.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [x] Reproduce: build/obtain a custom Mixamo auto-rigged character (no
      licensed assets committed), convert, capture the probe failure and the
      lifted-arm rest pose.
- [x] Diagnose (`ad-diagnose`): rank hypotheses (twist/extra bones in
      `arm_chains`, bone-roll variance breaking `align`'s direction math,
      centimeter object scale interacting with `_verify`'s absolute floor,
      non-T bind pose) and instrument one at a time.
- [x] Fix with regression tests at the level `tests/addon/` exercises;
      extend the probe/verification messages for user-grade guidance.
- [ ] Answer the reporter; ship with the next release.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-17 — report received

Prioritized by the maintainer into the v1.0.7 field-driven slice (user
requests first). Error string verbatim from the screenshot:
`probe raise_z failed: error 0.1873 > tolerance 0.0058`. Reporter notes the
failure is model-independent ("it wasn't just this model") and preset-
independent (Auto and Mixamo).

### 2026-07-17 — relation to task 0034

Dean's non-destructive intermediary-armature suggestion is recorded as task
0034: it would make this failure class structurally impossible (the user's
asset would never be mutated). This task remains the immediate field fix on
the destructive path; its diagnosis feeds the 0034 decision on how much the
destructive path deserves to be repaired versus replaced.

### 2026-07-17 — diagnosis closed (ad-diagnose)

Feedback loop: a headless-Blender script builds synthetic Mixamo-named
armatures (no licensed assets) emulating a Blender FBX import (Y-up object
rotation, centimeter scale) and runs the real `convert_armature` on one
variant per hypothesis. Deterministic, ~5 s for seven variants.

Hypothesis outcomes, one variable per variant:

- Centimeter scale / tolerance floor — FALSIFIED. A T-posed character with
  arm length 0.116 world units converts with error 0.0000.
- Bone-roll variance — FALSIFIED. Randomized rolls on a T-posed armature
  convert with error 0.0000 (the reorient's `align_roll` normalizes them).
- Twist/extra arm bones — NOT TESTED; unnecessary once the winner reproduced
  both field numbers (Mixamo auto-rigger emits no twist bones).
- Non-T bind pose — CONFIRMED. Arms drooped ~70 degrees below horizontal on
  a small character reproduce the field report to three decimals: tolerance
  0.0058 (exact) and error 0.1853 vs the reported 0.1873 (residual ~1% is
  the real character's arms not being perfectly straight).

Root cause: `mixamo_preset` hard-codes `already_t_pose=True` ("Mixamo
characters download in T-pose", task 0008). True for library characters,
false for custom uploads — the auto-rigger keeps whatever bind pose the
uploaded mesh had (commonly arms-down). The re-rest is skipped, the reorient
assumes a T-pose that is not there, and the `raise_z` probe fails. The
"lifted arm high" in the screenshot is the probe's own 90-degree shoulder
rotation surviving the error path (the pose reset only ran on success),
compounding the mutated bone names/orientations.

Fix (this branch): the T-pose claim is now verified geometrically —
`arm_t_pose_deviation_degrees` in `posecap_core.retarget` measures the
shoulder-to-elbow direction against the T-pose target, and a deviation
beyond 2 degrees (probe failure starts at ~2.9) triggers the existing
re-rest. Default T-posed characters measure ~0 and keep skipping it (no
regression, and shape-keyed default characters stay convertible). Probe
failure now resets the pose and tells the user the way out (Ctrl+Z,
re-export in T-pose); a shape-keyed mesh that needs re-posing is refused
with the same guidance instead of leaking Blender's RuntimeError.
Regression tests: pure-math coverage in tests/core/test_retarget.py and a
scripted-armature e2e in tests/e2e/test_blender_addon_smoke.py.

Implication for task 0034 (non-destructive intermediary armature): this
failure class is a symptom of the destructive path's structure — conversion
mutates the user's asset before self-verification can prove the geometry
assumptions hold, so every wrong assumption ships as visible damage plus an
undo burden. The geometric gate added here shrinks the class but cannot
close it (unknown rigs can still fail after mutation). Dean's intermediary
armature would make the class structurally impossible: probes could run on
the intermediary before anything touches the user's asset, and a failure
would cost nothing. The destructive path is now field-viable for UE and
Mixamo (library and custom); 0034's HITL question for the maintainer is
whether it stays as the fallback for unrecognized rigs or is replaced
outright.

### 2026-07-17 — fresh-context review applied (two-axis, WORKFLOW §10)

Standards axis: added the missing `bpy.context.view_layer.update()` before
the position reads in `_needs_re_rest` (stale-depsgraph risk, matching the
in-file pattern); linked the re-rest trigger margin to the probe tolerance
through one shared `PROBE_RELATIVE_TOLERANCE` constant in the retarget
domain (previously a duplicated 0.05 literal across converter default, CLI
default, and test).

Spec axis: the decision moved into the domain as public
`needs_t_pose_re_rest` with CI-covered unit tests (UE always re-rests,
measured T keeps the skip, 1.9/2.1-degree edges, one drooped arm suffices);
a `tests/addon/` fake-bpy test now exercises the geometric gate and the
shape-key refusal through `convert_armature` in CI (the e2e suite self-skips
without a local Blender); the e2e script gained threshold-crossover cases
(1.5-degree droop converts with shape keys intact, 2.5-degree fires the
re-rest and converts without them); the probe-failure message now leads with
user language and keeps the diagnostics parenthetical. AC3 stays unchecked:
the synthetic no-regression evidence is automated, but the task 0008
real-character matrix (X Bot / Y Bot in the Blender GUI) was not re-run —
it rides the next release qualification.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
