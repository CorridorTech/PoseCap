# Task `0020`: Register PEAR as a Pose Backend

**Status:** done
**Created:** 2026-07-14
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0002-select-installed-pose-backend.md
**Board ref:**

## Context

PoseCap cannot add independently licensed and provisioned estimators while PEAR is
hardcoded into the addon command builder. This tracer bullet must put the existing
PEAR installation behind the manifest-discovered Pose Backend seam without changing
what an animator sees or what command and pose stream PEAR produces. It proves the
modular boundary before MediaPipe or MHR adds new scientific behavior.

## Acceptance Criteria

- [x] A valid PEAR manifest discovered from the configured PoseCap registry exposes
  one ready Pose Backend with its stable identifier, display name, protocol version,
  capabilities, compatibility facts, and launch command.
- [x] One malformed, unsupported, duplicate, or relative-executable manifest is
  reported unavailable without hiding or executing a valid PEAR manifest.
- [x] Selecting the registered PEAR backend produces the same live command arguments
  as the current camera and video launch paths.
- [x] With PEAR as the only ready backend, selection is automatic and the existing
  startup event, TCP stream, latest-wins consumption, preview, and recording tests
  remain green.
- [x] The registry and PEAR tracer tests pass on Windows and under the Linux static-
  analysis platform without importing PEAR or any backend-specific dependency into
  contracts or core.

## Plan

- [x] Record the `ad-tdg` ground-truth pair, Test Dependency Map, candidate strategies,
  and single-criterion selection in Notes.
- [x] Add one public-interface tracer test for valid PEAR manifest discovery and run it
  RED before implementing the minimum registry behavior.
- [x] Add validation and duplicate-isolation behaviors one failing test at a time.
- [x] Route the existing PEAR command through the selected backend and prove camera and
  video command parity through addon tests.
- [x] Refactor only after the focused registry, engine-process, UI-state, CLI, and
  contract tests are green.
- [x] Run the full local quality gate and complete a two-axis `ad-review` audit trail.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-14 — `ad-tdg` strategy selection

**Ground-truth pair:** given a registry containing one valid PEAR manifest, discovery
returns exactly one ready backend selected as `pear`, and its launch command preserves
the current PEAR executable and `live --pear-root` prefix. The existing command path
is the negative/control case: no registry behavior may import or execute PEAR while
cataloguing manifests.

**Test Dependency Map:** the tracer enters through a new public addon registry API,
uses a stdlib-only manifest decoder owned by `posecap_contracts`, and exits as a
catalogue of ready backends plus isolated issues. Command integration then enters
through `panels._engine_command`; existing guards remain
`tests/addon/test_ui_state.py`, `tests/addon/test_engine_process.py`,
`tests/engine/test_cli.py`, and `tests/contracts/test_pose_frame_codec.py`. Baseline:
111 tests passed in 1.72 seconds.

**Approaches considered:**

1. Keep schema parsing and discovery entirely in the addon. This is locally simple,
   but makes the installer duplicate the wire definition.
2. Put the immutable manifest and decoder in `contracts`, with filesystem discovery
   and selection in the addon. This keeps one stdlib-only schema and makes behavior
   testable without Blender, GPU, PEAR, or installer execution.
3. Make the engine expose a catalogue command. This creates a bootstrap dependency on
   the very runtime being selected and couples discovery to one backend environment.

**Single criterion:** testability at the license and process boundary. Approach 2 is
selected because it proves discovery and failure isolation through public interfaces
without loading backend code, while retaining one contract for future installers.

### 2026-07-14 — `ad-tdd` and verification closeout

The tracer ran RED then GREEN through the public addon package: the installer writes
an atomic PEAR manifest, the addon discovers and auto-selects it, and camera and video
commands remain byte-for-byte equivalent to the legacy builder. Invalid JSON, unknown
schema, relative or missing executables, case-insensitive duplicate identifiers, and
an unreadable registry remain observable without executing backend code. A present but
invalid registry cannot silently fall back to an unregistered runtime; the legacy
fallback exists only when no registry has been installed yet.

Compatibility now records operating systems, accelerators, account requirement, and
license terms. The manifest contract stays stdlib-only and the addon package exports
the registry API. No backend dependency, licensed asset, credential, or token entered
the repository.

Verification evidence: ruff check and format, pyright Windows and Linux, import-linter,
Markdown links, and `git diff --check` all passed. The full default pytest gate passed
with 413 tests and 9 expected marker exclusions. `ad-architecture` audit found the
existing PEAR-only overview stale; Task 0021 records that binding-doc reconciliation
after ADR-0010 acceptance. The `ad-review` audit trail is ignored at
`.agentic/reviews/20260714T000000Z-working-tree.md`.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
