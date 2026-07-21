# Task 0041: Recover cu128 throughput and measure the recording cost

**Status:** proposed
**Created:** 2026-07-21
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:**
**Board ref:**

## Context

PoseCap ships a real-time promise on a runtime that costs a third of its frame
rate, and a second cost on top of that which was only discovered during the
v1.0.7-win.11 qualification and has never been investigated.

The first cost is accepted and disclosed. Moving PEAR to the cu128 matrix
(ADR-0016) was required for RTX 50 support, and it regresses pre-Blackwell
throughput: interleaved cold-GPU A/B on an RTX 3080 measured 30.25 to 20.53
mean NET FPS, a median +46.2 % frame-time, consistent across all six pairs
(`doc/benchmarks.md`, 2026-07-17). The cause was narrowed rather than guessed:
identical precision policy on both paths, `cudnn.benchmark=False` on both, zero
`conv3d` anywhere, so the delta tracks the torch/cuDNN kernel matrix (cuDNN
9.1 to 9.10) on Ampere. The cheap recovery lead was tested and closed —
`cudnn.benchmark=True` is neutral-to-worse, consistent with the EHM batch size
varying with detected-person count. The remaining lead, never actioned, is to
profile the EHM ViT forward per operation under both matrices; that backbone is
attention- and matmul-heavy, which cuDNN conv autotuning does not touch.

The second cost is new. Task 0032's 2026-07-20 entry recorded that recording is
not free: with Record Live MoCap engaged, addon pose-apply latency rises from
about 1.8 ms to 4.0–7.7 ms (peak 13.4 ms) and engine throughput drops from
about 21 to 15.40–17.83 `stream_fps` in the same session. The 2026-07-17 A/B
measured streaming only, so this cost is absent from every published number.
Recording is what an animator actually does with the product, which makes this
the number that matters most and the one we have never characterised.

There is also documented headroom that is not a regression at all:
`doc/benchmarks.md` notes upstream PEAR reporting a 50 FPS live demo against our
~37 FPS model-plus-pre/post stage cost on the same class of GPU, so pipeline
overhead is a separate recoverable seam from the kernel-matrix regression.

Without this work the product keeps a measured shortfall against its own PRD
target of sustained 30 FPS, and the maintainer keeps facing a
per-architecture-payload question (one build for RTX 30/40, another for RTX 50)
whose only honest answer today is guesswork. Recovering the regression on the
single matrix removes that question instead of answering it.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] The recording cost is characterised on a quiesced GPU with the same
      interleaved method as the 2026-07-17 A/B: streaming-only versus
      recording, warmup discarded, at least five measured pairs, reported as
      NET FPS and pose-apply latency.
- [ ] A per-operation profile of the EHM forward under cu124 and cu128 exists
      and names the operations that account for the frame-time delta, rather
      than attributing it to the matrix as a whole.
- [ ] Each recovery candidate the profile suggests is either adopted with a
      measured gain, or rejected with the measurement that rejected it —
      recorded in Notes the way the `cudnn.benchmark` lead already was.
- [ ] The split of the recording cost between engine throughput and addon
      pose-apply work is established, so it is known which side to optimise.
- [ ] `doc/benchmarks.md` gains a dated row for the recording measurement,
      and one for any accepted recovery, in the existing ledger format.
- [ ] Whatever the outcome, the per-architecture-payload question is answered
      with evidence: either the regression is recovered enough that one matrix
      stands, or the residual cost is quantified so the fork can be judged on
      numbers.
- [ ] The measurement basis for the PRD's 30 FPS target is fixed and recorded
      (recording or streaming, which GPU, which detector preset), so the target
      becomes falsifiable rather than a number without conditions.
- [ ] The final result states plainly how far the best achieved configuration
      sits from 30 FPS under that basis — the target stands (2026-07-21
      maintainer decision), so "improved" is not a passing answer.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [ ] Reproduce the recording cost measured during the v1.0.7-win.11
      qualification, on a quiesced machine, using the `doc/benchmarks.md`
      method.
- [ ] Separate engine-side from addon-side cost using the existing
      instrumentation (`stream_fps` and `pose_apply_time`).
- [ ] Profile the EHM forward per operation under both matrices with
      `torch.profiler`, not conv-level knobs, per the 2026-07-17 finding.
- [ ] Evaluate the candidates the profile surfaces; measure each, keep or
      reject with the number.
- [ ] Investigate the separate pipeline-overhead seam implied by the upstream
      50 FPS comparison in `doc/benchmarks.md`.
- [ ] Record every result in `doc/benchmarks.md` and close out the
      per-architecture-payload question in Notes.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-21

Opened from the v1.0.7-win.11 qualification. Two leads are already closed and
must not be re-run: `cudnn.benchmark=True` does not recover the regression
(tested, neutral-to-worse), and the conv3d+AMP regression is not applicable
(zero `conv3d` on any PEAR path). Start from the ViT forward.

The maintainer asked during the qualification whether shipping separate
RTX 30/40 and RTX 50 builds would be worth it. The recommendation was not to
fork: the cost of a fork is permanent and doubles every future migration
(cu128 is itself terminal, with CUDA 13 next), while the regression is
plausibly recoverable once. This task is what makes that recommendation
falsifiable rather than a preference.

### 2026-07-21 — maintainer decision: the 30 FPS target stands

Asked whether the PRD's 30 FPS target should be revised to match the shipped
cu128 numbers, the maintainer confirmed it stays at 30 and will be treated as
unmet until reached. The PRD is therefore deliberately unchanged.

That decision changes what this task is. The 2026-07-17 A/B measured **cu124 at
30.25 mean NET FPS** — the target, met, on the qualified RTX 3080 — against
cu128's 20.53. So this is not a target the product has never reached; it is one
that was reached and then traded for RTX 50 support with open eyes. This task
is regression recovery against a standing commitment, not opportunistic
optimisation, and it is prioritised accordingly.

It also reopens the fork question rather than settling it. The earlier
recommendation against per-architecture payloads rested on accepting ~20 FPS
for the pre-Blackwell majority; with 30 FPS reaffirmed as the bar, that
acceptance is no longer available as a steady state. Recovering cu128 on a
single matrix remains the better outcome — it serves every GPU and avoids
doubling all future migrations — but a temporary cu124 payload for RTX 30/40
is now a legitimate fallback, and this task's measurements are what decide
between them.

Open before measurement can begin: the target needs a definition it does not
have. `doc/product/PRD.md` says "pose applied in the viewport at 30 FPS ... on
an RTX-class GPU", which does not say whether recording counts, which GPU, or
which detector preset — and this qualification showed recording alone costs
about a quarter of the frame rate. The proposed basis, pending the maintainer's
confirmation, is the hardest honest one: **30 FPS while recording, on the
RTX 3080 that is already the qualification reference, at the default detector**.
Until that is fixed, no measurement here can declare the target met.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
