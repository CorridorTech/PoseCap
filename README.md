# CorridorRig

Real-time markerless motion capture for **Blender**: a webcam streams full-body SMPL-X poses onto your character while a physical encoder rig drives world position and rotation. Built in collaboration with **Corridor Digital**.

Free and open source.

## Status

**Early development — no releases yet.** See the [PRD](doc/product/PRD.md) for scope and roadmap.

## What it is

Three components, one pipeline:

- **Blender extension** — panels and operators inside Blender: start/stop the live stream, record mocap to the timeline, capture single poses, manage SMPL-X body models.
- **Engine bridge** — a separate GPU process wrapping the [PEAR](https://github.com/Pixel-Talk/PEAR) pose-estimation model (single image in, SMPL-X parameters out, real-time rates). Streams poses to Blender over a local socket.
- **Hardware rig firmware** *(optional)* — Arduino sketch reading 8 magnetic rotary encoders through an I2C multiplexer; drives world position/rotation of a target object over serial, layered on top of the AI body pose.

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
| Hardware rig *(optional)* | Arduino-compatible board + up to 8x AS5600 encoders + TCA9548A-class I2C multiplexer, USB serial |

RTX 20 series and older CUDA GPUs are untested and unsupported. Linux support for the engine bridge is on the roadmap; macOS is not currently planned.

## How it works

Two processes plus optional hardware, joined by explicit contracts:

1. The engine bridge captures webcam frames, runs YOLO person detection plus PEAR's ViT-based mesh recovery on the GPU, and streams SMPL-X pose parameters as JSON over a localhost TCP socket.
2. The Blender extension consumes the stream on a background thread and applies poses on the main thread at up to 30 FPS — without wiping your existing keyframes.
3. The encoder rig (if connected) sends channel values over serial; per-axis mapping with individual scalars drives the target object's world transform.

Binding structure lives in [ARCHITECTURE.md](ARCHITECTURE.md).

## Body models and licensing

SMPL-X body model files are **not included** and never will be — they are licensed by the Max Planck Institute (research) and [Meshcapade](https://meshcapade.com) (commercial). You download them yourself after accepting their terms; the plugin documents where to put them. Using the models in commercial production requires a commercial license from Meshcapade regardless of this plugin being free.

Plugin license: GPL-3.0 planned for the Blender extension (required for Blender API linkage); final split tracked in the [PRD open questions](doc/product/PRD.md).

## Roadmap

- **MVP** — full POC parity: live webcam streaming with device selection, record-live-mocap, timed capture, photo upload, batch folder processing, encoder rig input, SMPL-X model management, Windows installers.
- **Next** — [Fast SAM 3D Body](https://github.com/yangtiming/Fast-SAM-3D-Body) engine adapter with MHR-to-SMPL conversion, AMASS animation import, FBX/Alembic export, Linux engine bridge.
- **Later** — multi-camera estimation, retargeting to custom rigs, face/expression capture.

Full detail in the [PRD](doc/product/PRD.md).

## Project documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — layers, boundaries, IPC contracts
- [AGENTS.md](AGENTS.md) — operational guide for contributors and coding agents
- [doc/product/PRD.md](doc/product/PRD.md) — product scope, metrics, roadmap
- [doc/reference/](doc/reference/README.md) — the papers and upstream projects this builds on

## Contributing

Until a CONTRIBUTING.md lands: read [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md) first, open an issue before large changes, and never commit model files or weights — the gitignore and CI guard this, and license-clean history is a hard rule.

## Acknowledgements

- **Dean / Corridor Digital** — concept and the production use case driving this
- **[PEAR](https://wujh2001.github.io/PEAR/)** (Wu et al., IDEA) — the pose-estimation backbone
- **[Fast SAM 3D Body](https://github.com/yangtiming/Fast-SAM-3D-Body)** (Yang et al.) — roadmap engine backend
- **[Meshcapade / MPI SMPL Blender addon](https://github.com/Meshcapade/SMPL_blender_addon)** — the addon lineage the POC started from
- **SMPL-X** body model by MPI for Intelligent Systems
