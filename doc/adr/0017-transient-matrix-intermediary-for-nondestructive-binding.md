# ADR-0017: Use a transient native intermediary for non-destructive binding

**Status:** superseded by ADR-0018

## Context

ADR-0014 chose a cached per-bone quaternion map to avoid a visible
intermediary. The task-0033 regression fixture disproved that simplification
for a parented non-T armature: the four plausible quaternion compositions
failed at least one of the legacy converter's shoulder probes. Blender's
`Bone.convert_local_to_pose` and Rigify's transfer utilities show that chain
retargeting must carry parent pose matrices and rest matrices recursively.

The product requirement does not permit solving this by re-resting the user's
armature. It requires the same capture result while leaving names, weights,
rest data and mesh structure untouched.

## Decision

Create a temporary, hidden intermediary armature only while a bound stream is
active. Its armature data is a copy of the selected target's data;
the existing converter normalizes that copy, never the target. Incoming
rotations drive the normalized intermediary. Blender-native `Copy Transforms`
constraints transfer its evaluated pose to the target.

The binding custom property remains the durable user-visible state. The
intermediary is runtime-only: every normal, failure and stop path removes its
object and copied armature datablock. Recording still keys the target's own
rotation channels, so takes remain after unbind and contain no intermediary
reference.

## Consequences

* This supersedes ADR-0014's direct-quaternion live-path mechanism. The
  binding map remains the durable source-to-target name map, while the native
  evaluator owns connected-bone translation semantics that isolated target
  quaternions cannot reproduce.
* Non-T and parented chains use the same evaluated-pose behavior as the proven legacy
  converter without changing user rest data.
* Capture creates one short-lived PoseCap-owned object and evaluates an extra
  source pose per frame. Its measured frame-time must remain within the
  existing ten-percent regression budget before this ADR is accepted.
* A saved bound file restores by rebuilding the intermediary at next stream
  start; no generated source is serialized.
* The source object and constraints are capture-session runtime state only;
  they are removed on normal stop, invalid-target recovery, and startup
  failure. No generated datablock is saved as the binding.
