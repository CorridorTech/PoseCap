# ADR-0014: Bind characters via compensated pose writes

**Status:** proposed
**Date:** 2026-07-17
**Deciders:** alexandremendoncaalvaro (maintainer), Dean (product direction)

## Context

Spec 0005 requires character setup that never modifies the user's asset.
Today the addon rewrites the armature (rename, T-pose re-rest, reorient)
so that streamed SMPL-X parent-relative rotations can be written directly
as pose-bone local quaternions; when the rewrite's geometry assumptions
fail, the asset is corrupted (task 0033). The product direction (Dean,
task 0034) is an intermediary binding layer.

Grounding across comparable tools (task 0034 research pass) found three
canonical non-destructive shapes in Blender:

1. Ghost-bone constraint binds — hidden helper bones carrying the
   character's rest orientation inside a driving armature, world-space
   Copy Rotation constraints on the character's pose bones (Expy Kit;
   Rokoko's offline retarget operator).
2. Cached per-bone rotation offsets computed once at bind, composed with
   each incoming frame in Python, written directly to pose bones (Rokoko
   Studio Live's live-streaming path; Keemap).
3. Source-side rest normalization plus bake (Auto-Rig Pro Remap) —
   offline-oriented, wrong shape for live streaming.

PoseCap's constraints: a 30 FPS hot path with a <100 ms latency budget
that already works by direct `rotation_quaternion` writes planned in
`core/` (`plan_pose_application`) and executed by a thin bpy adapter;
recording that keyframes inline on the driven bones as frames arrive (no
bake step); the hexagonal rule that decision math lives in `core/`,
testable without Blender; and a product tradeoff statement that favors
working-first-try over implementation convenience. Rokoko's live path
validates shape 2 at this frame rate but takes a shortcut PoseCap must
not copy: it disables `use_inherit_rotation` on the user's armature data
(a persistent asset mutation) instead of doing parent-relative math.

## Decision

We will bind characters by computing a per-bone binding map once at bind
time and driving the user's own pose bones with rest-compensated
quaternions every frame — shape 2, with full parent-relative composition
in `core/` and zero persistent writes to the asset.

Concretely:

* At bind, the bpy adapter reads each mapped bone's rest matrix (and the
  armature object transform) once and hands them to `core/`, which builds
  a binding map: per SMPL-X joint, the target bone name and the
  change-of-basis quaternions that convert an SMPL-X joint-frame rotation
  into that bone's local frame, including the rest-pose delta for non-T
  binds.
* Per frame, `plan_pose_application` output is composed through the
  binding map in `core/`; the existing pose writer writes the compensated
  quaternions to the user's bones by their original names. Pose channels
  and inline keyframes are the only writes that ever touch the asset —
  both are user-visible animation state, not asset structure.
* Binding verification runs as pure math on the binding map (the probe
  expectations become computable predictions), plus a pose-channel probe
  that is cleared afterward; no edit-mode changes, no modifier changes.
* Unbind clears PoseCap's pose channels and drops the binding map. No
  PoseCap datablocks remain in the file.

## Consequences

* The task 0033 failure class disappears structurally: a wrong geometry
  assumption produces a wrong prediction or a wrong pose — both costless
  and reversible — never a damaged asset.
* Binding math (basis changes, rest-delta compensation, verification
  predictions) is pure `core/` code with unit tests; the bpy adapter
  stays thin, per the dependency rule and the existing
  application-planning pattern.
* The hot path keeps its current shape and budget: one Python loop, one
  depsgraph tag, no per-frame scene objects, no constraint dependency
  graph. Recording keeps inline keyframing on the user's own action —
  takes survive unbinding with no bake.
* Presets (UE, Mixamo, custom JSON) reduce to name mappings consumed at
  bind time; the destructive re-rest/reorient machinery is no longer
  needed for capture once the binding ships.
* Negative: rotation composition that constraints would do in C now runs
  in Python per frame; the existing 30 FPS instrumentation must confirm
  the added quaternion multiplications stay inside the 10% regression
  rule (GUIDELINES §5).
* Negative: correctness rests entirely on our math instead of Blender's
  constraint evaluator; the compensating control is that pure-math
  verification is unit-testable at a depth scene-mutation code never was.
* The binding map is runtime state: file save/reload while bound must
  restore or cleanly degrade (spec 0005 edge case), which the
  implementation tasks must design for explicitly.
* The fate of the destructive conversion path is a separate maintainer
  decision this ADR does not make; until it is recorded, the path remains
  shipped and field-viable (task 0033's fix).

## Alternatives Considered

* Ghost-bone constraint bind (shape 1, Dean's literal "intermediary rig")
  — rejected for the live path: requires edit-mode surgery and a second
  armature datablock, puts constraints on the user's bones (conflict
  policy needed with their own constraints), and forces a visual-keying
  bake for recording (slow enough that Rokoko chunks it 25 frames at a
  time). Kept in mind as an optional later UX layer if users should see
  and edit the binding; the binding-map seam does not preclude it.
* Source-side rest normalization plus bake (shape 3) — rejected: offline
  batch shape; PoseCap's primary path is live streaming with inline
  recording.
* Repair the destructive path harder (extend task 0033's geometric gate)
  — rejected as the structural direction: every new skeleton family
  reintroduces mutation risk; the gate shrank the failure class but
  cannot close it, and the maintainer's product direction is
  non-destructive setup.
* Rokoko's `use_inherit_rotation = False` shortcut inside shape 2 —
  rejected outright: it is a persistent mutation of the user's armature
  data, exactly what spec 0005 forbids; parent-relative composition in
  `core/` replaces it.
