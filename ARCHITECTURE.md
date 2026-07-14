# Architecture

System-level patterns and boundaries. Pair with ADRs in `doc/adr/` for individual decisions; step-by-step functional flows are diagrammed in [`doc/workflows.md`](doc/workflows.md).

## Overview

PoseCap lets an animator drive a body model in Blender from live camera pose estimation while keeping camera selection, preview, recording, and retargeting in one workflow. Poses are pelvis-locked — monocular depth estimation cannot recover reliable world position, so world translation remains deferred. Without PoseCap, the workflow falls back to manual keyframing or external mocap suites. The system is a desktop pipeline: a Blender extension launches one selected, independently installed **Pose Backend** process and consumes its common pose stream. PEAR is the high-fidelity backend and requires the Windows NVIDIA/CUDA runtime; MediaPipe Lite is the CPU-first body-capture backend. Those are backend compatibility constraints, not system-wide dependencies. No server or database exists; the primary boundary is the local process boundary.

## Layers & Boundaries

Hexagonal (ports and adapters). Dependency rule: source code dependencies point inward only.

* `contracts/` — wire formats shared by all processes: pose payload schema, job status, and versioned Pose Backend manifests. Pure Python, stdlib only. Imports nothing from any other layer.
* `core/` — domain: pose model (SMPL-X parameter types), retarget/mapping logic, keyframe policy. Pure Python plus numpy. Defines ports (abstract interfaces) for pose streams, job queues, and clock/scheduling. Never imports `bpy`, `torch`, sockets, or filesystem APIs.
* `addon/` — Blender adapter: operators, panels, properties, handlers, the Pose Backend registry, TCP pose-stream client, and backend process launcher. Only layer that imports `bpy`. It validates static manifests and launches their commands but never imports backend packages. UI classes contain no domain logic — they call core through ports.
* `engine/` — Pose Backend adapters: common TCP pose-stream server, PEAR's external model-loading adapter, and MediaPipe Lite's isolated landmark adapter. PEAR alone imports `torch`/`ultralytics`/PEAR code; MediaPipe is imported lazily inside its own runtime. Upstream PEAR research code is not in this repo; the adapter imports it from a pinned external location. Each backend adapts native output before crossing the common stream boundary.

Crossing rule: the addon and selected Pose Backend communicate only through the startup event and `contracts/` wire formats over the transports below — never by importing each other. The operating-system suite installer advertises selected backend components through validated manifests in the PoseCap-owned registry; discovery never scans arbitrary directories or `PATH`.

## Patterns

* **IPC — live pose:** localhost TCP, newline-delimited JSON frames, engine is server, addon is client. Push-based; no disk polling, no mtime races. Transport sits behind a core port so it is swappable without touching domain code.
* **IPC — batch/single jobs:** file drop (images in, JSON pose files out) with a per-job JSON status file replacing the POC's `_progress.txt`/`_failed.txt` sidecars. Output written via temp file + `os.replace`.
* **Wire format:** JSON everywhere; pickle is banned for IPC (same deserialization risk class as `weights_only=False`, already banned in AGENTS.md).
* **Pose Backend discovery:** each backend owns its environment, dependencies, model cache, doctor, and license-specific setup. The suite's backend component handler atomically writes one versioned manifest containing an absolute launch command, protocol versions, capabilities, and compatibility facts. Invalid, ambiguous, or unavailable manifests are never executed.
* **Blender threading:** no `bpy` calls off the main thread. Background threads (the TCP client) produce into latest-wins single-slot queues; `bpy.app.timers` callbacks consume on the main thread. This is the only concurrency pattern in the addon.
* **Process lifecycle:** the selected backend is spawned and terminated by process handle/PID through a platform adapter — never `shell=True`, never taskkill-by-window-title. The backend self-terminates when the parent Blender PID dies.
* **Error handling:** domain errors defined in `core/`; the addon maps them to `Operator.report` + `{'CANCELLED'}` at the bpy edge; the engine logs them structured and reports failure through the job status file or stream close.
* **Validation:** contracts validate JSON and manifest schemas on decode; the addon additionally validates backend identity and executable readiness before launch. Core receives only typed, validated dataclasses and never re-validates.
* **Licensed assets:** each Pose Backend owns its assets and license setup. PEAR's SMPL-X/FLAME/MANO model files and weights resolve through configured local paths at runtime; nothing licensed ships in the repo or the extension wheel.

## Naming Conventions

* Packages and modules: `snake_case`. Ports named by role (`PoseStream`, `JobQueue`); adapters prefixed by technology (`tcp_pose_client`, `bpy_keyframe_writer`).

## Observability

* Logs: stdlib `logging`, one `RotatingFileHandler` per process (addon and engine), bounded size — replaces the POC's unbounded `modal_log.txt`. INFO for lifecycle, DEBUG for per-frame events (off by default).
* Metrics: none — single-user desktop tool. The engine logs inference FPS at INFO on an interval.
* Traces: none.

## Deployment Topology

Desktop, Windows-first for the implemented PEAR and MediaPipe Lite paths. Two deliverables establish the runtime boundary:

* Blender extension zip — built by a repo script that vendors `contracts/` and `core/` into the wheel (uv workspace is the single source of truth); installed through Blender's extension system, not directory junctions.
* Operating-system suite installer — always installs PoseCap Base and offers each implemented Pose Backend as an optional isolated component. The Windows installer offers MediaPipe Lite as the recommended account-free CPU component and PEAR as the NVIDIA/CUDA licensed-model component. Other operating systems reuse the manifest and installed-inventory contracts through native packaging surfaces rather than the Windows executable.

Platform-specific code (process spawn/kill, webcam enumeration) lives in adapter modules only; core and contracts are platform-neutral.
