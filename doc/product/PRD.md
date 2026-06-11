# PRD — CorridorRig

Status: draft
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

* Full POC feature parity with zero reproduced POC bugs: live webcam streaming, record-live-mocap, single timed capture, photo upload, batch folder processing, Arduino rig input with per-axis mapping, SMPL-X model and shape management, pose import.
* Live mocap performance: pose applied in the viewport at 30 FPS with under 100 ms capture-to-viewport latency on an RTX-class GPU.
* Clean-machine setup completes in one documented installer pass in 15 minutes or less, including environment build.
* License-clean repository from the first commit: no model files or weights ever in git history, so the repo can go public without history rewrite; addon code GPL-compatible; rewrite carries no code from the GPL POC fork.
* Codebase a community contributor can enter: hexagonal layers per ARCHITECTURE.md, domain logic testable without Blender or a GPU, quality gates green on main.

## Non-goals

* Multi-camera estimation — research-grade, deferred (see Roadmap: Later).
* Fast-SAM-3D-Body / MHR backend — second engine adapter, not part of parity (see Roadmap: Next).
* Face, jaw, and expression capture — POC had it disabled; stays out until body capture is solid.
* Retargeting to arbitrary or Rigify rigs — SMPL-X armature is the only target for now.
* Linux and macOS support in the MVP — Windows-first; platform adapters keep the door open.
* Redistributing SMPL-X/FLAME/MANO model files or PEAR weights — never, in any release form.
* Mobile or browser capture sources.

## Success Metrics

* Sustained 30 FPS pose application with capture-to-viewport latency under 100 ms on an RTX-class GPU — measured by instrumented timestamps logged by the engine bridge and addon (frame-stamped log comparison).
* Parity checklist (derived from POC registered operators plus feature_updates.md) passes 100% — measured by the MVP spec acceptance criteria.
* Clean-machine install test: one installer pass, 15 minutes or less, no manual file copying — measured by a documented install run on a machine without dev tooling.
* At least one external (non-founder) contributor PR merged within 90 days of the public repo announcement — measured on GitHub.
* Zero licensed binaries in git history at every release — measured by a repository scan in CI.

## Roadmap

MVP — full POC parity, one vertical architecture:

* Live webcam streaming with explicit device selection — engine bridge, TCP pose stream, addon applies pose without touching existing keyframes.
* Record Live MoCap — timeline-synced keyframe recording with clear start/stop, keyframes persist across stream restarts.
* Single timed capture and photo upload — file-drop job with progress and failure reporting.
* Batch folder processing — drop a folder of images, get pose files out.
* Arduino encoder rig input — 8-channel read, per-axis channel mapping, per-axis scalars, stabilized rotation, no face/jaw channels.
* SMPL-X model management — add body model, shape from betas and measurements, pose import, keyframe manager.
* Windows installers — environment build and extension install via Blender's extension system.

Next:

* Public release — repo goes public, contribution docs land, backend and licensing verified for announcement.
* Fast-SAM-3D-Body engine adapter, including the MHR-to-SMPL feedforward conversion (Dean's open problem; upstream is MIT).
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
* PEAR upstream license terms (code at Pixel-Talk/PEAR and weights at BestWJH/PEAR_models) — verify redistribution and commercial-use terms before the public announcement names PEAR as the backend.
* Commercial SMPL-X (Meshcapade) license for Corridor's production use — who obtains it and when.
* Repository home for the public repo — Corridor org, Dean's account, or Ale's account.
* Go-public criteria — what gates the flip from private to public (MVP parity done? CI green? PEAR license verified? contribution docs ready?).
* Parity checklist canonical source — first MVP spec must enumerate it from the POC's registered operators, not its README (README advertises dead features).

## Related

* AGENTS.md — operational guide; stack and licensing posture.
* ARCHITECTURE.md — binding layer structure the roadmap items implement.
* doc/reference/README.md — PEAR and Fast-SAM-3D-Body papers, upstream addon lineage.
* ADRs: none yet; five candidates flagged in the architecture pass plus the license split above.
