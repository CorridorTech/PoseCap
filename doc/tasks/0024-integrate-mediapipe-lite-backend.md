# Task `0024`: Integrate MediaPipe Lite backend

**Status:** done
**Created:** 2026-07-14
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0003-select-windows-backend-modules.md
**Board ref:**

## Context

PoseCap needs a useful camera-only capture path whose installation does not require
model-provider accounts, research-only body-model terms, or an NVIDIA GPU. This task
implements the accepted Lite decision in ADR-0008 as an isolated MediaPipe component
without changing the high-fidelity PEAR offer.

## Acceptance Criteria

- [x] The isolated component pins MediaPipe, its official Holistic task bundle, and
  the bundle SHA-256 without adding licensed body-model assets to the repository.
- [x] The Windows component installs an app-local CPU runtime and atomically
  registers a `body`-only Pose Backend manifest.
- [x] The addon starts Lite without a PEAR asset gate, applies only declared body
  bones, and bypasses the PEAR orientation correction.
- [x] A fixture-video stream emits schema-valid body frames and explicit no-person
  frames through the existing TCP JSON interface.
- [x] The source-preview lifecycle offers live frames and closes cleanly on stream
  teardown.
- [x] An installed isolated component streams the real fixture video over TCP.
- [x] A clean GUI-driven suite installation selects MediaPipe Lite, reaches the
  ready PoseCap panel, and exercises a live capture with the installed component.

## Plan

- [x] Convert canonical MediaPipe world landmarks into the existing body rotation
  contract in `core/src/posecap_core/landmark_pose.py`.
- [x] Add the isolated runtime and command entry point under
  `engine/src/posecap_engine/`.
- [x] Add the payload builder, component handler, suite selection, manifest, and
  installer rendering coverage under `packaging/` and `tools/`.
- [x] Cover body capability filtering, no-model onboarding, live streaming, preview
  teardown, and installed-component streaming with focused tests.
- [x] Run the clean GUI installation acceptance after this implementation slice is
  frozen, then record the observed result here.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-14

`ad-ground` combined the official Holistic Landmarker API and task-bundle guidance,
the MediaPipe implementation path, PoseCap's PEAR stream and preview conventions,
and the repository history for isolated installer components. The production boundary
is a `body` capability rather than an implied full-body-and-hands claim: the live
runtime maps 33 world landmarks to a canonical skeleton, retargets body rotations,
emits zero hand placeholders that are filtered before Blender application, and
preserves no-person frames.

`ad-tdd` added the preview lifecycle tracer before the implementation: two captured
frames are offered to the preview and the window is closed at teardown. The focused
MediaPipe, conversion, addon, packaging, and installed-component tests passed. The
clean GUI suite run remains the final acceptance criterion for this task.

The rebuilt `1.0.5-win.4` isolated component installed its app-local Python 3.11
runtime, all 19 pinned CPU dependencies, and the three PoseCap wheels. Its doctor
loaded the official task bundle successfully, the registered manifest reported
`capabilities: ["body"]`, and the installed launcher streamed the fixture video over
TCP. The suite installer then compiled with matching PEAR and MediaPipe `win.4`
payload manifests; the generated executable is
`packaging/dist/PoseCap_v1.0.5-win.4_Windows_Setup.exe` in ignored build output.

The complete local gate passed: ruff, format verification, Windows and Linux
pyright, import-linter, and `476 passed, 3 skipped, 10 deselected` under pytest.

The first two-axis review pass found a multi-backend blocker before delivery: the
registry correctly discovered PEAR and Lite but did not let the animator choose one.
The corrected panel persists `pose_backend_id` in the scene, exposes each ready
backend with compatibility facts, keeps Automatic behavior for a sole backend, and
requires an explicit choice only when multiple backends are ready. The final compiled
installer was rebuilt after that correction; its SHA-256 is
`b585b98c26b6e04948dc9a5bb45885944bf93dfb97723e89e3353b60e99ca786`.

A later rebuild removed the remaining implicit PEAR dependency by extracting
neutral live-source value objects. A subprocess test proves that importing the
MediaPipe adapter no longer imports `pear_adapter`. The model download is now pinned
to the official `float16/1` URL rather than its mutable `latest` alias; the verified
SHA-256 and byte size remain unchanged. A fresh component acceptance tree then
installed the rebuilt payload and passed doctor plus fixture-video streaming. The
recompiled installer SHA-256 is
`7ddb2a686ab8cef1a2303960c41c833070fa49e752a67f7a006240dcd96bc386`.

The final `ad-review` audit is
`.agentic/reviews/20260714T170941-working-tree-modular-backends.md`. It found no
remaining standards issue. Its sole specification concern is the deliberately open
clean GUI acceptance criterion; that criterion remains the release gate for this
task, rather than an unrecorded gap.

### 2026-07-17 — closed by registry hygiene verification

The open criterion — a clean GUI-driven suite installation reaching a ready
panel and exercising a live capture — is satisfied by the release
qualification recorded in task 0026 Notes (2026-07-14): from an empty
application-data root and an isolated Blender profile, the GUI installer
candidate installed MediaPipe Lite, the panel reached the ready state, and a
capture through the live streaming path visibly drove the converted Mixamo
armature at 17.74-23.00 FPS, with a screen recording retained. The public
`v1.0.6-win.3` release additionally passed the installed MediaPipe
integration test after an unauthenticated download (task 0026 Notes,
2026-07-15). That qualification drove the live path from the panel's video
source; the camera-specific GUI journey is tracked by task 0026's MediaPipe
criterion, not here. No orphan TODO or FIXME exists in the Python tree
(repository grep, 2026-07-17). Status flipped to done.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
