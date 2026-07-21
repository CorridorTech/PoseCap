# Task 0032: Qualify a Blackwell-capable PEAR runtime matrix

**Status:** in-progress
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:**
**Board ref:** issue #49

## Context

The PEAR backend pins Torch `2.4.1+cu124`, whose compiled CUDA kernels end at
`sm_90`. Every RTX 50 (Blackwell, `sm_120`) machine is therefore locked out of
PEAR: the GPU is visible but cannot execute the first inference (issue #49,
RTX 5090 field report). The reporter proved the path end to end by hand —
Torch nightly cu128 plus PyTorch3D compiled for `sm_120` gave a working live
PEAR stream on an RTX 5090 — and PyTorch has since shipped official Blackwell
support in stable releases: 2.7.0 is the first stable line with `sm_120`
kernels and official cu128 wheels. The RTX 50 install base only grows; every
month without a qualified matrix widens the locked-out audience of the
consumer-GPU product promise.

The release pipeline already compiles PyTorch3D from source on the release
runner (`tools/install/setup_pear_runtime.ps1`, VS 2022 + CUDA), so a matrix
bump is a re-pin plus requalification, not new infrastructure.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] A grounded matrix decision is recorded: target stable Torch line with
      `sm_120` kernels (candidate: the newest stable verified against
      PyTorch3D), cu12x index URL, and the PyTorch3D version/build that
      compiles against it — with the single-matrix-for-all-GPUs versus
      per-architecture-payload question answered by evidence, not preference.
- [x] The PEAR payload built from the new matrix passes Doctor and a real
      source-to-TCP inference on a pre-Blackwell qualified GPU (regression:
      the existing RTX 30/40 audience keeps working).
- [x] The same payload passes Doctor and a real PEAR live stream on an RTX 50
      GPU (Blackwell validation — coordinate the retest with the issue #49
      reporter if no RTX 50 hardware is available in-house).
- [ ] Doctor reports the architecture-compatibility check truthfully for both
      generations (no false "unsupported" on Blackwell, no false success).
      Pre-Blackwell half done first-hand (2026-07-20); no Doctor output from
      real `sm_120` hardware has ever been inspected — see that entry.
- [ ] Issue #49 is answered with the qualified matrix and the release that
      carries it; the issue's remaining-before-close checklist is updated.
      Answered for the matrix and the `win.10` pre-release on 2026-07-19;
      re-opened here because the release that now *carries* it is the stable
      `v1.0.7-win.11`, which the issue has not been told about — it is still
      OPEN.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [x] Ground (`ad-ground`) the exact pins: newest stable Torch with `sm_120`
      wheels compatible with PyTorch3D source builds (start at Torch 2.7.0 /
      cu128, check newer stable lines), plus torchvision and the PyTorch3D
      revision; verify cu128 wheels retain pre-Blackwell architectures so one
      matrix serves all supported GPUs.
- [x] Update the pins (`requirements-torch.lock`, `torchIndexUrl` in
      `packaging/build_installer.ps1`, PyTorch3D reference in
      `tools/install/setup_pear_runtime.ps1`) and rebuild the PEAR payload.
- [x] Qualification build (workflow_dispatch) and the two-generation
      validation runs; record evidence in Notes. Blackwell validated in the
      field on `win.10`; the pre-Blackwell packaged-payload run closed on
      `win.11` (2026-07-20 entry below).
- [x] Ship with the next release (`v1.0.7-win.11`, stable `Latest`).
- [ ] Answer issue #49 with the release that carries the matrix and close it
      out — the issue is still OPEN awaiting that comment.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-17 — task recorded

Prioritized by the maintainer into the v1.0.7 field-driven slice alongside
task 0031 (offline video batch) and tasks 0014/0015 (support bundle).
Evidence base: issue #49 reporter's working hand-built runtime (Torch nightly
cu128 + source-built PyTorch3D on an RTX 5090) and PyTorch 2.7.0 release
notes announcing official `sm_120` stable support with cu128 wheels.

### 2026-07-17 — matrix ground (web research, cited)

Recommended matrix: `torch==2.9.1+cu128` + `torchvision==0.24.x+cu128` +
PyTorch3D `v0.7.9` (current pin — its tag already contains the MSVC/CUDA-12.8
pulsar fix, commit 366eff21). One wheel serves all target GPUs: the v2.9.1
build scripts pin `TORCH_CUDA_ARCH_LIST = 7.0;7.5;8.0;8.6;9.0;10.0;12.0`
(RTX 30 native sm_86, RTX 40 runs sm_86 binaries, RTX 50 native sm_120) — no
per-architecture payloads. Time window: PyTorch is sunsetting CUDA 12.8
(cu128 default replaced by cu130 in 2.11, removed from the build matrix in
2.12), so 2.9.1 is the last patched line distributing cu128; this matrix is
stable but terminal, and the next migration will be CUDA 13 with a fresh
PyTorch3D revalidation. Fallback if the 2.9.1 source build fails:
`torch==2.7.1+cu128` (direct community evidence of PyTorch3D Windows builds).

Risks to gate in the plan: (1) no direct report of a PyTorch3D Windows build
against 2.9.1 — the qualification build is the gate, fallback recorded; (2)
`torch.load` default flipped to `weights_only=True` in 2.6 — audit every
PEAR checkpoint load; GUIDELINES §12 bans `weights_only=False`, so the
remediation is an `add_safe_globals` allowlist, never the banned flag; (3) a
conv3d+AMP performance regression in 2.9.0 (possibly fixed only in 2.10) —
check whether PEAR uses conv3d under autocast, benchmark if so; (4) driver
floor rises to R570+ and Pascal/GTX 10xx drop off — release notes must say
both. Full citations in the research record (PyPI/pytorch releases,
dev-discuss cu128 deprecation RFCs #172663/#178665, v2.9.1 build scripts,
pytorch3d #1970/v0.7.9, pytorch/vision matrix).

### 2026-07-17 — pins bumped and the four recorded risks gated

Pin bump landed on `fix/0032-blackwell-torch-matrix` per the grounded matrix
(`torch==2.9.1+cu128` + `torchvision==0.24.1+cu128` + PyTorch3D `v0.7.9`):

- `packaging/requirements-torch.lock` — `torch==2.9.1+cu128`,
  `torchvision==0.24.1+cu128`. torchvision resolved to the exact `0.24.1`
  patch (the patch-aligned pair of torch 2.9.1); both wheels verified present
  on the cu128 index for cp311/win_amd64, as is the fallback
  `torch-2.7.1+cu128` wheel.
- `packaging/build_installer.ps1` — `torchIndexUrl` now
  `https://download.pytorch.org/whl/cu128`; THIRD_PARTY_NOTICES wheel line
  updated to cu128.
- `tools/install/setup_pear_runtime.ps1` — wheel matrix parameter is `12.8`
  (sole `ValidateSet` value; both the primary and fallback matrices are
  cu128), torch/torchvision pins bumped to `2.9.1`/`0.24.1`. `-Pytorch3DRef`
  already pinned `v0.7.9`, which is exactly the matrix decision — no change.
- `tests/test_packaging_config.py` — the matrix contract test was moved to the
  new pins red-green, and extended with two drift guards: the installer
  manifest `torchIndexUrl` must carry the lock's CUDA tag, and the release
  runner script must pin the same torch/torchvision versions and index. The
  installer path is covered end to end: `install_pear.ps1` resolves
  `requirements-torch.lock` against the manifest's `torchIndexUrl`.

Risk 2 (`torch.load` default flip in 2.6) — audited, no change needed:

- Repo-wide grep: the only `torch.load` is
  `engine/src/posecap_engine/pear_adapter.py:301`, already explicit
  `weights_only=True` on a plain tensor state dict (`backbone`/`head`) —
  unaffected by the default flip; `tests/engine/test_pear_adapter.py` asserts
  the flag. No `weights_only=False` anywhere (GUIDELINES §12 clean).
- Upstream PEAR (pinned `9773319`, audited read-only at the local checkout):
  the PoseCap inference path (`Ehm_Pipeline(configs/infer.yaml)` + forward)
  executes no upstream `torch.load` at all — the adapter loads the HF
  weights itself. The upstream loads without an explicit `weights_only`
  (`models/backbones/vit.py:340`, `models/pipeline/pipeline.py:562`,
  `utils/helper.py:171`, `dataset/webdata_loader*.py`) sit on training or
  standalone-app paths never imported by the adapter; `vit.py:340`
  (`_init_backbone`) is additionally dead code on any path — it reads
  `self.cfg`, which `ViT.__init__` never assigns, and no caller invokes it.
- YOLO weights load through Ultralytics' own loader (installed unpinned at
  setup time; current releases handle the torch >= 2.6 safe-load default
  internally). The qualification Doctor run is the runtime gate.
- No `add_safe_globals` allowlist needed.

Risk 3 (conv3d+AMP regression in 2.9.0) — audited, not applicable: zero
`conv3d`/`Conv3d` in the repo and in upstream PEAR. The only AMP reference is
`models/vitdet/cascade_mask_rcnn_vitdet_h_75ep.py` (a vitdet training config
off the inference path). PEAR live inference runs full precision under
`torch.no_grad()` with `set_float32_matmul_precision("high")` — no autocast.
No benchmark required; the 10% frame-time regression rule (GUIDELINES §5)
still applies at qualification via the standard FPS instrumentation.

Risk 4 (release-note input, recorded here per plan — release notes are not
written by this task): the cu128 wheel line raises the NVIDIA driver floor to
R570+, and torch 2.9.1 kernels start at `sm_70` — Pascal/GTX 10xx (sm_6x)
drops off. Both statements must appear in the release notes of the release
that ships this matrix.

Doctor architecture check: no code change needed for truthful sm_120
reporting — `engine/src/posecap_engine/doctor.py` derives supported
architectures dynamically from `torch.cuda.get_arch_list()` and compares
against `torch.cuda.get_device_capability()`; with the cu128 wheel the arch
list includes `sm_120` and the check passes on Blackwell without a false
"unsupported". `tests/engine/test_doctor.py` fake version strings
(`2.4.1+cu124`) are arbitrary echo fixtures, not pins — left untouched.

Config-only seams (lockfile content, index URLs, PowerShell pins) are covered
by the extended contract tests above; there is no further testable Python
seam for this change — the real gates are the maintainer-run qualification
build and the two-generation validation, which stay unchecked.

Follow-up for the qualification/ship step (maintainer-gated): ADR-0007 still
records the cu124 matrix as accepted and needs a superseding amendment once
the 2.9.1 qualification build passes; `doc/benchmarks.md` entries stay as the
dated cu124 ledger and a fresh baseline row lands with the new matrix.

### 2026-07-17 — review fix package applied (four fresh-context reviews)

Consolidated findings from the two-axis reviews of the pin-bump branch,
applied on `fix/0032-blackwell-torch-matrix`:

- The binding-doc contradiction (accepted ADR-0007 still recording cu124
  while the pins ship cu128) is resolved the decision-record way:
  `doc/adr/0016-blackwell-cu128-runtime-matrix.md` drafted as proposed —
  acceptance gated on the qualification build and the two-generation
  validation — and ADR-0007 carries a factual pointer note to it. ADR-0007
  is not marked superseded until qualification passes.
- `tools/install/setup_pear_runtime.ps1` keeps the ADR-0007 matrix
  reproducible: wheel-matrix option `12.4` restored (cu124 index +
  2.4.1/0.19.1 pins in per-matrix maps) for rollback and triage; `12.8` is
  the default.
- `packaging/installer/install_pear.ps1` progress label no longer hardcodes
  a CUDA version ("Install PyTorch CUDA wheels"); a drift test now rejects
  any CUDA-version literal in that script.
- `tests/test_packaging_config.py` cross-file guards now derive the expected
  versions and CUDA tag from `requirements-torch.lock` instead of repeating
  literals, so a coordinated wrong bump cannot satisfy them; a new guard
  pins the setup script's toolkit default (`CUDA\v12.8`) to the wheel tag —
  the exact mismatch axis ADR-0007 had to surface as a warning. The module
  docstring now reflects the ADR-0016-proposed status.
- Fallback visibility: both pin sites (`requirements-torch.lock`,
  `setup_pear_runtime.ps1`) carry a comment naming the recorded fallback
  `torch==2.7.1+cu128` and pointing here and to ADR-0016.

Evidence added per review request:

- torchvision pairing: the pytorch/vision README compatibility matrix rows
  read `2.9 -> 0.24` and `2.7 -> 0.22`, so torch 2.9.1 pairs with
  torchvision 0.24.1 (patch-aligned) and the 2.7.1 fallback pairs with
  0.22.1.
- Wheel presence: the cu128 index (download.pytorch.org/whl/cu128) lists
  `torch-2.9.1+cu128-cp311-cp311-win_amd64.whl`,
  `torchvision-0.24.1+cu128-cp311-cp311-win_amd64.whl`, and the fallback
  `torch-2.7.1+cu128-cp311-cp311-win_amd64.whl` — verified by fetching the
  index listings during this session.
- Ultralytics safe-load: NOT independently verified against the package
  registry in this session. Ultralytics installs unpinned at setup time and
  its recent releases are understood to wrap checkpoint loads in their own
  safe-load handling for torch >= 2.6, but the claim rests on general
  knowledge, not a checked source; the qualification Doctor run plus the
  real source-to-TCP inference is the gate that actually proves YOLO
  weights load under torch 2.9.1.

### 2026-07-17 — cold-GPU A/B: real cu128 frame-time regression on RTX 30/40

The qualification-gate FPS instrumentation (risk-3 note said it "still applies
via the standard FPS instrumentation") fired. Measured cleanly on a quiesced,
cold RTX 3080 — an earlier same-day attempt was inconclusive because the
machine was thermally/load-contended.

Method: interleaved A/B, warmup pair discarded, 6 measured pairs alternating
per runtime, NET FPS = (frames−1)/(last−first captured_at) — the exact
benchmarks.md baseline method. OLD `%LOCALAPPDATA%\PoseCap\runtime\venv`
(torch 2.4.1+cu124) vs NEW `C:\Dev\PoseCap\.venv-pear` (torch 2.9.1+cu128),
`yolov8s`, `dance_fast_indoor_1280x720_30fps.mp4`.

Result: OLD 30.25 vs NEW 20.53 mean NET FPS — **+46.2 % median paired
frame-time, −32 % throughput**, consistent +41–58 % across all six pairs, tight
variance both sides. cu128 costs ~one-third of live throughput on Ampere
(`sm_86`). Full ledger row (matrix, conditions, per-pair table) in
`doc/benchmarks.md` (2026-07-17 cold-GPU A/B entry).

This is a **product tradeoff for the maintainer**, not a silent absorb: cu128 is
required for RTX 50 (ADR-0016) but regresses the existing RTX 30/40 audience by
~32 %. It does not change the recommended matrix (RTX 50 stays locked out on
cu124), but the release that ships ADR-0016 should decide whether to disclose
the pre-Blackwell cost in release notes and whether a recovery pass is worth it.

Cause is the torch/cuDNN kernel matrix (cuDNN 9.1.0 → 9.10.2 on Ampere), not
pipeline Python: precision policy identical on both paths (`torch.no_grad()` +
`set_float32_matmul_precision("high")`, no autocast), `cudnn.benchmark=False`
on both. It is **not** risk 3 (conv3d+AMP) — that is separately re-confirmed
N/A this session: zero `conv3d`/`Conv3d` anywhere in either PEAR root or the
adapter (the 2.9.0 regression needs conv3d to exist to bite), and the only AMP
reference remains `models/vitdet/cascade_mask_rcnn_vitdet_h_75ep.py:40`
(`train.amp.enabled`), a vitdet training config off the inference path.

Untested recovery lead for the qualification step, not yet actioned:
`torch.backends.cudnn.benchmark = True` (live input size is fixed at 720p) may
reclaim part of the cost via cuDNN algorithm autotuning — worth a spike before
accepting the regression as final.

### 2026-07-17 — cudnn.benchmark recovery lead tested: does NOT recover

Ran the lead from the entry above (`torch.backends.cudnn.benchmark = True`,
injected via `sitecustomize` on the CLI subprocess, verified False→True).
Interleaved A/B, NEW-off vs NEW-on, alternated within-pair, 5 measured pairs.

The machine was CPU-contended during this spike by an unrelated
`corridorkey2_offline-full` Inno Setup compile (ISCC pid 28324, LZMA + models),
so absolute FPS was ~half the clean main-sweep numbers and the OLD cold anchor
read 12–15 instead of ~30 — a clean absolute re-run is owed once the machine
quiesces. But the *paired* within-pair comparison is robust to that drift (off
and on runs are adjacent, same contention): benchmark=True never wins —
per-pair OLD-off ≥ on in all 5 pairs (off 15.7/16.7/16.7/18.2/14.5 vs on
12.7/12.5/16.3/16.0/12.9), mean off 16.36 vs on 14.08 (−13.9%). So
`cudnn.benchmark=True` does not reclaim the cu128 regression; it is neutral-to-
slightly-worse, consistent with the live pipeline seeing variable EHM batch
sizes (variable detected-person count) that force cuDNN to re-benchmark per
shape. Lead closed — do not pursue `cudnn.benchmark` as the fix.

Implication for the cause: the cu128 cost is most likely in the PEAR EHM ViT
backbone (attention/matmul-heavy), which cuDNN conv autotuning does not touch —
not in a conv path. Any future recovery attempt should profile the EHM forward
under both matrices (e.g. per-op timing / `torch.profiler`), not conv knobs.
The regression itself stays as recorded: real, ~+46% frame-time on Ampere, a
maintainer product tradeoff against RTX 50 support.

### 2026-07-17 — finalized release-note copy (maintainer chose accept + disclose)

Maintainer decision on the measured Ampere regression: ship the cu128 matrix and
disclose the cost (accept, not optimize — the `cudnn.benchmark` recovery lead was
tested and does not recover; see the entry above). This is the finalized
user-facing release-note block for the release that ships ADR-0016, covering the
three statements risk 4 mandated (RTX 50 support, R570+ driver floor, Pascal
drop) plus the measured RTX 30/40 throughput cost:

> [!IMPORTANT]
> **GPU support changed in this release.** The PEAR (GPU pose) backend moved to
> a new CUDA runtime to add RTX 50-series support.
> - **RTX 50-series (Blackwell) is now supported.** These GPUs could not run the
>   PEAR backend on earlier releases.
> - **NVIDIA driver R570 or newer is required** for the PEAR backend — update
>   your driver before installing if you use GPU pose.
> - **GeForce GTX 10-series (Pascal) and older GPUs are no longer supported** by
>   the PEAR backend. The MediaPipe (CPU) backend still runs on any machine.
> - **RTX 30/40-series: live PEAR frame rate is lower than the previous
>   release** — about one-third lower on an RTX 3080 in our testing. This is the
>   cost of a single runtime that serves every supported GPU from one installer.
>   Real-time capture still works; throughput is lower.

Wiring (done in this change): the durable three-fact portion (RTX 50 support,
R570+ driver floor, Pascal drop) is folded into the `$releaseNotice` here-string
in `.github/workflows/release.yml`, so `--generate-notes` prepends it on every
cu128 release — the cu128 matrix already landed on `main` via #88, so the notice
belongs on `main`, not on the (merged) `fix/0032-blackwell-torch-matrix` branch.
The transition-specific "RTX 30/40 ~one-third lower live FPS vs the previous
release" line is NOT auto-wired (it is release-relative); the maintainer pastes
it from the block above into the first cu128 release draft before publishing.
Exact FPS figures stay in `doc/benchmarks.md` (2026-07-17 cold-GPU A/B entry),
not the user-facing note.

### 2026-07-19 — qualification outcome: ADR-0016 accepted, ADR-0007 superseded

Qualification outcome recorded; ADR-0016 accepted, ADR-0007
  superseded. Evidence, in the order it arrived:
  - `v1.0.7-win.10` built and published as a pre-release. Its PEAR payload was
    verified to carry the decided pins — `requirements-torch.lock` pinning
    `torch==2.9.1+cu128` and `torchvision==0.24.1+cu128`, plus a prebuilt
    `pytorch3d-0.7.9-cp311-cp311-win_amd64.whl` — so users install a wheel
    rather than compiling. All 12 release assets verified by SHA-256.
  - **Blackwell, in the field:** the issue #49 reporter retested the published
    build on an RTX 5090 and reported it "worked out of the box with PEAR". The
    installer path therefore also worked on a real user's machine.
  - **Blackwell, independently:** a community Linux installer contribution
    (PR #98, deferred for later review) reused this matrix unmodified and
    validated it on a Linux RTX 5090.
  - **Ampere:** the 2026-07-17 interleaved A/B on a quiesced RTX 3080 ran real
    source-to-TCP inference on these pins, at the measured 32% throughput cost.
  - The addon shipped in this build also passes the real-Blender headless e2e
    suite (register/unregister, socket streaming, Mixamo conversion) on
    Blender 5.0.

### 2026-07-19 — what is still open, and why

Deliberately still open — — the pre-Blackwell criterion above is
  NOT checked. The Ampere evidence is a development-runtime A/B, not a run of
  the packaged `win.10` payload on an RTX 30/40 machine. The pending end-to-end
  release qualification covers exactly that, so this task closes when a build
  carrying this matrix is promoted to stable `Latest`. `Latest` is still
  `v1.0.6-win.4` (cu124) until then.

### 2026-07-20 — closed: packaged payload qualified on Ampere, shipped as `Latest`

The outstanding pre-Blackwell criterion is now met against a **packaged
payload**, not a development runtime, and the matrix shipped stable.

Build under test: `v1.0.7-win.11`, cut from `main` at `f27f123`. It is the
first artifact carrying the Automatic-backend fix (#101) and the removed
30 FPS claims (#103); `win.10` predated both.

- **Installer, real run on the Ampere workstation** (RTX 3080, `sm_86`,
  driver 610.62), upgrading over an existing install: completed
  ("PoseCap setup complete"). The installer preselected PEAR on the NVIDIA
  driver and showed the `Custom` setup type (#93/#95 behaviour, observed).
- **Doctor on the packaged payload — `ok: true`.** Reported
  `torch 2.9.1+cu128`, `torchvision 0.24.1+cu128`, `pytorch3d 0.7.9`; every
  PEAR import resolved (`models.pipeline.ehm_pipeline`, `utils.general_utils`,
  ultralytics, huggingface_hub); PEAR archive at the pinned revision, PEAR
  asset paths present, pinned HF weights present.
- **Architecture check on this generation only.** `torch_cuda` reported
  `supported_architectures: [sm_70, sm_75, sm_80, sm_86, sm_90, sm_100,
  sm_120]` with `status: ok` on an `sm_86` device: the wheel does carry
  Blackwell kernels alongside Ampere, and there is no false "unsupported" on
  the generation actually tested. That is only half the criterion, which is
  why it stays unchecked. **No Doctor output from real `sm_120` hardware has
  ever been inspected.** The Blackwell evidence remains what it was: the issue
  #49 reporter's prose report that `win.10` (same pins) "worked out of the
  box", and PR #98 — which commit `f27f123` deliberately narrowed to
  corroborating the runtime *version matrix* on Blackwell, **not** this ADR's
  source-build method (it used a prebuilt third-party PyTorch3D wheel).
  Neither is a Doctor architecture-check reading, so "no false success" on
  Blackwell is still unproven rather than proven.
- **Real source-to-TCP inference on the packaged payload.** A converted Mixamo
  armature (`Character ready (Mixamo); verification 0.0000`) was driven live by
  the PEAR backend from the video-file source. Streaming without recording
  (23:09:31–23:10:46): engine `stream_fps` **20.27–22.06** (mean ≈ 21.0), addon
  applying 100–105 poses per 5 s window at **avg 1.6–1.9 ms**. This is what
  the criterion demanded and what the 2026-07-19 entry refused to claim from
  the dev-runtime A/B.
- **Recording costs throughput and pose-apply latency — recorded, not hidden.**
  The moment Record Live MoCap engages, addon `avg_ms` rises from ~1.8 ms to
  **4.0–7.7 ms** (max 13.4 ms) in the same session, and the second, fully
  instrumented recording run (23:13:04–23:13:44) sustained only
  **15.40–17.83** `stream_fps` against the ~21 of streaming alone. So the
  ~20 FPS figure describes live streaming; capture-while-recording on this GPU
  runs nearer 16–18 FPS. This cost is newly observed here and is **not**
  covered by the 2026-07-17 A/B (which measured streaming only).
- **The streaming rate matches the prediction.** Mean ≈ 21.0 against the
  2026-07-17 cold-GPU A/B mean of 20.53 for cu128 (~2.5 % above) — the ~32 %
  Ampere cost that ships is the cost that was measured and disclosed, not a
  worse surprise. The recording-time figure above is a separate, additional
  cost.
- **Recording verified from a cleared state.** `animation_data` was cleared to
  `None` first (so the FBX's own imported `mixamo.com` action could not be
  mistaken for captured output); Record Live MoCap then produced a new
  `ArmatureAction` with **38 480 keyframes across 288 f-curves, all on
  `pose.bones`**, spanning frames 1–250. Provenance: this was read from the
  Blender Python console during the session and is **not** backed by any log
  file on disk — unlike the Doctor and FPS figures above, it cannot be
  re-checked from an artifact after the fact.

Scope and every session that ran, stated plainly so the numbers above cannot
be read as cherry-picked:

- 22:54:52–22:55:27 — **live webcam**, maintainer's own run on this build,
  15.90–17.24 `stream_fps` with poses applied to a rig. This is the only
  webcam evidence; every run below used the video-file source.
- 23:06:22–23:09:17 — camera source with **no subject in frame**: 53–60
  `stream_fps` (that is camera passthrough rate, not inference) and **zero**
  `pose_apply_time` entries, i.e. no pose was produced. Not evidence of
  anything except that the pipeline idles safely with nobody present.
- 23:09:31–23:10:46 — video source, streaming then first recording; the
  20.27–22.06 and latency-rise figures above come from here.
- 23:13:04–23:13:44 — video source, second recording after the animation-data
  clear; the 38 480-keyframe result and the 15.40–17.83 figures come from here.

Only PEAR was selected in the panel. MediaPipe was installed and passed its
own runtime verification at install time (`"backend": "mediapipe" ... "ok":
true`) but was never driven, so nothing here qualifies the MediaPipe capture
path.

`v1.0.7-win.11` was promoted to stable `Latest` on 2026-07-21 (UTC),
superseding `v1.0.6-win.4` (cu124) — the condition this task set for closing.

**Not closed, deliberately.** Two acceptance items are unmet and are named
above rather than waved through: the Blackwell half of the Doctor
architecture check (no `sm_120` Doctor reading exists), and issue #49's
closing comment (the issue is still OPEN). An earlier draft of this entry
checked both and set `Status: done`; a fresh-context review caught it, and
the record is corrected here rather than in a later commit.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
