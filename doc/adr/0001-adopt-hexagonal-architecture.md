# ADR-0001: Adopt hexagonal architecture with an enforced dependency rule

**Status:** accepted
**Date:** 2026-06-11
**Deciders:** Ale (alexandremendoncaalvaro), Dean (Corridor Digital)

## Context

The POC welded domain logic to `bpy`: pose mapping, keyframe policy, and channel math live inside operator classes, ~200 lines of preprocessing are copy-pasted across three engine scripts, and Windows process hacks sit inline in domain code. Nothing is testable without Blender plus a CUDA GPU. The product goals (PRD) include community contributors entering the codebase and a future second engine backend (Fast SAM 3D Body), both of which need stable seams. The rewrite needs a structure where the expensive dependencies — Blender, torch, hardware — are replaceable edges, not load-bearing walls.

## Decision

We will structure the system as hexagonal (ports and adapters) with five layers — `contracts/`, `core/`, `addon/`, `engine/`, `firmware/` — and an inward-only dependency rule: `contracts/` imports stdlib only; `core/` imports stdlib, numpy, and `contracts/`; `addon/` and `engine/` import inward only and never each other. `bpy`, `torch`, `serial`, sockets, and filesystem APIs are forbidden in `contracts/` and `core/`. The rule is enforced deterministically by import-linter in CI, not by review memory. Full layer definitions live in ARCHITECTURE.md.

## Consequences

* Domain logic (pose mapping, retargeting, keyframe policy) becomes testable without Blender, GPU, camera, or hardware — the 90% coverage target in GUIDELINES.md §9 is only achievable because of this.
* A second engine backend is an adapter behind the existing `PoseStream` port; no core changes.
* New contributors get a navigable structure with one place per concern.
* More ceremony than the POC: every capability needs a port, an adapter, and a wire format. Small features pay an indirection tax.
* The addon build needs vendoring machinery (ADR-0004) because two interpreters share `core/` and `contracts/`.

## Amendment (2026-06-12)

The `firmware/` layer was removed at product review: the Arduino encoder hardware was specific to Dean's own setup and is dropped from the product (PRD Non-goals). The structure is now four layers — `contracts/`, `core/`, `addon/`, `engine/` — under the same inward-only dependency rule. `serial` remains on the forbidden-import list for `contracts/` and `core/` as a guard. Mentions of `firmware/` and the five-layer count in the Context, Decision, and Consequences above are historical. ARCHITECTURE.md reflects the four-layer structure.

## Alternatives Considered

* Simple layered structure (ui → services → infra) — weaker seams; nothing stops `bpy` imports from leaking into services; test isolation not guaranteed.
* Pragmatic module split (cleaned-up POC layout) — fastest to ship, but reproduces the POC's central failure: logic only runnable inside Blender.
