# Architecture

System-level patterns and boundaries. Pair with ADRs in `doc/adr/` for individual decisions; step-by-step functional flows are diagrammed in [`doc/workflows.md`](doc/workflows.md).

## Overview

PoseCap lets an animator drive an SMPL-X body model in Blender from live webcam pose estimation (PEAR engine, CUDA). Poses are pelvis-locked — monocular depth estimation cannot recover reliable world position, so world translation is an open problem deferred to the roadmap. Without PoseCap, the mocap workflow falls back to manual keyframing or external mocap suites. The system is a desktop pipeline on one Windows machine: a Blender extension (runs in Blender's bundled Python) and an engine bridge process (uv-managed venv, owns PyTorch/PEAR). No server, no database; the boundary is a process boundary.

## Layers & Boundaries

Hexagonal (ports and adapters). Dependency rule: source code dependencies point inward only.

* `contracts/` — wire formats shared by all processes: pose payload schema, job status. Pure Python, stdlib only. Imports nothing from any other layer.
* `core/` — domain: pose model (SMPL-X parameter types), retarget/mapping logic, keyframe policy. Pure Python plus numpy. Defines ports (abstract interfaces) for pose streams, job queues, and clock/scheduling. Never imports `bpy`, `torch`, sockets, or filesystem APIs.
* `addon/` — Blender adapter: operators, panels, properties, handlers, plus driven adapters (TCP pose-stream client, engine process launcher). Only layer that imports `bpy`. UI classes contain no domain logic — they call core through ports.
* `engine/` — PEAR bridge: model loading, inference loop, webcam capture, TCP pose-stream server, batch folder worker. Only layer that imports `torch`/`ultralytics`/PEAR code. Upstream PEAR research code is not in this repo; the bridge imports it from a pinned external location.

Crossing rule: addon and engine communicate only through `contracts/` wire formats over the transports below — never by importing each other.

## Patterns

* **IPC — live pose:** localhost TCP, newline-delimited JSON frames, engine is server, addon is client. Push-based; no disk polling, no mtime races. Transport sits behind a core port so it is swappable without touching domain code.
* **IPC — batch/single jobs:** file drop (images in, JSON pose files out) with a per-job JSON status file replacing the POC's `_progress.txt`/`_failed.txt` sidecars. Output written via temp file + `os.replace`.
* **Wire format:** JSON everywhere; pickle is banned for IPC (same deserialization risk class as `weights_only=False`, already banned in AGENTS.md).
* **Blender threading:** no `bpy` calls off the main thread. Background threads (the TCP client) produce into latest-wins single-slot queues; `bpy.app.timers` callbacks consume on the main thread. This is the only concurrency pattern in the addon.
* **Process lifecycle:** engine spawned and terminated by process handle/PID through a platform adapter — never `shell=True`, never taskkill-by-window-title. Engine self-terminates when the parent Blender PID dies.
* **Error handling:** domain errors defined in `core/`; the addon maps them to `Operator.report` + `{'CANCELLED'}` at the bpy edge; the engine logs them structured and reports failure through the job status file or stream close.
* **Validation:** contracts validate on decode (schema check at the boundary); core receives only typed, validated dataclasses and never re-validates.
* **Licensed assets:** SMPL-X/FLAME/MANO model files and engine weights resolve through configured local paths at runtime; nothing licensed ships in the repo or the extension wheel.

## Naming Conventions

* Packages and modules: `snake_case`. Ports named by role (`PoseStream`, `JobQueue`); adapters prefixed by technology (`tcp_pose_client`, `bpy_keyframe_writer`).

## Observability

* Logs: stdlib `logging`, one `RotatingFileHandler` per process (addon and engine), bounded size — replaces the POC's unbounded `modal_log.txt`. INFO for lifecycle, DEBUG for per-frame events (off by default).
* Metrics: none — single-user desktop tool. The engine logs inference FPS at INFO on an interval.
* Traces: none.

## Deployment Topology

Desktop, Windows-first. Two artifacts:

* Blender extension zip — built by a repo script that vendors `contracts/` and `core/` into the wheel (uv workspace is the single source of truth); installed through Blender's extension system, not directory junctions.
* Engine bridge — `uv sync` in the repo; launched by the addon or standalone for batch work.

Platform-specific code (process spawn/kill, webcam enumeration) lives in adapter modules only; core and contracts are platform-neutral.
