# Benchmarks

Hardware-keyed measured evidence. Every entry records the machine, date, method,
and conditions — a number without its hardware and conditions is noise. Decisions
derived from these numbers live in ADRs/commits; this file is the ledger.

Method scripts referenced here are session tools; the durable harness is
`tests/engine/test_source_stream_invariants.py` (`pytest -m gpu`) plus the
per-stage/variant methodology described per entry.

## Workstation A — RTX 3080 10 GB, Windows 11, driver 610.62, torch 2.4.1+cu124

### 2026-07-10 — live pipeline stage costs (dance fixture, 60 frames, warmed)

Method: real `_load_pear_runtime`, per-frame `perf_counter` around the YOLO
detect call and the full `infer()`; fixture `dance_fast_indoor_1280x720_30fps.mp4`.
Conditions: desktop session active (~3.7 GB VRAM held by other apps) — treat as
upper bound, not clean-room.

| Stage | mean | p95 |
|---|---|---|
| YOLO detect (yolov8x @ 640) | 15.5 ms | 16.8 ms |
| PEAR EHM + pre/post (derived) | 27.2 ms | 45.0 ms |
| Full serial frame (yolov8x) | 43.7 ms | 61.8 ms |

Implied serial ceiling with yolov8x: ~23 FPS.

### 2026-07-10 — YOLO variant sweep (150 frames = 50 x 3 fixtures)

Method: same runtime path, detector swapped; detection = >=1 person box per frame.

| Model | mean | p95 | Detection rate |
|---|---|---|---|
| yolov8x | 15.5 ms | 16.8 ms | 100% (150/150) |
| yolov8m | 7.4 ms | 9.4 ms | 100% (150/150) |
| yolov8s | 5.8 ms | 8.7 ms | 100% (150/150) |
| yolov8n | 5.5 ms | 7.1 ms | 100% (150/150) |

Decision: default `yolov8s` (commit 8549196) — identical detection on the fixture
set at ~1/3 the cost; serial budget 27.2 + 5.8 ≈ 33 ms ≈ 30 FPS spec target.
Caveat: detection *rate* is not bbox *quality*; crop_ratio 1.75 gives margin, and
the pose-accuracy eval harness (PRD Next) is the instrument for a quality delta.

### 2026-07-10 — end-to-end stream rate (net, steady-state, captured_at deltas)

Method: `live --source <input>`, TCP client, fps from timestamp span after the
first frame. Same noisy-desktop conditions as above.

| Input | Detector | NET FPS | p50 gap | p95 gap |
|---|---|---|---|---|
| dance fixture (30fps video) | yolov8x | 22.6 | 40.0 ms | 41.5 ms |
| physical camera index 0 (720p) | yolov8x | 18.9 | 47.5 ms | 53.0 ms |
| dance fixture (30fps video) | yolov8s | 24.1 | 37.0 ms | 60.5 ms |

Camera path serializes capture read (~7 ms) on top of inference — a
capture/infer overlap is the next structural win. The official 10-minute
sustained measurement (SPEC-0001 criterion) requires a dedicated GPU session
and is still pending; the yolov8s fixture number above was taken with the GPU
shared and undershoots the isolated-stage prediction.

### 2026-07-10 — GPU invariant suite wall time

`pytest -m gpu` (3 fixtures, full runtime, wire-contract assertions):
121 s with yolov8x → 47 s with yolov8s, 3/3 passing, exact frame counts.

### 2026-07-17 — cu128 vs cu124 A/B on a cold GPU (task 0032 / ADR-0016 qualification)

Method: interleaved A/B — warmup pair discarded, 6 measured pairs, runtimes
alternated within each pair to cancel slow thermal drift. NET FPS =
(frames − 1) / (last − first captured_at), identical to the 2026-07-10 baseline
row. Fixture `dance_fast_indoor_1280x720_30fps.mp4` (300 frames), detector
`yolov8s` (default), `live --source` + TCP client. Harness/method scripts:
`ab_runner.py` over `measure_fps.py` (session tools).
Conditions: quiesced desktop, GPU 43–56 °C, ~1.7 GB VRAM held (desktop apps
only), inter-run util ~0–2 %, per-run power 150–195 W (real GPU compute) —
near clean-room, unlike the shared-GPU 2026-07-10 baseline (~3.7 GB held).

Runtimes (only the CUDA matrix differs; precision policy identical):

| | OLD | NEW |
|---|---|---|
| venv | `%LOCALAPPDATA%\PoseCap\runtime\venv` | `C:\Dev\PoseCap\.venv-pear` |
| pear root | `%LOCALAPPDATA%\PoseCap\pear` | `C:\Dev\PoseCap-PEAR` |
| torch | 2.4.1+cu124 | 2.9.1+cu128 |
| torchvision | 0.19.1 | 0.24.1 |
| cuDNN | 9.1.0 | 9.10.2 |

| Matrix | mean NET FPS | median | stdev | mean frame-time |
|---|---|---|---|---|
| OLD cu124 (2.4.1) | 30.25 | 30.40 | 0.73 | 33.1 ms |
| NEW cu128 (2.9.1) | 20.53 | 20.70 | 0.46 | 48.7 ms |

Per-pair frame-time delta (NEW vs OLD): +45.0, +40.9, +43.6, +47.3, +57.9,
+49.8 % — **median +46.2 %, i.e. −32 % throughput**. Consistent across all six
pairs with tight variance on both sides: a real, large regression, not noise.

Reading: cu128 regresses live throughput hard on this pre-Blackwell (Ampere
`sm_86`) GPU. On a cold GPU cu124 sustains ~30 FPS and cu128 ~20.5 FPS; the
2026-07-10 baseline of 24.1 was shared-GPU and undershot cu124's cold ceiling.
Precision policy is identical on both paths (`torch.no_grad()` +
`set_float32_matmul_precision("high")`, no autocast) and `cudnn.benchmark=False`
on both — the delta tracks the torch/cuDNN kernel matrix (cuDNN 9.1 → 9.10 on
Ampere), not pipeline Python. This is the qualification-gate FPS regression
(GUIDELINES §5, >10 % frame-time) flagged in task 0032; it is **not** the
conv3d+AMP path (task 0032 risk 3, separately confirmed N/A — zero conv3d on
any PEAR path). Untested recovery lead, left to the maintainer: `cudnn.benchmark
= True` (fixed 720p input) may reclaim part of the cost.

Product tradeoff: cu128 is required for RTX 50 (Blackwell) support per ADR-0016;
this is its measured cost on the existing RTX 30/40 audience.

### Context: upstream claims

PEAR reports 100+ FPS model-only inference and a 50 FPS live demo (project
page). Our 27 ms PEAR-stage cost (~37 FPS model+pre/post) is consistent with
that order of magnitude on a 3080; the remaining gap to upstream numbers is
pipeline overhead, not the model — headroom exists beyond 30 FPS.
