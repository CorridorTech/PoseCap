# Task 0034: Drive characters through a non-destructive intermediary armature

**Status:** in-progress
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** [spec 0005](../specs/0005-non-destructive-character-binding.md)
**Board ref:**

## Context

Dean's product suggestion (2026-07-17, Discord): "Rather than converting the
rig, it would be cool to create an 'intermediary' rig that we can bind the
target rig to so it is non-destructive." (Repo vocabulary: armature, per
GUIDELINES §2.1 — "rig" stays out of code and UI copy.)

Today's character setup mutates the user's asset in place
(`addon/posecap_addon/character_setup.py`): it renames bones and vertex
groups, re-rests the arm chains into a T-pose, and applies that as the new
rest pose. When the alignment math misjudges a skeleton — exactly the class
of failure in task 0033, where custom Mixamo characters end up with an arm
permanently raised — the user's asset is corrupted, not just unconverted.
An intermediary architecture inverts this: PoseCap owns and drives a
correctly-shaped SMPL-X armature (which it already knows how to build), and
the user's character binds to it through constraints or a retarget layer.
Conversion failures become reversible (delete the intermediary, character
untouched), presets become bind-mappings instead of destructive edits, and
the same binding seam is the future home for arbitrary-armature retargeting
(PRD "Later": custom and Rigify targets).

This is an architecture-level change to the retarget path: it needs a
feature spec and an ADR, not a patch. Task 0033 stays open as the immediate
field fix — its diagnosis should inform whether the near-term repair effort
goes into the destructive path or is redirected here.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] A feature spec (doc/specs) and an ADR record the intermediary-binding
      architecture: how the intermediary armature is created, how a target
      character binds to it (constraints versus drivers versus other),
      what happens to the existing destructive conversion path, and the
      migration story for characters already converted.
- [ ] Setting up a character for capture leaves the user's armature, bone
      names, vertex groups, and rest pose byte-identical when the user
      removes PoseCap's intermediary (verifiable by comparing the asset
      before setup and after teardown).
- [ ] A failed or imperfect binding is recoverable in one step and reports a
      user-grade message; the character asset is never modified as part of
      the failure path.
- [ ] Live capture and recording behavior through the intermediary matches
      the current direct path within the task 0008 validation matrix
      (default Mixamo, UE, and the custom-character reproduction from task
      0033).
- [ ] Dean's suggestion is answered with the recorded direction.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [x] Ground (`ad-ground` / `ad-grill`): how comparable tools bind mocap to
      arbitrary characters non-destructively (Rokoko retargeter, Auto-Rig
      Pro remap, Blender constraint-based retargeting addons), and what the
      existing `character_setup.py` machinery (SMPL-X armature creation,
      mapping presets, probe verification) can be reused as the intermediary
      builder and the binding validator.
- [ ] Draft the spec and ADR; decide the fate of the destructive conversion
      (kept as legacy, hidden, or removed) with the maintainer.
- [ ] Implement per the spec's task split (TDD; binding correctness pinned
      against the task 0008 matrix plus the task 0033 reproduction).
- [ ] Answer Dean; ship with a release.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-17 — suggestion recorded

Relayed by the maintainer with the instruction that task 0033's field report
makes this direction "very important". Relationship recorded on both sides:
0033 is the user-blocking bug on the destructive path; this task is the
structural fix that would make that failure class impossible. The 0033
diagnosis decides how much repair the destructive path deserves in the
meantime.

### 2026-07-17 — ground closed; spec and ADR drafted

Ground closed (four sources: official Blender docs, line-level reading of
the Rokoko / Expy Kit / Keemap repos plus Auto-Rig Pro documentation,
in-repo pose-application seams, git history of the conversion path). The
synthesis and the shape selection live in
[ADR-0014](../adr/0014-bind-via-compensated-pose-writes.md); the feature
contract is [spec 0005](../specs/0005-non-destructive-character-binding.md)
(draft).

Note on the title: the selected design creates no intermediary armature
object — the binding is a computed map driving the user's own bones, per
ADR-0014's Decision; Dean's literal ghost-armature shape is recorded there
as the rejected alternative (kept possible as a later UX layer). The
outcome he asked for (non-destructive, failure costs nothing) is the
spec's contract.

Maintainer decisions pending (HITL): accept spec 0005 and ADR-0014, and
the fate of the destructive conversion path (recommendation: keep as
shipped fallback while the binding field-proves for one release, then
retire; open question in spec 0005, to be recorded in its own ADR).

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
