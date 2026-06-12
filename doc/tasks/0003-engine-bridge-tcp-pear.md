# Task 0003: Engine bridge — TCP pose server wrapping PEAR

**Status:** proposed
**Created:** 2026-06-11
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

The engine side reuses the POC's verified inference loop (`PEAR/live_webcam.py:146-209`: capture without CAP_DSHOW — it froze some Windows webcams; YOLO classes=0 imgsz=640 most-confident box; crop-ratio patch; torch.no_grad; cv2.Rodrigues conversion) and replaces the pickle/os.replace file handoff with NDJSON over a localhost TCP server (ADR-0002/0003). PEAR installs from a pinned external revision (ADR-0005); weights pin a HuggingFace revision with `weights_only=True` — the POC's global `torch.load` monkeypatch (`live_webcam.py:13`) is banned. Device enumeration moves here because the engine owns the environment that can enumerate (the POC's in-Blender attempt never worked). The spec's open question on TCP port strategy gets resolved and recorded in this task's Notes. HITL: needs CUDA GPU and a physical webcam. Depends on tasks 0001-0002.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] `uv run corridorrig-engine devices` prints a JSON device list usable by the addon dropdown.
- [ ] Live mode serves schema-valid NDJSON pose frames at inference rate; "no person" produces explicit status frames, not silence.
- [ ] Integration test against recorded fixture frames (no live camera) validates frames against the golden schema; `gpu` tag skips cleanly without CUDA.
- [ ] Engine exits within 5 seconds of parent-PID death and on stream-socket disconnect (decision between the two recorded in Notes).
- [ ] PEAR revision and HF weight revision pinned in config; no `weights_only=False` anywhere (grep-clean).
- [ ] Inference FPS logged at INFO on an interval to a rotating log; no per-frame disk I/O or above-DEBUG logging on the hot path.
- [ ] TCP port strategy implemented and documented (Notes + contracts handshake if schema changed).

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [ ] `engine/src/corridorrig_engine/capture.py` — webcam open/read (no CAP_DSHOW), device enumeration.
- [ ] `engine/src/corridorrig_engine/pear_adapter.py` — model load (pinned), detect+infer+Rodrigues, reusing POC loop structure.
- [ ] `engine/src/corridorrig_engine/stream_server.py` — TCP server, NDJSON frames via contracts codec, single-client lifecycle.
- [ ] `engine/src/corridorrig_engine/watchdog.py` — parent-PID + disconnect liveness (platform adapter).
- [ ] `engine/src/corridorrig_engine/cli.py` — `devices` and `live` entry points.
- [ ] Resolve port strategy; record in Notes; update contracts if handshake needed.
- [ ] `tests/engine/` — fixture-frame integration tests (`integration`/`gpu` tags).
- [ ] Full gate + /ad-commit.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-06-11

Decision: the recorded-frame fixtures created for this task's integration tests carry ground-truth pose labels (rendered SMPL-X sequences with known parameters) so the pose-accuracy eval harness (PRD Next roadmap) has labeled data from day one. The harness itself is out of this task's scope — it gets its own spike after the engine CLI lands.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
