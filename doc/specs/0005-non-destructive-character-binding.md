# Spec 0005: Bind characters for capture without modifying the asset

**Status:** draft
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro

## Context

Character setup today converts the user's armature in place: bones and
vertex groups are renamed to SMPL-X joint names, arm chains are re-rested
into a T-pose, and bone orientations are rewritten so streamed rotations
land in the right space (doc/workflows.md "Target armature requirements").
The conversion is destructive by design — and when its geometry assumptions
misjudge a skeleton, the user's asset is corrupted rather than merely
unconverted. Task 0033 was exactly this class in the field: a custom Mixamo
character permanently damaged (arm raised, bones renamed) by a conversion
that then failed its own verification. The product maintainer's direction
(Dean, relayed 2026-07-17, task 0034) is an intermediary layer the user's
character binds to, so setup is non-destructive and failure costs nothing.

PoseCap's users are editors, animators, and designers — an asset they
imported must never be at risk from a setup step. Every comparable tool
(Rokoko Studio Live, Auto-Rig Pro Remap, Expy Kit) keeps the user's bone
names and rest pose untouched and binds through a mapping layer; PoseCap's
destructive conversion is the outlier. Not shipping this leaves every new
skeleton family one wrong geometric assumption away from destroying user
work, and keeps "undo the conversion" as the only recovery path.

## User Scenarios

- **Scenario 1:** bind a recognized character
  - Given an imported character whose skeleton family PoseCap recognizes
    (Unreal Engine or Mixamo, library or custom upload, any bind pose)
  - When the user clicks the character-setup action
  - Then the character is ready for live capture, and the user's armature —
    bone names, vertex groups, rest pose, bone orientations — is unchanged

- **Scenario 2:** live capture through the binding
  - Given a bound character and a running pose stream
  - When frames arrive
  - Then the character follows the performance with the same visual result
    the destructive conversion produced (task 0008 validation matrix), at
    the same frame budget

- **Scenario 3:** recording through the binding
  - Given a bound character with recording enabled
  - When the user records a take
  - Then keyframes land on the user's own armature action and survive
    unbinding — no bake step, no PoseCap objects referenced afterward

- **Scenario 4:** teardown
  - Given a bound character (including a mid-stream or failed state)
  - When the user removes the binding
  - Then the asset is byte-identical to before setup (verifiable by
    comparing armature data before bind and after unbind)

- **Scenario 5:** binding fails
  - Given a character PoseCap cannot bind (unrecognized skeleton, missing
    bones)
  - When the user attempts setup
  - Then the character is untouched, and the failure message tells a
    non-technical user what to do next

## Requirements

### Functional

- User can set up a recognized character for capture without any rename,
  re-rest, reorientation, or other persistent edit to the armature, mesh,
  or vertex groups.
- The binding drives the user's bones through the existing preset name
  mappings (UE, Mixamo with prefix variants, custom JSON) — presets become
  bind mappings, not destructive edits.
- Non-T bind poses (the task 0033 class) bind and capture correctly; the
  rest-pose delta is compensated by the binding, not repaired on the asset.
- Setup verifies the binding before declaring the character ready, without
  mutating the asset to do so; verification failure leaves no trace.
- User can unbind in one step from any state, including after a failure or
  a Blender session reload.
- Recording writes keyframes to the user's armature so takes remain after
  unbinding.
- The existing destructive conversion remains available per the accepted
  ADR that records its fate (see Related).

### Non-functional

- Frame budget unchanged: 30 FPS pose application, <100 ms
  capture-to-viewport (PRD budget); binding adds no per-frame scene
  objects or constraint dependencies on the hot path.
- Binding math lives in `core/` (stdlib + numpy), unit-testable without
  Blender, per the hexagonal dependency rule (GUIDELINES §1).
- Failure messages are user-grade (GUIDELINES §2.2): what happened, what
  to do next, no tracebacks.

## Success Criteria

Definitional. Measurable conditions; pass/fail observable, not
aspirational. Per-criterion progress tracking lives in per-Spec tasks.

- Before/after comparison of the armature datablock (bone names, rest
  matrices, rolls, vertex-group names) across bind → capture → unbind
  shows zero differences, automated in the e2e suite.
- The task 0033 reproduction (custom Mixamo, arms drooped, centimeter
  scale) and the task 0008 matrix families capture correctly through the
  binding, pinned by the same probe expectations the converter uses today.
- Steady-state frame time through the binding is within 10% of the
  converted-armature baseline (GUIDELINES §5 regression rule), measured by
  the existing frame-time instrumentation.
- A recorded take plays back on the user's armature after unbinding with
  no PoseCap datablocks remaining in the file.

## Edge Cases

- Bones missing from the mapping (custom uploads without fingers): bind
  body-only, as detection does today.
- The user's bones carry pre-existing animation data or constraints: the
  binding must not delete them; a conflict is reported, not resolved
  silently.
- Armature object with non-identity rotation or centimeter scale (Y-up FBX
  imports): compensation includes the object transform.
- Blender file saved while bound, reopened: binding either restores or
  degrades to a clean unbound state — never a half-driven armature.
- Undo pressed mid-capture: no crash, no StructRNA errors (AGENTS.md
  gotcha), stream degrades gracefully.
- A character already converted by the destructive path: binds like any
  SMPL-X-named armature (identity mapping, zero rest delta).

## Out of Scope

- Arbitrary-armature retargeting beyond the existing preset families
  (custom and Rigify targets are PRD "Later"; this spec creates the seam,
  not the feature).
- World position (pelvis-locked per doc/workflows.md).
- Migration tooling for assets already damaged by past failed conversions.
- Removing the destructive conversion path (its fate is an ADR decision,
  recorded separately).

## Open Questions

- Fate of the destructive conversion path (kept as fallback, hidden, or
  removed after a field-proving period) — maintainer decision, recorded in
  the binding-architecture ADR.
- Whether the binding surfaces to the user as a visible PoseCap-owned
  intermediary armature (Dean's literal phrasing) or stays an invisible
  mapping layer — UX decision; the architecture ADR records the driving
  mechanism either way.

## Related

- ADRs: doc/adr/0014-bind-via-compensated-pose-writes.md (proposed with
  this spec)
- Tasks: doc/tasks/0034-nondestructive-intermediary-armature.md (parent);
  implementation tasks appended as they are created
- Depends on: doc/specs/0001-live-webcam-pose-streaming.md (stream
  contract); task 0033's fix defines the destructive path this replaces
