# Spec `0002`: Select any installed Pose Backend

**Status:** shipped
**Created:** 2026-07-14
**Owner:** alexandremendoncaalvaro

## Context

PoseCap users must be free to choose a pose estimator according to its license,
account, operating-system, hardware, and capture characteristics without learning a
second workflow. Today the addon and engine name PEAR directly, so another backend
would either inherit PEAR's environment or add conditionals throughout the product.
That would make an optional choice capable of breaking every user's installation.

This feature makes independently installed Pose Backends discoverable and selectable
while preserving the current camera, preview, recording, target-armature, and live
stream behavior. It implements the Optional Pose Backends amendment in the product
PRD; the scientific integration of MediaPipe and MHR remains separate follow-up work.

## User Scenarios

- **Scenario 1: Continue using the existing PEAR installation**
  - Given PEAR is the only installed and ready Pose Backend
  - When the animator starts the live stream
  - Then PoseCap selects PEAR automatically and the existing command, stream, preview,
    and recording behavior remain unchanged

- **Scenario 2: Choose between independently installed backends**
  - Given two or three valid Pose Backend manifests are installed in any order
  - When the animator opens PoseCap
  - Then every installed backend appears once with its readiness and compatibility
    facts, and the animator can select one before starting the same live workflow

- **Scenario 3: Keep a working backend when another is unavailable**
  - Given one ready backend and one missing, malformed, or incompatible backend
  - When PoseCap discovers the registry
  - Then the ready backend remains usable and the unavailable backend is not executed
    and shows an actionable reason

- **Scenario 4: Remove one backend without affecting another**
  - Given multiple backends are installed
  - When one backend and its manifest are removed
  - Then the remaining backends retain their readiness, selection, and runtime files

## Requirements

### Functional

- PoseCap must discover versioned JSON manifests only from its configured registry
  directory.
- Each manifest must provide a unique stable identifier, display name, absolute launch
  command, supported PoseCap protocol versions, output capabilities, and compatibility
  facts covering license acceptance, account access, operating systems, and
  accelerators.
- Discovery must validate every manifest before exposing or executing it; one invalid
  manifest must not hide or disable valid manifests.
- Discovery order and duplicate handling must be deterministic across case-sensitive
  and case-insensitive filesystems.
- With one ready backend, PoseCap must select it automatically; with multiple ready
  backends, PoseCap must persist and reuse the user's selection while it remains ready.
- Starting a stream must launch only the selected backend through the existing process
  boundary and consume the existing startup event and TCP JSON stream.
- The current PEAR backend must be the first registered backend and must preserve its
  existing command arguments, settings, doctor, stream payload, and user workflow.
- A backend must run inside its own installed environment; PoseCap Base must not import
  backend-specific Python packages.
- Backend-specific output must be adapted to a declared PoseCap protocol version before
  crossing the process boundary; unavailable output channels must remain unavailable
  rather than fabricated.
- User-facing installation, selection, readiness, and recovery must remain GUI-driven;
  no animator workflow may require a terminal command.

### Non-functional

- Manifest discovery is an executable trust boundary: relative executable paths,
  unknown manifest versions, duplicate identifiers, and malformed field types must be
  rejected before process launch.
- Backend manifests and diagnostics must never contain credentials, access tokens, or
  licensed model data.
- Discovery and launch failures must be logged with backend identifier and manifest
  path without logging secrets.
- Existing latest-wins delivery, process cleanup, parent watchdog, and no-shell launch
  guarantees must remain intact.

## Success Criteria

- Automated tests install synthetic manifests for one, two, and three backends in
  every installation order and observe the same deterministic discovered set.
- Automated tests prove that a malformed or duplicate manifest cannot execute and
  cannot prevent a valid backend from being selected and launched.
- The PEAR tracer bullet produces the same launch command and decodable pose stream as
  the pre-registry path for camera and video sources.
- Pairwise install/remove acceptance tests leave each unaffected backend's manifest,
  doctor result, and launch command unchanged.
- Existing addon, contracts, core, engine, packaging, and governance tests remain
  green, including the Windows and Linux static-analysis gates.

## Edge Cases

- The registry directory is missing, empty, unreadable, or contains non-JSON files.
- Two files declare identifiers that differ only by letter case.
- A manifest is valid but its executable has been moved or removed.
- The selected backend becomes unavailable between discovery and stream start.
- The persisted selection references an uninstalled backend.
- A backend supports no PoseCap protocol version understood by the installed addon.
- A manifest path or executable path contains spaces or non-ASCII characters.
- One backend exits before announcing its TCP endpoint while another remains ready.

## Out of Scope

- Implementing MediaPipe or MHR inference and retargeting.
- Accepting a third-party license or creating a provider account on the user's behalf.
- Proving PEAR or MHR on AMD, Intel, macOS, or native Linux runtimes.
- Replacing TCP JSON, latest-wins delivery, SMPL-X target setup, or recording behavior.
- Opening an unrestricted third-party plugin marketplace.

## Open Questions

- None. ADR-0010 owns the binding discovery and process-isolation decision; backend-
  specific protocol extensions belong to their own specs and ADRs.

## Related

- PRD: [Optional Pose Backends amendment](../product/PRD.md#amendment--optional-pose-backends)
- Domain: [`Pose Backend`](../../CONTEXT.md#pose-backend)
- ADRs: [ADR-0001](../adr/0001-adopt-hexagonal-architecture.md),
  [ADR-0002](../adr/0002-tcp-json-stream-live-pose.md),
  [ADR-0003](../adr/0003-json-wire-format-ban-pickle.md),
  [ADR-0010](../adr/0010-discover-isolated-pose-backends.md)
- Tasks: [Task 0020 — Register PEAR as a Pose Backend](../tasks/0020-register-pear-pose-backend.md),
  [Task 0021 — Reconcile optional backend architecture](../tasks/0021-reconcile-optional-backend-architecture.md)
- Depends on: [Spec 0001](0001-live-webcam-pose-streaming.md)
