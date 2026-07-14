# ADR-0010: Discover isolated Pose Backends by manifest

**Status:** accepted
**Date:** 2026-07-14
**Deciders:** alexandremendoncaalvaro

## Context

PoseCap must let an animator install MediaPipe, PEAR, MHR, or any combination in any
order without changing the camera-to-Blender workflow. The choices are not editions
of the product: each is a **Pose Backend** with different model access, license,
operating-system, accelerator, latency, and output-channel characteristics.

The current architecture already has the correct runtime seam. The addon launches an
external process, reads its announced TCP endpoint, and consumes latest-wins JSON pose
frames through `PoseStream`. However, the addon command builder and engine frame-source
factory name PEAR directly. Adding more conditionals there would couple every release
of the PoseCap Base to every optional backend.

MediaPipe, PEAR, and MHR cannot safely share one Python environment. The tested PEAR
and MHR paths require different PyTorch stacks, while MediaPipe provides the intended
CPU and cross-platform path. uv workspaces deliberately share a lockfile and virtual
environment and are not suitable for members with conflicting requirements. Python
entry-point discovery has the same problem because it sees packages in the current
environment. Jupyter kernel specs provide the closer proven shape: a small manifest
advertises an independently installed executable and metadata while the frontend
keeps one interaction protocol.

## Decision

We will discover optional Pose Backends from versioned JSON manifests in a
PoseCap-owned registry directory. Each validated manifest will provide a stable
backend identifier, display name, absolute launch command, supported PoseCap protocol
versions, declared output capabilities, and user-facing compatibility facts for
license acceptance, account access, operating systems, and accelerators.

Each backend will own its Python environment, dependencies, model cache, doctor, and
license-specific setup. The PoseCap Base will never import a backend's Python package.
It will select one installed manifest, launch that command through the existing
process boundary, and consume the existing startup event and TCP JSON stream. The
backend must adapt its native estimator output to a PoseCap protocol version before it
crosses the process boundary; unsupported channels remain explicitly unavailable.

The installer will own manifest installation and removal. Discovery will be limited
to the PoseCap registry rather than arbitrary working directories or `PATH`. Manifests
will be schema-validated, identifiers will be unique, executable paths will be
absolute, and an invalid manifest will be reported as unavailable rather than
executed. The current PEAR runtime will be registered first as a tracer bullet with
no change to its live behavior, settings, or output.

## Consequences

* Any one, two, or all three backends can be installed in any order because their
  dependency environments and model assets never merge.
* Camera selection, preview, recording, latest-wins delivery, and target-armature
  behavior remain PoseCap features rather than backend-specific workflows.
* The UI can explain requirements before installation and show only readiness states
  supported by a backend manifest plus its doctor result.
* MediaPipe can establish Windows and Linux CPU support without weakening PEAR or MHR;
  Linux NVIDIA and future AMD investigations remain backend-specific evidence.
* A backend can retain additional body, hand, face, shape, or mesh channels when a
  supported protocol version represents them; absent channels are not fabricated.
* Installers must update manifests atomically with their backend runtime and remove
  stale manifests on uninstall.
* A manifest is an executable trust boundary. Keeping discovery in an app-owned
  directory and rejecting invalid paths is mandatory; arbitrary third-party manifest
  installation is not implied by this decision.
* The first slice adds indirection around PEAR without immediate user-visible value,
  but proves backwards compatibility before MediaPipe changes the runtime matrix.

## Alternatives Considered

* Add MediaPipe and MHR conditionals to the existing addon and engine CLI — rejected
  because the PoseCap Base would know every backend and optional installation would
  still share dependency pressure.
* Discover Python packages through entry points — rejected because discovery and load
  occur in one Python environment, conflicting with backend isolation.
* Add all backends as uv workspace members or extras — rejected because one shared
  lockfile and environment cannot represent the independently tested runtime stacks.
* Search `PATH` or arbitrary directories for backend executables — rejected because
  selection would be nondeterministic and expand the executable trust boundary.
* Ship one universal environment containing every backend — rejected because users
  would download and accept requirements for backends they deliberately did not
  choose, and one dependency conflict could break every capture path.
