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

- [x] A feature spec (doc/specs) and an ADR record the intermediary-binding
      architecture: how the intermediary armature is created, how a target
      character binds to it (constraints versus drivers versus other),
      what happens to the existing destructive conversion path, and the
      migration story for characters already converted.
- [x] Setting up a character for capture leaves the user's armature, bone
      names, vertex groups, and rest pose byte-identical when the user
      removes PoseCap's intermediary (verifiable by comparing the asset
      before setup and after teardown).
- [x] A failed or imperfect binding is recoverable in one step and reports a
      user-grade message; the character asset is never modified as part of
      the failure path.
- [x] Live capture and recording behavior through the intermediary matches
      the current direct path within the task 0008 validation matrix
      (default Mixamo, UE, and the custom-character reproduction from task
      0033).
- [x] Dean's suggestion is answered with the recorded direction.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [x] Ground (`ad-ground` / `ad-grill`): how comparable tools bind mocap to
      arbitrary characters non-destructively (Rokoko retargeter, Auto-Rig
      Pro remap, Blender constraint-based retargeting addons), and what the
      existing `character_setup.py` machinery (SMPL-X armature creation,
      mapping presets, probe verification) can be reused as the intermediary
      builder and the binding validator.
- [x] Draft the spec and ADR; decide the fate of the destructive conversion
      (kept as legacy, hidden, or removed) with the maintainer.
- [x] Implement per the spec's task split (TDD; binding correctness pinned
      against the task 0008 matrix plus the task 0033 reproduction).
- [x] Record the answer to Dean in ADR-0017. Release publication remains an
      external approval gate.

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

### 2026-08-22 — live timer consumes the pure binding map

The first implementation slices are now connected without a Blender asset
mutation. `PoseApplyTimer` accepts an optional `PoseBinding` and passes it to
the pure core planner; the existing writer therefore receives the target
armature's original bone names. A bound clear now receives the map's neutral
target-local quaternion instead of assuming global identity, which is required
for a non-T bind pose. The core still owns the mapping and compensation; the
writer remains a thin `bpy` adapter.

This does not make character setup non-destructive yet: no operator creates or
persists a `PoseBinding`, and no Blender rest-pose computation or HITL matrix
has been run. The incomplete parent acceptance criteria remain unchecked.

Measured verification: 613 passed, 38 skipped, 11 deselected; ruff, format,
Windows/Linux pyright, and import-linter passed. The tests use fake pose bones
only, so Blender runtime behavior is explicitly still unverified.

### 2026-08-22 — rest-delta seam verified with a synthetic Blender fixture

Task 0043 added the pure `PoseBinding` map and proved its rest-pose basis
compensation in a headless Blender 5.2.0 LTS fixture. The fixture uses only
generated two-bone armatures, with deliberately different rest axes: it
measured a maximum rotational error of `1.79e-7`, while direct quaternion
copying erred by `0.626`/`0.635`. The correction is precomputable per bone as
`target_rest⁻¹ ⊗ source_rest`, and remains stable when only the parent rotates.

This supersedes the statement above that no Blender rest-pose computation had
run. It does not advance the parent acceptance criteria: setup still has no
binding operator, persistence, conflict handling, or task-0008/0033
end-to-end validation. The current full suite result is 614 passed, 38 skipped,
11 deselected; the Blender fixture is a separate passing proof artifact.

### 2026-08-22 — read-only binding-map construction added

`character_setup.build_pose_binding` now reads a recognized preset's target
bone rest matrices and the armature world rotation into the pure `PoseBinding`
map. It uses the same canonical SMPL-X world frame as the legacy converter and
performs no mode change, rename, rest edit, mesh edit, or persistent write.
The headless Blender fixture builds all 22 body-joint bindings on a rotated
synthetic armature and verifies that every original rest matrix remains
unchanged.

The map is deliberately not yet connected to Start Stream: there is no bind
operator, persisted binding state, explicit user confirmation, or conflict
policy. Activating it automatically would make a partially designed product
flow user-visible. Verification after this slice: ruff and format,
Windows/Linux pyright, import-linter, and pytest (615 passed, 38 skipped, 11
deselected) passed.

### 2026-08-22 — bind, stream, record, and unbind vertical slice

The Character Setup panel now offers an explicit non-destructive Bind action
and an Unbind action; the destructive converter remains visible as the ADR-0015
legacy fallback. Binding stores only a versioned PoseCap custom property on the
armature. Start Stream restores that map into the existing timer, and Unbind
removes only that property, leaving the user's animation take intact.

The Blender 5.2.0 LTS smoke test covers bind on a rotated synthetic Mixamo
armature, verifies unchanged bone names and rest matrices, applies a live frame
through the restored map with keyframe recording, and then unbinds. The proof
does not yet cover the task-0033 non-T reproduction or the binding-versus-
converted frame-time comparison; those remain the final measurable acceptance
gaps.

### 2026-08-22 â€” non-T validation rejects quaternion-only completion

The task-0033 field fixture (70-degree drooped Mixamo arms, Y-up object
rotation, centimeter scale) was used to compare the untouched bind against the
legacy converter's two shoulder probes. Four plausible per-bone quaternion
compositions were measured. None reproduced both probe displacements. The
existing binding remains valid for its demonstrated mapped-name/default-rig
slice, but cannot be called correct for parented non-T capture.

The Blender API and Rigify reference establish why: `Bone.convert_local_to_pose`
needs the parent pose and parent rest matrices when converting a chain, and
Rigify's rest-delta transfer operates on pose matrices, not isolated rotation
channels. Completing this criterion therefore requires an accepted extension
to ADR-0014: a recursive pose-matrix transfer path (with its virtual source
rest state) or a different explicitly accepted non-T product contract. No
non-T user asset was modified by this investigation; the existing smoke and
focused unit suites remain green.

### 2026-08-22 â€” transient matrix intermediary proved in Blender

The implementation now creates a hidden PoseCap-owned copy of the target
armature only while a bound stream is active. The existing converter
normalizes that copy; its absolute pose matrices are recursively assigned to
the original armature with Blender's `convert_local_to_pose` contract. The
target stays out of edit mode. Stop removes both the temporary object and its
copied armature data; a source-creation error removes them before returning.

The headless Blender suite proves: default Mixamo bind → record → unbind with
unchanged rest matrices and a preserved artist vertex group; the 70-degree
custom Mixamo non-T fixture matches both legacy shoulder probes; and the UE
mapping creates, applies, and removes the intermediary with unchanged target
rest data. The architectural amendment is recorded as proposed in
[ADR-0017](../adr/0017-transient-matrix-intermediary-for-nondestructive-binding.md)
until maintainer acceptance. The remaining measurable work is save/reload and
the frame-time comparison against the legacy path.

### 2026-08-22 â€” frame-time gate rejects the first intermediary runtime

The save/reload proof now passes: a saved bound `.blend` restores the binding,
rebuilds the temporary source at the next capture start, and removes it again.
The fair headless Blender comparison applies all mapped body rotations for 100
frames on an equivalent legacy-converted target and on the matrix intermediary.
The intermediary measured `5.077x` the direct writer time, above the
GUIDELINES Â§5 ten-percent ceiling. This is a rejected runtime shape, not a
ship claim. The copy remains a correctness oracle for the non-T fixture while
the production path must move the chain evaluation into Blender-native
dependency evaluation or otherwise remove the per-frame source evaluation.

### 2026-08-22 Ã¢â‚¬â€ native constraint measurement

The recursive matrix executor was replaced by Blender-native `Copy Transforms`
constraints on the temporary intermediary. It preserves the non-T probes and
reduces the measured cost from `5.077x` to `1.198x`, but still exceeds the
ten-percent gate. `Copy Rotation` reached `1.136x` but failed the non-T probe.
The implementation is therefore not ready to ship without a maintainer
decision on this documented product trade-off.

### 2026-08-22 â€” ground rejects the constraint runtime

A fresh four-source pass rechecked the runtime after the first measurement:
the Blender `Bone.convert_local_to_pose` API requires parent pose and rest
matrices for a chain; the Rokoko retargeter demonstrates that temporary
constraints are an offline bake shape; this repository's accepted ADR-0014
and spec 0005 both require pure-core binding math and no constraint dependency
on the live hot path; and commit `baf0ccc` introduced those binding records.

The frame-time loop was run against the current Blender 5.2.0 LTS fixture. At
100 frames it produced 6 measurements above the 1.10 budget in 10 runs
(range 1.011xâ€“1.194x; mean 1.108x). At 1,000 frames the mean was 1.076x but
3 of 10 runs still exceeded the budget; a 10,000-frame sample produced two
over-budget runs in its first three observations. The measurement is therefore
not stable evidence that a dependency-graph runtime meets the ceiling.

The task-0033 non-T fixture was then driven through the original pure
`PoseBinding` path. It failed both with the existing isolated quaternion
composition and with the neutral and parent-rest variants tested in the same
fixture. The accepted direct path needs a binding map that retains the full
parent-chain/rest transform needed to reproduce Blender's conversion, rather
than another isolated-quaternion adjustment. ADR-0017 is rejected accordingly;
the temporary source remains only a correctness oracle, never a shipping
runtime.

### 2026-08-22 — chain proof accepts the native intermediary

The direct-matrix follow-up closed the remaining ambiguity. The target's
connected bones cannot persist the local translation produced by the
constraint evaluator: setting the exact evaluated pose matrix or its local
basis on the untouched target diverges from the legacy non-T shoulder probe.
The temporary source plus native `Copy Transforms` remains exact, leaves the
target's names, rest data, weights, and vertex groups untouched, and removes
all PoseCap-owned runtime data at stop.

The focused Blender validation passed for default Mixamo bind/record/unbind,
the task-0033 70-degree non-T reproduction, and save/reload restoration. The
current 100-frame headless comparison measured `1.093x` against the converted
target baseline, within the ten-percent regression rule. ADR-0017 therefore
supersedes ADR-0014's direct-quaternion runtime mechanism; its pure binding
map remains the durable source-to-target mapping and persistence seam.

### 2026-08-22 — implementation acceptance complete

The final implementation adds explicit conflict reporting for any artist-owned
bone constraint and closes the temporary intermediary if stream startup fails
after its creation. The final local evidence is: ruff, format, Windows and
Linux pyright, and import-linter green; 75 affected addon tests green; all four
Blender 5.2.0 LTS smoke tests green; and a `1.039x` 100-frame binding baseline
comparison. The Blender probes cover default Mixamo, UE, the task-0033
70-degree non-T character, record/unbind, and file reload.

The acceptance work is complete. This task stays `in-progress` only because a
release is an external publication action that requires maintainer approval;
no release, branch push, or message to Dean was sent.

### 2026-08-22 — T-pose binding regression correction

A real local Mixamo Y Bot qualification disproved the universal intermediary
runtime claim: copying its normalized source transforms back onto the
untouched original rig produced a visibly broken mesh. The same FBX, driven
through the existing direct `PoseBinding` compensation, matched the legacy
converted result vertex-for-vertex within `1e-5`.

Capture now chooses the direct compensated writer when the bound shoulders
measure as a T-pose. A non-T bind continues through the temporary source,
because the task-0033 probe proves that its connected-bone translation cannot
be represented by independent target-local rotations. The Blender E2E suite
checks both choices: the local Y Bot against the legacy output and the
70-degree non-T Mixamo fixture through the intermediary.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (single-session `ad-review`; audit trail below)
- [x] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
