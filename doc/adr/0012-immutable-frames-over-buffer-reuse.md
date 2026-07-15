# ADR-0012: Immutable frames win over buffer preallocation

**Status:** accepted
**Date:** 2026-07-15
**Deciders:** alexandremendoncaalvaro

## Context

GUIDELINES section 5 required "no per-frame allocations on hot paths — preallocate
and reuse numpy buffers". The shipped design contradicts it deliberately: pose
frames are frozen dataclasses whose arrays are made read-only
(`setflags(write=False)`), so every frame allocates fresh arrays by construction.
The full-repository audit confirmed the conflict is systemic — no hot path
preallocates, because none can while frames stay immutable. The engine's measured
bottleneck is model inference (17–24 FPS observed under GUI load), not allocation
or garbage collection, and no measurement attributes frame-time loss to
allocation.

Immutability exists for a reason: pose frames cross thread and process boundaries
(engine capture thread, TCP encode, addon reader thread, timer callback). A reused
mutable buffer on those paths invites aliasing bugs — a frame mutated while a
consumer still holds it — which are exactly the intermittent, unreproducible
failures a live-capture product cannot afford.

## Decision

Frame payload immutability is the binding design; buffer preallocation yields to
it. GUIDELINES section 5 is amended to require "no avoidable per-frame work"
(disk I/O, logging above DEBUG, string formatting beyond the wire format) and to
name fresh per-frame arrays as the accepted cost of aliasing safety.
Preallocation remains the guidance only where immutability is not part of the
contract (private scratch buffers inside one function). The existing mandatory
frame-time instrumentation and the 10% regression rule stay: if measurement ever
shows allocation dominating frame time, that evidence reopens this decision.

## Consequences

* Per-frame allocation on hot paths is no longer an audit violation; unmeasured
  micro-optimization pressure is removed.
* Aliasing safety across thread and process boundaries stays guaranteed by
  construction, not by review vigilance.
* Any future buffer-reuse proposal must arrive with frame-time measurements
  showing allocation as the bottleneck, and must supersede this ADR.

## Alternatives Considered

* Redesign for preallocated reusable buffers — rejected: touches core, engine,
  and addon; removes the immutability guarantee; and chases a bottleneck no
  measurement has demonstrated while inference dominates frame time.
* Keep the guideline text and treat violations as accepted drift — rejected: a
  binding document that the whole codebase deliberately violates trains readers
  to ignore it.
