# PoseCap

Real-time markerless motion capture for **Blender**: a webcam streams full-body SMPL-X poses straight onto your character. Built in collaboration with **Corridor Digital**.

Free and open source.

## Demo

Input video on the left; on the right, the SMPL-X body skeleton reconstructed frame-by-frame from the engine's live TCP stream (PEAR inference on an RTX 3080, 100% of frames tracked):

![Ale PoseCap Test](doc/media/posecap-live-capture.gif)

![Dance demo — video left, streamed skeleton right](doc/media/demo_dance.gif)

![Handstand demo — full inversion tracked](doc/media/demo_handstand.gif)

The clips are the repo's own test fixtures ([tests/fixtures/video/](tests/fixtures/video/SOURCES.json)), driven through the real pipeline with `posecap-engine live --source <video>` — the same deterministic path the automated GPU test suite uses. The skeleton viewer uses hand-approximated bone lengths; inside Blender the stream drives a real SMPL-X armature.

## Status

**Early development — first installable preview available.** Grab the Windows installer from the [latest release](https://github.com/CorridorTech/PoseCap/releases/latest); see the [PRD](doc/product/PRD.md) for scope and roadmap.

## What it is

Two components, one pipeline:

- **Blender extension** — panels and operators inside Blender: start/stop the live stream, record mocap to the timeline, capture single poses, manage SMPL-X body models.
- **Engine bridge** — a separate GPU process wrapping the [PEAR](https://github.com/Pixel-Talk/PEAR) pose-estimation model (single image in, SMPL-X parameters out, real-time rates). Streams poses to Blender over a local socket.

## Who it's for

Blender animators who want believable body animation without mocap suits, markers, or external mocap software. Corridor Digital's production artists are the founding users; if you have Blender, a webcam, and an NVIDIA GPU, it's for you too.

## Compatibility (current target)

| Component | Supported now |
|---|---|
| OS | Windows 10 / 11 |
| GPU | NVIDIA RTX 30 / 40 / 50 series (CUDA required — no CPU path) |
| Blender | 4.2 LTS minimum, 5.x supported |
| Python | 3.11 (Blender bundled for the extension; uv-managed venv for the engine bridge) |
| Camera | Any webcam, including virtual cameras (e.g. Iriun) |

RTX 20 series and older CUDA GPUs are untested and unsupported. Linux support for the engine bridge is on the roadmap; macOS is not currently planned.

## How it works

Two processes, joined by explicit contracts:

1. The engine bridge captures webcam frames, runs YOLO person detection plus PEAR's ViT-based mesh recovery on the GPU, and streams SMPL-X pose parameters as JSON over a localhost TCP socket.
2. The Blender extension consumes the stream on a background thread and applies poses on the main thread at up to 30 FPS — without wiping your existing keyframes.
3. Poses apply pelvis-locked: monocular depth estimation cannot recover trustworthy world position, so world translation stays out until a solid software approach lands (camera tracking is the leading candidate — see the roadmap).

Step-by-step diagrams for every flow (live streaming, capture jobs, install) live in [doc/workflows.md](doc/workflows.md); binding structure lives in [ARCHITECTURE.md](ARCHITECTURE.md).

## Body models and licensing

Two separate licenses apply — the plugin's and the body models':

- **PoseCap itself** is free and open source: GPL-3.0 for the Blender extension (required for Blender API linkage), Apache-2.0 for the contracts, core, and engine-bridge libraries — decided in [ADR-0006](doc/adr/0006-license-split-gpl-addon-apache-libraries.md).
- **The SMPL, SMPL-X, and FLAME body models** are licensed by the Max Planck Institute for research (non-commercial) use. They are **never distributed with PoseCap** — not in this repo, not in the installer. Each user registers on the official MPI sites and accepts the license terms personally; the plugin's setup wizard then automates the download using that user's own account credentials. The [illustrated setup guide](doc/guides/smplx-model-setup.md) walks through it.
- **Commercial production use of the body models** requires a commercial license from [Meshcapade](https://meshcapade.com), independent of the plugin itself being free.

## Roadmap

- **MVP** — live webcam streaming with device selection, record-live-mocap, timed capture, batch image processing, SMPL-X model management, Windows installers.
- **Next** — [Fast SAM 3D Body](https://github.com/yangtiming/Fast-SAM-3D-Body) engine adapter with MHR-to-SMPL conversion, AMASS animation import, FBX/Alembic export, Linux engine bridge.
- **Later** — world position via camera tracking, pose-accuracy eval harness, multi-camera estimation, retargeting to custom rigs, face/expression capture.

Full detail in the [PRD](doc/product/PRD.md).

## Project documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — layers, boundaries, IPC contracts
- [doc/workflows.md](doc/workflows.md) — sequence diagrams and flowcharts per functionality
- [AGENTS.md](AGENTS.md) — operational guide for contributors and coding agents
- [doc/product/PRD.md](doc/product/PRD.md) — product scope, metrics, roadmap
- [doc/reference/](doc/reference/README.md) — the papers and upstream projects this builds on

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — setup from clone to green tests, the project map, commit conventions, and the rules CI enforces. Short version: most of the codebase (`contracts/`, `core/`) needs no GPU and no Blender to work on; never commit model files or weights; one concern per signed-off commit.

## Acknowledgements

- **Dean / Corridor Digital** — concept and the production use case driving this
- **[PEAR](https://wujh2001.github.io/PEAR/)** (Wu et al., IDEA) — the pose-estimation backbone
- **[Fast SAM 3D Body](https://github.com/yangtiming/Fast-SAM-3D-Body)** (Yang et al.) — roadmap engine backend
- **[Meshcapade / MPI SMPL Blender addon](https://github.com/Meshcapade/SMPL_blender_addon)** — the addon lineage the POC started from
- **SMPL-X** body model by MPI for Intelligent Systems
