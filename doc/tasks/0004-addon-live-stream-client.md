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

- [x] Extension zip builds with vendored pure-Python wheels; installs via Blender's extension system on 4.2 LTS and a 5.x build.
- [x] Start Stream spawns the engine by process handle, connects with bounded retry, and the UI passes Starting → Streaming; connect timeout lands in Stopped with a reported reason.
- [x] Poses apply at the stream rate with stale frames dropped (latest-wins); per-limb filters and orientation fix work; existing keyframes untouched (automated count before/after).
- [x] Deleting the armature mid-stream produces a warning state and no unhandled exception; selecting a valid target resumes without restart.
- [x] Stop Stream terminates the engine by handle; no engine process remains after 5 seconds (process-listing check).
- [x] Socket drop shows Reconnecting; engine death lands in Stopped with reason.
- [x] Apply-time instrumentation logged at INFO on an interval to a rotating log; nothing above DEBUG per frame.
- [x] Headless smoke test via `blender --background --python` exercises register/unregister and a simulated frame apply (`e2e` tag); addon disable does not raise (POC double-unregister bug regression check).

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] `addon/` extension skeleton: `blender_manifest.toml` (wheels list), registration chain, preferences.
- [x] `addon/.../stream_client.py` — daemon thread, makefile line reader, typed decode via contracts, latest-wins slot.
- [x] `addon/.../apply_timer.py` — bpy.app.timers callback: pop, validate armature ref, core policy → bone writes, redraw tag.
- [x] `addon/.../engine_process.py` — spawn/terminate by handle (platform adapter, no shell=True).
- [x] `addon/.../panels.py` + state property — lifecycle UI per workflows.md state machine.
- [x] Extension build script vendoring wheels (`tools/build_extension.py`).
- [ ] Headless e2e smoke + manual verification matrix (4.2/5.x) recorded in Notes.
- [ ] Full gate + /ad-commit.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-06-28

Started the addon-side live stream client as the first task 0004 vertical slice after task 0003's engine stream close-out. Added `addon/posecap_addon/stream_client.py` with a daemon TCP reader thread, `socket.makefile("r")` line reads, contracts-level `decode_pose_frame()` validation at the boundary, bounded connect retry, explicit close/error reporting, and a single-slot latest-wins queue behind `latest()`. Added `addon/posecap_addon/__init__.py` and `py.typed` so the package has a registration entry point and pyright can type-check the addon source.

The first public client test starts a local TCP server, writes two schema-valid pose frames, and verifies `TcpPoseStreamClient.latest()` returns only the newest unconsumed frame before returning `None`. Verification passes: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, and `uv run pytest -q` (`93 passed, 1 deselected`).

Not claimed in this slice: Blender extension manifest/build, bpy timer application, engine process spawning, lifecycle UI, reconnect behavior, armature validation, keyframe preservation checks, or Blender 4.2/5.x HITL verification.

Follow-up `/ad-review` found two addon-client issues before merge. A TDD pass added public `TcpPoseStreamClient` regressions for an idle gap between stream frames and for stopping while the client is still connecting. The client now puts the connected socket back into blocking mode before wrapping it with `socket.makefile("r")`, avoiding Python's timed-out file-object state, and a voluntary `close()` during connect no longer reports the last connection failure as a terminal stream error.

Added the extension packaging slice with `addon/blender_manifest.toml`, the Blender extension root entry point at `addon/__init__.py`, and `tools/build_extension.py`. The build script stages `addon/`, builds `posecap-contracts` and `posecap-core` wheels with `uv build --wheel --package ... --out-dir ...`, verifies that every wheel declared in the manifest exists, and writes `posecap-0.1.0.zip`.

TDD coverage for the public packaging behavior lives in `tests/addon/test_build_extension.py`: it exercises `build_extension()` through a fake wheel builder and asserts the zip contains the manifest, root entry point, addon package, stream client, and vendored wheel paths declared by Blender. Verification passed for the focused test, the real build into `.agentic/extension-dist/posecap-0.1.0.zip`, `blender --command extension validate --valid-tags=""`, and a Blender 5.0 CLI build/validate from the staged source. Full local gates passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, and `uv run pytest -q` (`98 passed, 1 deselected`).

Pre-merge `/ad-review` found one packaging bug before the branch was merge-ready: `build_extension(repo_root=...)` accepted an explicit repository root but still ran `uv build --package` from the caller's current working directory. A TDD regression now changes cwd outside the repo and verifies the wheel-builder runs from `repo_root`; the build script wraps only the `uv build` calls in that working directory. The previously failing outside-repo invocation now builds the extension zip, and Blender 5.0 validates it successfully.

Added `addon/posecap_addon/engine_process.py` as the pure-Python process launcher slice. The public `start_engine_stream()` surface starts a process from an argv list with `shell=False`, reads the engine's first stdout `listening` JSON event with a bounded timeout, returns the announced TCP endpoint together with the `subprocess.Popen` handle, and `stop()` terminates by handle with a kill fallback. TDD coverage starts a real Python child process that announces a listening endpoint and verifies the wrapper stops it, plus a timeout regression that confirms a non-announcing child process is terminated before `EngineStartupError` escapes. The extension build test now asserts `posecap_addon/engine_process.py` lands in the zip.

Verification for the launcher slice passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`101 passed, 1 deselected`), a fresh extension build, and Blender 5.0 `extension validate` on the updated zip.

Added `addon/posecap_addon/apply_timer.py` as the main-thread apply slice. `PoseApplyTimer.tick()` consumes the `PoseStream.latest()` surface, ignores empty and `no_person` frames without clearing the last pose, validates the target before every `ok` frame, runs `core.plan_pose_application()` with the configured limb filter/orientation fix, writes through a `PoseWriter`, tags redraw, and keeps previous quaternions for continuity. `BpyArmaturePoseWriter` is duck-typed so the module remains importable outside Blender; it writes `rotation_quaternion`, inserts `KEYFRAME_DATA_PATH` when recording is enabled, treats `ReferenceError: StructRNA ... removed` as an invalid target, and `tag_view3d_redraw()` marks only `VIEW_3D` areas.

TDD coverage lives in `tests/addon/test_apply_timer.py`: it verifies `ok` frame application/reschedule, `no_person` hold-last-pose behavior, single warning plus recovery for invalid targets, Blender-style quaternion/keyframe writes, removed-armature invalidation, and redraw tagging. The extension build test now asserts `posecap_addon/apply_timer.py` lands in the zip. Verification passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`107 passed, 1 deselected`), a fresh extension build, and Blender 5.0 `extension validate`.

Final pre-merge review hardening caught two packaging issues before the branch was ready: the manifest used the broader `GPL-3.0-or-later` SPDX expression while ADR-0006 and CONTRIBUTING bind the addon to GPL-3.0, and `tools/build_extension.py` could recursively clear an arbitrary existing staging directory if called with an unsafe `--staging-dir`. TDD coverage now asserts the manifest declares `SPDX:GPL-3.0-only`, the generated zip excludes the internal staging marker, staging inside protected repository source paths is rejected, and existing non-stage directories are left untouched.

Post-hardening verification passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`109 passed, 1 deselected`), a fresh extension build, and Blender 5.0 `extension validate` on the rebuilt zip.

Not claimed in this slice: Blender preferences, Start Stream UI lifecycle wiring, extension installation through the UI on Blender 4.2 LTS and 5.x, headless register/unregister smoke, live stream application inside Blender, keyframe-count preservation checks, or apply-time rotating-log instrumentation.

### 2026-06-29

Added the lifecycle UI/state slice with `addon/posecap_addon/ui_state.py` and `addon/posecap_addon/panels.py`. The pure state model covers Stopped, Starting, Streaming, Recording, Reconnecting, and Warning affordances; the Blender adapter registers `Scene.posecap`, a View3D sidebar panel, and Start/Stop operators through the package registration chain without importing `bpy` during normal pytest/pyright runs. The panel delegates drawing to a pure function so lifecycle controls stay covered outside Blender.

TDD coverage now verifies the state-control matrix, panel drawing through a fake layout, Blender-style class/property registration through a fake `bpy`, addon register/unregister delegation, and extension packaging of the new UI files. A Blender 5.0.1 background smoke with the staged vendored wheels registers `posecap_addon`, mutates `bpy.context.scene.posecap.lifecycle_state`, and unregisters twice without raising. Not claimed in this slice: preferences, real Start Stream engine/process wiring, transition to Streaming after first frame, extension installation through the UI, live pose application inside Blender, recording/keyframe behavior, or rotating apply-time instrumentation.

Verification passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`113 passed, 1 deselected`), a fresh extension build, Blender 5.0 `extension validate`, and the Blender 5.0.1 background register/unregister smoke.

Connected the lifecycle panel Start/Stop operators to the real addon-side live runtime. Start now builds the public engine command (`posecap-engine live --pear-root ... --camera-index ... --parent-pid ...`), starts the engine through `start_engine_stream()`, starts `TcpPoseStreamClient`, registers a stable `bpy.app.timers` callback around `PoseApplyTimer.tick()`, and transitions Starting to Streaming on the first received frame. Stop now unregisters the timer callback when still registered, closes the stream client through the timer, terminates the engine process by handle, clears Record Live MoCap, and returns the UI to Stopped. Addon unregister also stops any active session before removing Blender classes/properties.

TDD coverage added two public operator tests in `tests/addon/test_ui_state.py`: the happy path verifies Start owns engine/client/timer and Stop tears them down, and the timeout path verifies a client connection error is observed by the main-thread timer, lands in Stopped with a reason, and closes both client and engine. The implementation deliberately does not mutate `Scene.posecap` from the TCP reader thread; the background client only records `error`, and the timer callback performs lifecycle transitions on Blender's main thread. No new core/contracts/engine coupling was added.

Verification passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`115 passed, 1 deselected`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, Blender 5.0 `extension validate`, and a Blender 5.0.1 background smoke that registers `posecap_addon`, mutates `bpy.context.scene.posecap.lifecycle_state`, and unregisters twice. Not claimed in this slice: Blender preferences/installer wiring for the PEAR runtime executable, socket-drop reconnection, recording/keyframe behavior, apply-time rotating-log instrumentation, extension installation through the UI, or Blender 4.2 LTS HITL verification.

Added the socket-drop and engine-death lifecycle slice. `TcpPoseStreamClient` now exposes a public `connection_state`, treats EOF/read `OSError` after an established connection as a recoverable drop, enters `RECONNECTING`, and reconnects to the same announced endpoint with the existing bounded retry behavior. Decode/schema errors remain terminal. The live-stream timer observes the client state on Blender's main thread, transitions Streaming/Recording to Reconnecting, promotes back to Streaming on the next frame, and checks engine liveness before client errors so an externally dead engine lands in Stopped with `Engine process exited`.

TDD coverage added public tests for the operator/timer lifecycle (`Streaming -> Reconnecting -> Streaming` on socket drop, no resume from a queued stale frame while still reconnecting, and `Streaming -> Stopped` on engine death) plus a real localhost reconnect test for `TcpPoseStreamClient` across two server-side TCP connections. Focused verification passed: `uv run pytest tests/addon/test_ui_state.py tests/addon/test_stream_client.py tests/addon/test_apply_timer.py -q` (`18 passed`). Not claimed in this slice: apply-time rotating-log instrumentation, Blender preferences/installer wiring, recording/keyframe behavior, extension installation through the UI, or Blender 4.2 LTS HITL verification.

Full verification passed for this slice: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`119 passed, 1 deselected`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, Blender 5.0 `extension validate`, and a Blender 5.0.1 background register/unregister smoke against the staged extension.

Added addon apply-time instrumentation. `PoseApplyTimer` now accepts an `ApplyTimeInstrumentation` adapter, records only successfully applied `ok` frames, and emits aggregate INFO logs on an interval instead of logging per frame. `configure_addon_logging()` installs a bounded stdlib `RotatingFileHandler` for `posecap-addon.log`, and Start Stream configures it from `bpy.app.tempdir` before creating the timer. The extension packaging test now asserts `posecap_addon/instrumentation.py` ships in the zip.

TDD coverage added public tests for interval aggregation without INFO per frame, bounded rotating-log handler setup without duplicate handlers, `PoseApplyTimer` duration recording on applied frames, Start Stream instrumentation wiring, and extension packaging of the new module. Focused verification passed: `uv run pytest tests/addon/test_apply_timer.py tests/addon/test_instrumentation.py tests/addon/test_ui_state.py tests/addon/test_build_extension.py -q` (`22 passed`). Full local pytest passed with `123 passed, 1 deselected`. Not claimed in this slice: Blender preferences/installer wiring, recording/keyframe behavior, extension installation through the UI, or Blender 4.2 LTS HITL verification.

Added the headless Blender e2e smoke. `tests/e2e/test_blender_addon_smoke.py` builds the extension zip with vendored wheels, extracts it into a temporary extension root, runs Blender via `blender --background --factory-startup --python`, loads the extension root entry point, registers the addon, unregisters twice, registers again, creates a minimal armature with a `pelvis` bone, and applies a simulated `ok` pose frame through `PoseApplyTimer`/`BpyArmaturePoseWriter`. The test is marked `e2e`/`slow` so default pytest gates continue to deselect it unless explicitly requested.

Focused verification passed with Blender 5.0 at `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe`: `POSECAP_BLENDER=... uv run pytest tests/e2e/test_blender_addon_smoke.py -q -m e2e` (`1 passed`). Focused ruff checks for the new test passed. Not claimed in this slice: extension installation through Blender's UI, Blender 4.2 LTS HITL verification, recording/keyframe behavior, or the full 4.2/5.x manual verification matrix.

Full verification for this slice passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`123 passed, 2 deselected`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, and Blender 5.0 `extension validate`.

Added armature-warning recovery for the live panel runtime. The stream session now resolves `Scene.posecap.target_armature` on each applied frame instead of freezing the original object at Start Stream, and `PoseApplyTimer` reports recovery after a successful apply following an invalid-target warning. A deleted/removed armature now transitions the UI to Warning once; selecting a valid replacement lets the next `ok` frame apply to the new target and returns the UI to Streaming without restarting the stream.

TDD coverage added `test_streaming_invalid_armature_warns_and_reselected_target_resumes`, which starts the panel runtime with a removed armature, observes the Warning state, swaps in a fake valid `pelvis` armature, and verifies the next frame applies and restores Streaming. Focused verification passed: `uv run pytest tests/addon/test_ui_state.py tests/addon/test_apply_timer.py -q` (`17 passed`). Not claimed in this slice: recording/keyframe behavior, extension installation through Blender's UI, Blender 4.2 LTS HITL verification, or the full 4.2/5.x manual verification matrix.

Full verification for this slice passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`124 passed, 2 deselected`), `POSECAP_BLENDER=... uv run pytest tests/e2e/test_blender_addon_smoke.py -q -m e2e` (`1 passed`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, and Blender 5.0 `extension validate`.

Added the Stop Stream process-listing acceptance check. `tests/addon/test_ui_state.py::test_stop_stream_terminates_engine_process_and_removes_pid` starts the panel runtime with a real long-lived Python child wrapped in `EngineProcess`, invokes the public Stop Stream operator, and verifies both the process handle and OS process listing (`tasklist` on Windows, `ps` elsewhere) no longer show the PID within the existing 5-second stop path. The runtime already used `EngineProcess.stop()` correctly, so no addon implementation change was needed in this slice.

Focused verification passed: `uv run pytest tests/addon/test_ui_state.py::test_stop_stream_terminates_engine_process_and_removes_pid -q` (`1 passed`) and `uv run pytest tests/addon/test_ui_state.py tests/addon/test_engine_process.py -q` (`13 passed`). Not claimed in this slice: extension installation through Blender's UI, Blender 4.2 LTS HITL verification, recording/keyframe behavior, or the full 4.2/5.x manual verification matrix.

Full verification for this slice passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`125 passed, 2 deselected`), `POSECAP_BLENDER=... uv run pytest tests/e2e/test_blender_addon_smoke.py -q -m e2e` (`1 passed`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, and Blender 5.0 `extension validate`.

### 2026-07-01

Added a public Start Stream timeout acceptance regression. `tests/addon/test_ui_state.py::test_start_stream_real_client_timeout_stops_engine_process` drives the registered Start Stream operator with a real `start_engine_stream()` child process that announces an unused localhost endpoint, a real `TcpPoseStreamClient` configured with a short bounded retry window, and the public timer callback. The existing runtime already moved Starting to Stopped with a reported connect-timeout reason and terminated the engine process by handle, so this slice required no addon runtime change.

Focused verification passed: `uv run pytest tests/addon/test_ui_state.py::test_start_stream_real_client_timeout_stops_engine_process -q` (`1 passed`) and `uv run pytest tests/addon/test_ui_state.py tests/addon/test_stream_client.py tests/addon/test_engine_process.py -q` (`18 passed`). The previous public operator happy-path test continues to cover Starting to Streaming after the first frame.

Full verification for this slice passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`126 passed, 2 deselected`), `POSECAP_BLENDER=... uv run pytest tests/e2e/test_blender_addon_smoke.py -q -m e2e` (`1 passed`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, and Blender 5.0 `extension validate`.

Added a keyframe-preservation acceptance regression for live pose application. `tests/addon/test_apply_timer.py::test_bpy_armature_pose_writer_preserves_existing_keyframes_when_not_recording` records the existing keyframe count on a Blender-style fake pose bone, applies a non-recording stream pose, and verifies the keyframe count/list is unchanged while the quaternion is updated. The broader acceptance criterion is covered by existing tests for latest-wins stale-frame dropping (`tests/addon/test_stream_client.py`), stream timer application (`tests/addon/test_apply_timer.py`), and core limb-filter/orientation-fix planning (`tests/core/test_application.py`, `tests/core/test_filters.py`).

Focused verification passed: `uv run pytest tests/addon/test_apply_timer.py::test_bpy_armature_pose_writer_preserves_existing_keyframes_when_not_recording -q` (`1 passed`) and `uv run pytest tests/addon/test_apply_timer.py tests/addon/test_stream_client.py tests/core/test_application.py tests/core/test_filters.py -q` (`27 passed`).

Full verification for this slice passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`127 passed, 2 deselected`), `POSECAP_BLENDER=... uv run pytest tests/e2e/test_blender_addon_smoke.py -q -m e2e` (`1 passed`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, and Blender 5.0 `extension validate`.

Added the addon preferences skeleton. `POSECAP_AP_AddonPreferences` registers under the active add-on package id, draws persistent defaults for the external PEAR checkout and engine executable, and Start Stream now falls back to those preferences when the scene-level PEAR Root field is empty. Scene settings remain the per-file override; preferences provide the install-level default without adding installer behavior to task 0004.

Focused verification passed: `uv run pytest tests/addon/test_ui_state.py -q` (`14 passed`) and `uv run pytest tests/addon/test_ui_state.py tests/addon/test_registration.py tests/addon/test_build_extension.py -q` (`19 passed`).

Full verification for this slice passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`129 passed, 2 deselected`), `POSECAP_BLENDER=... uv run pytest tests/e2e/test_blender_addon_smoke.py -q -m e2e` (`1 passed`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, and Blender 5.0 `extension validate`.

Recorded partial extension install evidence for the manual verification matrix. This workstation currently has Blender 5.0.1 only (`C:\Program Files\Blender Foundation\Blender 5.0\blender.exe`); no Blender 4.2 LTS install was found under `C:\Program Files\Blender Foundation`, so the 4.2 half of the install acceptance remains HITL/open. With `BLENDER_USER_RESOURCES` isolated to `.agentic\blender-user-resources-5.0`, Blender 5.0.1 listed `user_default` under that temporary directory, `blender --command extension install-file --repo user_default --enable .agentic\extension-dist\posecap-0.1.0.zip` exited 0, `blender --command extension list` reported `posecap [installed]`, and a background preferences check printed `bl_ext.user_default.posecap` in `bpy.context.preferences.addons`.

### 2026-07-05

Added a public pose-orientation diagnostic after iVCam HITL showed visually inverted arm motion on the temporary smoke armature. `tools/diagnose_pose_orientation.py --pretty` builds a synthetic `left_shoulder_positive_z` payload, runs the public `core.plan_pose_application()` path, independently ports Dean's POC Rodrigues/quaternion behavior for the same payload, and reports PoseCap-vs-POC quaternions per sampled bone. The diagnostic currently reports `matches_poc: true`, with only `pelvis` and `left_shoulder` non-identity; this pins the core math to Dean's POC path and keeps the remaining visual mismatch suspicion on target armature rest pose / bone local axes rather than stream transport, camera index, PEAR extraction, or the PoseCap core planning route.

TDD coverage lives in `tests/tools/test_pose_orientation_diagnostic.py`. The red step failed on the missing diagnostic script; the green step passed with `uv run pytest tests\tools\test_pose_orientation_diagnostic.py -q` (`1 passed`). Focused ruff and Windows pyright checks also passed for the new test/tool pair.

Full verification for this slice passed: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`130 passed, 2 deselected`), `POSECAP_BLENDER=... uv run pytest tests/e2e/test_blender_addon_smoke.py -q -m e2e` (`1 passed`), a fresh extension build to `.agentic/extension-dist/posecap-0.1.0.zip`, and Blender 5.0 `extension validate`. Blender 4.2 LTS remains unverified on this workstation because no 4.2 install exists under `C:\Program Files\Blender Foundation`.

### 2026-07-09

Closed the Blender 4.2 half of the extension install matrix using the official
Blender 4.2.22 LTS portable build (downloaded from download.blender.org, run
from a scratch directory — nothing installed system-wide). With
`POSECAP_BLENDER` pointing at it, the headless e2e smoke passed
(`uv run pytest tests/e2e/test_blender_addon_smoke.py -q -m e2e`, `1 passed in
6.88s` — register/unregister double-toggle plus a simulated frame apply on the
bundled extension zip). With `BLENDER_USER_RESOURCES` isolated to
`.agentic/blender-user-resources-4.2`, `blender --command extension
install-file --repo user_default --enable .agentic/extension-dist/posecap-0.1.0.zip`
exited 0 and `extension list` reported `posecap [installed]`. Together with the
2026-07-01 Blender 5.0.1 evidence, the 4.2 LTS + 5.x install acceptance is now
covered headlessly on both versions; interactive GUI verification (panel
visible, stream connects) remains the HITL half.

Realtime measurement (engine side, RTX 3080, `--source` video fixture and
physical camera index 0): NET steady-state inference 22.6 FPS on the 30fps
dance fixture (inter-frame p50 40.0 ms, p95 41.5 ms — flat, compute-bound) and
18.9 FPS on the live camera (p50 47.5 ms, p95 53.0 ms — capture read serializes
on top of inference). Both below the 30 FPS / sub-100 ms spec target; the
sub-100 ms p95 latency component holds, the throughput component does not yet.
Optimization is spike work (per-stage bench prepared; YOLO detector size and
capture/infer overlap are the leading candidates).

### 2026-07-10 (GUI live demo — two real defects found)

Drove the full extension interactively in Blender 5.0.1 GUI (remote-controlled
session): extension installed via the extension system, PoseCap panel rendered
with all settings, Start Stream spawned the engine, lifecycle reached
Streaming, and the TCP client delivered a complete 1800-frame fixture stream
into the latest-wins slot (verified live: `seq 1799` waiting in the slot). A
real streamed pose was applied to the target armature (dance pose visible in
the viewport). Two defects surfaced:

1. **Blender extension wheel cache ignores same-version updates
   (release-blocker for updates).** Reinstalling a rebuilt `posecap-0.1.0.zip`
   kept the previously extracted `posecap_core` in
   `extensions\.local\lib\python3.11\site-packages` because the vendored wheel
   filename did not change. Result: new addon code + stale core wheel →
   `AttributeError: 'PoseApplication' object has no attribute 'world_offset'`
   inside the apply timer — which bpy silently unregisters on first exception.
   Symptom: panel says Streaming, armature frozen, no error surfaced to the
   user. Fix policy: every extension rebuild that touches vendored wheels MUST
   bump the wheel version (dev suffix, e.g. `0.1.1.dev<n>`), and the apply
   timer must catch exceptions and surface them in the panel instead of dying
   silently. Manual workaround validated: clear the two package dirs in
   `.local` and reinstall.

2. **`bpy.app.timers` starvation in an idle/remote session (needs its own
   diagnosis).** With the wheel cache fixed, the first frame applied and then
   the timer never fired again — `bpy.app.timers.is_registered()` returned
   True while the callback stopped being scheduled, in a session driven by
   remote input with the Blender window unfocused. Manual `tick()` calls from
   the Python console applied frames correctly every time (stream, client,
   planner, and writer all healthy). June's interactive HITL sessions never hit
   this. Candidate directions: exception-kill on a second code path (timer
   dies silently — same surfacing fix as above), or event-loop timer
   starvation specific to unfocused/remote sessions; the POC used a modal
   operator, which is the natural fallback if timers prove unreliable.
   Follow-up owns a minimal repro (`/ad-diagnose` material).

Session note: a debug attempt driving the timer via
`bpy.ops.wm.redraw_timer` from the console crashed Blender — that crash is the
debug tool's fault, not the addon's; do not use it as a workaround.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
