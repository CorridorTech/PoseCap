# ADR-0003: Use JSON for all IPC and pose files; ban pickle

**Status:** accepted
**Date:** 2026-06-11
**Deciders:** Ale (alexandremendoncaalvaro), Dean (Corridor Digital)

## Context

Every POC data exchange is a Python pickle: live pose, capture results, batch outputs, imported pose files. Unpickling executes arbitrary code, which makes every pose file a potential payload — unacceptable for a project that will go public and accept community-shared pose files. The POC also globally monkeypatched `torch.load` to `weights_only=False`, the same risk class. The payload itself is small (~170 floats per frame: global orient, 21 body joints, 2x15 hand joints, jaw, betas, expression, translation), so serialization performance is not a forcing factor at 30 Hz.

## Decision

We will use JSON for all inter-process communication and persisted pose files: newline-delimited frames on the live stream, one JSON document per pose artifact, one JSON status file per batch job. Decoders validate against the schema in `contracts/` at the boundary; `core/` receives only typed, validated data. Pickle is banned for IPC and persistence repo-wide. Model weights load exclusively with `torch.load(..., weights_only=True)` from pinned revisions.

## Consequences

* Pose files are safe to share, human-readable, diffable, and language-agnostic; golden-fixture contract tests (GUIDELINES.md §9) become plain text.
* stdlib `json` on both interpreters — nothing to vendor into the extension wheel.
* JSON is larger and slower than binary formats — negligible at this payload size and rate, revisit only if profiling says so.
* POC-era `.pkl` pose files are not directly importable; a one-time legacy converter is a candidate Next-roadmap item, decided separately.

## Alternatives Considered

* Keep pickle — zero migration, full POC compatibility; rejected on arbitrary-code-execution risk alone.
* msgpack — compact and fast, but a third-party dependency that must be vendored into the extension wheel, and binary frames lose eyeball-debuggability.
* protobuf — schema rigor at the cost of codegen tooling; overkill for one small frame type exchanged on localhost.
