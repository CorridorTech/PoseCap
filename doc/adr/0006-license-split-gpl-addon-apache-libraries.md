# ADR-0006: License split — GPL-3.0 addon, Apache-2.0 everything else

**Status:** accepted
**Date:** 2026-06-11
**Deciders:** Ale (alexandremendoncaalvaro), Dean (Corridor Digital)

## Context

The product will be free and open source. Blender is GPL and the Blender Foundation's position is that addons using the `bpy` API must be GPL-compatible, so the addon's license is constrained. The engine bridge, contracts, and core have no such constraint and are useful outside Blender (a future non-Blender consumer of the pose stream, the firmware ecosystem). The POC addon descends from the Meshcapade SMPL addon (GPL-3.0); this rewrite is clean-room precisely so no GPL lineage carries over and the non-addon packages are free to choose. Body-model files are licensed separately by MPI/Meshcapade and are unaffected — they never enter the repo regardless (ADR-0005, AGENTS.md).

## Decision

We will license `addon/` under GPL-3.0 and `contracts/`, `core/`, `engine/`, and `firmware/` under Apache-2.0. Each package carries its license in its metadata; the repo root documents the split. Vendoring Apache-2.0 wheels into the GPL-3.0 extension zip is a compatible one-way flow (Apache-2.0 is GPLv3-compatible). No code is ever copied from the POC addon into any package.

## Consequences

* The bridge, contracts, and firmware are reusable in permissive contexts, with Apache's explicit patent grant — relevant in the ML ecosystem.
* The extension zip as a whole distributes under GPL-3.0 with Apache notices retained; compliant and standard.
* Code may flow Apache → GPL (into the addon) but never GPL → Apache; contributors must know which side a change lands on. Reviews police this one rule.
* Two licenses add a line of explanation to CONTRIBUTING when it lands; slight onboarding overhead versus a single license.
* Resolves the PRD open question on license split.

## Amendment (2026-06-12)

`firmware/` was dropped from the product at product review (see ADR-0001 amendment; PRD Non-goals). The split now covers four packages: `addon/` under GPL-3.0; `contracts/`, `core/`, and `engine/` under Apache-2.0. Mentions of firmware in the Context, Decision, Consequences, and Alternatives above are historical.

## Alternatives Considered

* GPL-3.0 for everything — simplest story and common for Blender addons, but blocks permissive reuse of the bridge and firmware outside GPL projects.
* Apache-2.0/MIT for everything including the addon — conflicts with the Blender Foundation's GPL-compatibility expectation for `bpy`-linked code.
* MIT instead of Apache-2.0 for the libraries — no patent grant; Apache preferred given the ML-adjacent surface.
