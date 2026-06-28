# Task 0004: Addon — extension skeleton and live stream client

**Status:** in progress
**Created:** 2026-06-11
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

The Blender-side half of the live slice. Threading model is the grounded happy path: stdlib-only daemon thread reads the TCP stream line-by-line (`socket.makefile('r')`), drains-before-puts into a latest-wins slot (POC `utils/serial_reader.py:42-49` — the POC's serial path pioneered the pattern; the serial feature itself is dropped from scope), and a `bpy.app.timers` callback applies on the main thread (official 4.2 LTS pattern; brecht-endorsed; POC `operators/serial_ops.py:7-59` already ran this model). The POC's modal-operator/mtime-polling model (`operators/pose.py:807-838`) is retired. The bpy adapter does only bone writes — all math comes from `core/` (task 0002). Armature reference validated every applied frame (spec R8 — POC threw 6,670 StructRNA errors). Extension bundles `contracts/`+`core/` wheels per ADR-0004. UI surfaces the lifecycle states from doc/workflows.md. HITL: interactive Blender verification on 4.2 and 5.x. Depends on tasks 0001-0003.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] Extension zip builds with vendored pure-Python wheels; installs via Blender's extension system on 4.2 LTS and a 5.x build.
- [ ] Start Stream spawns the engine by process handle, connects with bounded retry, and the UI passes Starting → Streaming; connect timeout lands in Stopped with a reported reason.
- [ ] Poses apply at the stream rate with stale frames dropped (latest-wins); per-limb filters and orientation fix work; existing keyframes untouched (automated count before/after).
- [ ] Deleting the armature mid-stream produces a warning state and no unhandled exception; selecting a valid target resumes without restart.
- [ ] Stop Stream terminates the engine by handle; no engine process remains after 5 seconds (process-listing check).
- [ ] Socket drop shows Reconnecting; engine death lands in Stopped with reason.
- [ ] Apply-time instrumentation logged at INFO on an interval to a rotating log; nothing above DEBUG per frame.
- [ ] Headless smoke test via `blender --background --python` exercises register/unregister and a simulated frame apply (`e2e` tag); addon disable does not raise (POC double-unregister bug regression check).

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [ ] `addon/` extension skeleton: `blender_manifest.toml` (wheels list), registration chain, preferences.
- [x] `addon/.../stream_client.py` — daemon thread, makefile line reader, typed decode via contracts, latest-wins slot.
- [ ] `addon/.../apply_timer.py` — bpy.app.timers callback: pop, validate armature ref, core policy → bone writes, redraw tag.
- [ ] `addon/.../engine_process.py` — spawn/terminate by handle (platform adapter, no shell=True).
- [ ] `addon/.../panels.py` + state property — lifecycle UI per workflows.md state machine.
- [ ] Extension build script vendoring wheels (`tools/build_extension.py`).
- [ ] Headless e2e smoke + manual verification matrix (4.2/5.x) recorded in Notes.
- [ ] Full gate + /ad-commit.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-06-28

Started the addon-side live stream client as the first task 0004 vertical slice after task 0003's engine stream close-out. Added `addon/posecap_addon/stream_client.py` with a daemon TCP reader thread, `socket.makefile("r")` line reads, contracts-level `decode_pose_frame()` validation at the boundary, bounded connect retry, explicit close/error reporting, and a single-slot latest-wins queue behind `latest()`. Added `addon/posecap_addon/__init__.py` and `py.typed` so the package has a registration entry point and pyright can type-check the addon source.

The first public client test starts a local TCP server, writes two schema-valid pose frames, and verifies `TcpPoseStreamClient.latest()` returns only the newest unconsumed frame before returning `None`. Verification passes: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, and `uv run pytest -q` (`93 passed, 1 deselected`).

Not claimed in this slice: Blender extension manifest/build, bpy timer application, engine process spawning, lifecycle UI, reconnect behavior, armature validation, keyframe preservation checks, or Blender 4.2/5.x HITL verification.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
