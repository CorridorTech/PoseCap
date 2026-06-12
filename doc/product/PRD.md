# PRD — CorridorRig

Status: accepted
Created: 2026-06-11
Updated: 2026-06-11
Owner: alexandremendoncaalvaro

## Product

CorridorRig is a free, open-source Blender plugin that gives animators real-time markerless motion capture from a webcam (PEAR pose estimation) combined with a physical Arduino encoder rig for world position and rotation. It is the clean-architecture rewrite of Dean's (Corridor Digital) proof of concept, developed privately by Ale and Dean for now, with a public open-source release once the MVP is solid.

## Target User

Primary: Blender animators who need fast, cheap body mocap without suits, markers, or external mocap software — Corridor Digital's production artists are the founding instance of this user.

## Personas

* Production artist (Dean and Corridor team): uses it on real shoots; cares about reliability, keyframe safety, and setup speed on a new machine.
* Indie Blender animator: installs from a public release; cares about a working out-of-the-box experience on consumer NVIDIA hardware.
* Community contributor: developer extending the codebase; cares about layered architecture, tests, and contribution docs.

## Problem

Today, a Blender animator who wants believable body animation must hand-keyframe it, buy a mocap suit, or round-trip through external mocap software. Dean's POC proved a webcam plus a consumer GPU can stream SMPL-X poses straight onto a Blender rig in real time — but the POC is unmaintainable vibe-coded glue: no tests, copy-pasted pipelines, Windows hacks inline everywhere, known data-loss bugs (keyframe wipes on stream restart), and license-encumbered lineage. Without this rewrite, the capability dies with the prototype.

## Goals

* Parity with the POC's verified-working feature set (canonical list: [doc/reference/poc-verification.md](../reference/poc-verification.md)) with zero reproduced POC bugs: live webcam streaming, record-live-mocap, single timed capture, batch image processing, Arduino rig input with per-axis mapping, SMPL-X model spawn, pose import, keyframe management.
* Live mocap performance: pose applied in the viewport at 30 FPS with under 100 ms capture-to-viewport latency on an RTX-class GPU.
* Clean-machine setup completes in one documented installer pass in 15 minutes or less, including environment build.
* License-clean repository from the first commit: no model files or weights ever in git history, so the repo can go public without history rewrite; addon code GPL-compatible; rewrite carries no code from the GPL POC fork.
* Codebase a community contributor can enter: hexagonal layers per ARCHITECTURE.md, domain logic testable without Blender or a GPU, quality gates green on main.

## Non-goals

* Multi-camera estimation — research-grade, deferred (see Roadmap: Later).
* Fast-SAM-3D-Body / MHR backend — second engine adapter, not part of parity (see Roadmap: Next).
* Face, jaw, and expression capture — POC had it deliberately disabled; stays out until body capture is solid.
* SMPL+H body model — the POC's asset never existed; SMPL-X only.
* Retargeting to arbitrary or Rigify rigs — SMPL-X armature is the only target for now.
* Linux and macOS support in the MVP — Windows-first; platform adapters keep the door open.
* Redistributing SMPL-X/FLAME/MANO model files or PEAR weights — never, in any release form.
* Mobile or browser capture sources.

## Success Metrics

* Sustained 30 FPS pose application with capture-to-viewport latency under 100 ms on an RTX-class GPU — measured by instrumented timestamps logged by the engine bridge and addon (frame-stamped log comparison).
* Parity checklist (derived from the verified-working and code-complete tiers of [doc/reference/poc-verification.md](../reference/poc-verification.md)) passes 100% — measured by the MVP spec acceptance criteria.
* Clean-machine install test: one installer pass, 15 minutes or less, no manual file copying — measured by a documented install run on a machine without dev tooling.
* At least one external (non-founder) contributor PR merged within 90 days of the public repo announcement — measured on GitHub.
* Zero licensed binaries in git history at every release — measured by a repository scan in CI.
* Pose-accuracy regressions caught before release: once the eval-harness baseline exists, every backend or weight-pin change is scored against the golden-sample baseline and regressions beyond the recorded threshold block the change — measured by eval run logs.

## Roadmap

MVP — parity with the POC's verified-working set, one vertical architecture:

* Live webcam streaming with device selection — engine bridge, TCP pose stream, addon applies pose without touching existing keyframes; stream survives armature deletion/replacement (POC's biggest live failure mode).
* Record Live MoCap — timeline-synced keyframe recording with clear start/stop, independent of any preview toggle (POC trap), keyframes persist across stream restarts.
* Single timed capture — countdown, capture-to-pose with progress and failure reporting.
* Batch image processing — select images in Blender, get poses applied; file-drop job under the hood.
* Arduino encoder rig input — 8-channel read, per-axis channel mapping, per-axis scalars, stabilized rotation, no face/jaw channels. Code-complete in POC but never hardware-proven: first hardware validation happens here.
* SMPL-X model spawn (v1.1 neutral), pose import with per-limb filters and orientation fix, keyframe manager.
* Windows installers — environment build and extension install via Blender's extension system. The POC's documented install path was never proven (Dean ran a conda env); this one ships tested.

Next:

* Public release — repo goes public, contribution docs land, backend and licensing verified for announcement.
* Photo upload (single image) and standalone folder watcher — built in the POC but never successfully exercised; same job pipeline as batch.
* Shape editing UI (measurements-to-betas, randomize/reset) — orphaned operators in the POC, never reachable.
* Pose-accuracy eval harness — golden samples scored with metric-and-tolerance comparison; baseline-relative regression gate for backend swaps and PEAR pin bumps. The harness is built via spike once the engine CLI exists, but golden-sample acquisition starts immediately in parallel with MVP development: synthetic renders have zero code dependency (they land as task 0003 fixture inputs), and the Corridor capture session — gated on what hardware Dean confirms — is coordinated directly with Dean outside the task tracker. Prerequisite for objective backend comparison.
* Fast-SAM-3D-Body engine adapter, including the MHR-to-SMPL feedforward conversion (Dean's open problem; upstream is MIT). The eval harness above is the tool this work is measured with.
* Animation import (.npz AMASS) and FBX/Alembic export — advertised by the POC README but dead code in the POC.
* Linux support for the engine bridge.

Later:

* Multi-camera estimation (Fast-SAM-3D-Body multi-view fusion).
* Retargeting to custom and Rigify rigs.
* Face and expression capture.

## Constraints

* SMPL-X model files are MPI research-licensed: users obtain them directly from MPI/Meshcapade after accepting terms; the product only documents expected local paths. Commercial production use of the models (including Corridor's own) requires a Meshcapade commercial license — independent of the plugin's own license.
* Addon code links Blender's Python API and must be GPL-compatible; plan is GPL-3.0 for the addon.
* Repository is private during early development but must stay publishable at all times: git history is permanent, so licensed binaries and secrets are blocked by gitignore and CI scan from the first commit, never cleaned up after the fact.
* Runtime requires an NVIDIA CUDA GPU; CPU-only operation is out of scope (PEAR inference is CUDA-bound).
* Blender 4.2 LTS minimum, per AGENTS.md.

## Open Questions

* License split: single GPL-3.0 for the whole repo, or GPL-3.0 addon plus MIT/Apache-2.0 for contracts/core/engine bridge? One ADR decides; affects how reusable the bridge is outside Blender.

  Resolved: [ADR-0006](../adr/0006-license-split-gpl-addon-apache-libraries.md) (accepted) — GPL-3.0 for the addon, Apache-2.0 for contracts, core, engine bridge, and firmware. LICENSE files land with the scaffold.
* PEAR upstream license terms (code at Pixel-Talk/PEAR and weights at BestWJH/PEAR_models) — verify redistribution and commercial-use terms before the public announcement names PEAR as the backend.
* Commercial SMPL-X (Meshcapade) license for Corridor's production use — who obtains it and when.
* Repository home for the public repo — Corridor org, Dean's account, or Ale's account.
* Eval-harness design: metric set (MPJPE, PA-MPJPE, joint-angle error, temporal jitter/acceleration) and regression threshold — decided in the eval spike after the engine CLI lands (task 0003). Ground-truth data must be self-made; research datasets (AMASS, 3DPW) are license-restricted and never enter the repo. Ground-truth tiers: synthetic renders (perfect answer key), suit-plus-webcam session (high-quality real-world reference — suit-to-SMPL-X mapping adds its own error), footage-only (qualitative and no-reference jitter checks only — no true values without a reference system). Acquisition runs in parallel with MVP work; the Corridor session is coordinated directly with Dean.
* Go-public criteria — what gates the flip from private to public (MVP parity done? CI green? PEAR license verified? contribution docs ready?).
* Parity checklist canonical source — first MVP spec must enumerate it from the POC's registered operators, not its README (README advertises dead features).

  Resolved: the canonical source is [doc/reference/poc-verification.md](../reference/poc-verification.md), an evidence-based audit (artifact forensics + registration tracing) separating verified-working, code-complete-unproven, broken, and dead features. MVP parity scopes to the first two tiers.

## Related

* AGENTS.md — operational guide; stack and licensing posture.
* ARCHITECTURE.md — binding layer structure the roadmap items implement.
* doc/reference/README.md — PEAR and Fast-SAM-3D-Body papers, upstream addon lineage.
* ADRs: none yet; five candidates flagged in the architecture pass plus the license split above.
