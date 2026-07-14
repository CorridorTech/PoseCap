# ADR-0011: Use one modular suite installer

**Status:** accepted
**Date:** 2026-07-14
**Deciders:** alexandremendoncaalvaro

## Context

PoseCap must let an animator install MediaPipe, PEAR, MHR, or any combination
without asking them to understand separate packaging products. Separate visible
installers would preserve runtime isolation but multiply setup, repair, update, and
support workflows. A single shared Python environment would simplify the installer
surface but recreate the dependency and license coupling that ADR-0010 rejects.

The CorridorKey Runtime provides the proven local reference: one Windows suite
installer presents a fixed base plus optional components, downloads only selected
payloads, writes installed inventory, and owns repair, deselection, and cleanup while
shared assets remain deduplicated. Inno Setup directly supports setup types,
selectable components, component-bound files and actions, and verified downloads.

## Decision

We will provide one PoseCap suite installer per operating system. The installer will
always install PoseCap Base and will expose each implemented Pose Backend as an
optional component. The suite is the user-facing orchestrator; it does not merge
backend runtimes. Each backend component will retain its own environment,
dependencies, model cache, doctor, compatibility requirements, and manifest under
the PoseCap-owned backend registry.

On Windows, the suite will use Inno Setup with online-first, checksum-verified
payloads. It will write an installed-component inventory and will own install,
repair, explicit deselection, and uninstall cleanup for every component. PoseCap
Base will never perform NVIDIA, provider-account, or backend-model checks. Those
checks belong only to the selected backend component. Credentials and access tokens
will never enter the installer inventory or backend manifests.

The first implementation slice will make the current PEAR runtime optional behind
the fixed Base component without changing PEAR's validated runtime. MediaPipe and MHR
will be added only after this lifecycle is proven. Other operating systems will reuse
the component, inventory, and manifest contracts through their native packaging
surface rather than attempting to run the Windows installer.

## Consequences

* Users get one setup, repair, update, and uninstall surface while retaining any one,
  two, or three Pose Backends in any installation order.
* Unselected backends do not impose downloads, hardware checks, accounts, or license
  setup on the user.
* Runtime isolation from ADR-0010 remains intact because the suite coordinates
  components rather than sharing their environments.
* Installed inventory becomes product state and must remain accurate across upgrades,
  failed component installs, deselection, and repair.
* Deselecting an already installed component requires explicit cleanup; Inno Setup
  component selection alone is insufficient.
* Windows and Linux can share the same backend contract but require distinct native
  installer implementations.
* The installer becomes more sophisticated than the current monolithic PEAR
  bootstrap and needs generated-script, lifecycle, and clean-machine coverage.

## Alternatives Considered

* One visible installer per backend — rejected because users would manage multiple
  setup, repair, and uninstall products for one PoseCap workflow.
* One universal environment containing every backend — rejected because dependency,
  download, hardware, account, and license requirements would become global again.
* Keep the current PEAR-only monolithic installer — rejected because Base would remain
  coupled to NVIDIA and no account-free backend could be installed independently.
* Make backend installation terminal-driven — rejected because animator setup must
  remain GUI-driven and supportable.
