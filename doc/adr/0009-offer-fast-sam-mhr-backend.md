# ADR-0009: Offer Fast SAM as an experimental MHR backend

**Status:** proposed
**Date:** 2026-07-14
**Deciders:** alexandremendoncaalvaro

## Context

PoseCap needs a parametric full-body alternative to PEAR that can infer a complete
parametric body from one RGB camera without loading SMPL, SMPL-X, FLAME, or MANO
assets. MediaPipe satisfies the account-free live-capture use case described by
ADR-0008, but its landmarks cannot directly observe axial rotation around straight
limbs. Fast SAM 3D Body estimates body, feet, hands, skeletal state, and a full mesh
using Meta's Momentum Human Rig (MHR), whose code and model are
[Apache-2.0](https://github.com/facebookresearch/MHR).

A frozen 100-input spike ran the
[pinned Fast SAM implementation](https://github.com/yangtiming/Fast-SAM-3D-Body/tree/808b53c7d9c26a7e511d31144f1e5efb058e15c9)
and official SAM 3D Body checkpoint on the project RTX 3080. The checkpoint SHA-256
was `b5a2f9d305dd02626b967aa2e86021fba07065df66ce7a7e00ffb9664f150abf`, and its
MHR asset SHA-256 was
`352e271a6c42729c68554ceaea0c955e866970160c31e35506d782dc0f7377bc`.
The disposable runtime was Python 3.11 with Torch `2.5.1+cu124` under WSL2 Ubuntu;
native Windows execution was not established. Ninety-seven person-present inputs
produced finite MHR results; a no-person image, malformed image, and empty image
failed explicitly.
Each result exposed 133 body-pose values, 108 hand-pose values, 45 shape values,
127 skeletal transforms, and 18,439 mesh vertices. Twenty-frame T-pose, spin, and
handstand sequences crossed no severe-discontinuity gate, and visual inspection
found plausible meshes for those three pose classes. The spike did not have
motion-capture ground truth, so it did not establish absolute pose accuracy.

The same evidence establishes three material limits. First, compiled inference
measured 284.8 ms median and 339.3 ms p95, approximately three frames per second,
with 3.99 GB peak VRAM. The
[upstream project's approximately 65 ms result](https://github.com/yangtiming/Fast-SAM-3D-Body)
was measured with its TensorRT path on an RTX 5090 and cannot be transferred to the
tested workstation; the spike did not run TensorRT. Second, all 72 published
expression values were zero across the
97 valid outputs, so this checkpoint is not a facial-capture backend. Third, direct
MHR output is not compatible with
[PoseCap's schema-v1 SMPL-X contract](../../contracts/src/posecap_contracts/frames.py),
which expects
21 body joints, two sets of 15 hand joints, 10 shape values, 10 expression values,
and SMPL-X axis-angle ordering. The
[upstream MHR-to-SMPL publisher](https://github.com/yangtiming/Fast-SAM-3D-Body/blob/808b53c7d9c26a7e511d31144f1e5efb058e15c9/docs/realworld_deployment.md)
is not an escape hatch because it requires a licensed `SMPL_NEUTRAL.pkl`.

The official checkpoint remains gated on Hugging Face and totals approximately
2.8 GB. The custom [SAM License](https://huggingface.co/facebook/sam-3d-body-dinov3/blob/main/LICENSE)
grants use, modification, and redistribution when the same agreement accompanies
the materials; it does not state a commercial-use prohibition. The agreement
therefore does not itself rule out an experimental commercial path, but it is not
an open-source license, changes may take effect through continued use, and any
commercial use or redistribution by PoseCap needs legal review.
The
[upstream loader](https://github.com/facebookresearch/sam-3d-body/blob/b5c765a0d89d789985e186d396315e7590887b94/sam_3d_body/build_models.py)
also calls `torch.load(..., weights_only=False)`, which violates PoseCap's production
security rule until the checkpoint is converted to a safe weight format or loaded
behind a separately audited boundary.

## Decision

We will preserve Fast SAM 3D Body with direct MHR output as a proposed, optional
**PoseCap MHR Experimental** backend for continuous low-rate live preview and
capture-on-command, initially aimed at stop-motion performers regulating articulated
dolls in front of the camera. It remains the existing webcam-to-engine-to-Blender
workflow; it does not introduce photo import or a separate offline product flow. We
will not present it as full-rate performance capture or a one-to-one PEAR replacement.
It must remain a separate adapter behind the engine port and must not weaken or
silently reinterpret the schema-v1 SMPL-X contract. Its first production slice
requires a capability-aware wire contract, an explicit MHR-to-PoseCap retarget
adapter, safe checkpoint loading, and legal approval of the exact checkpoint-
distribution flow. Model files remain external and must never enter PoseCap's git
history.

## Consequences

* PoseCap can pursue richer body shape, hand pose, inferred limb twist, inversion,
  and occlusion handling without any SMPL-family asset in this backend.
* The product can have three honest modules inside the same live workflow: MediaPipe
  Lite for fluid accessible preview, PEAR plus SMPL-X for the current performance-
  capture workflow, and MHR Experimental for low-rate stop-motion pose regulation.
* Users do not receive a facial-expression solution from the tested MHR checkpoint;
  a separate face backend or a future nonzero checkpoint is required.
* User-supplied weights preserve a gated account step. Bundled or PoseCap-hosted
  weights could remove that customer step, but would make PoseCap a distributor
  under the SAM License and therefore require legal approval and compliance notices.
* Approximately three FPS is unsuitable for fluid human performance capture but can
  still provide useful live feedback while a stop-motion doll remains in each pose.
  TensorRT optimization may broaden that tier only after the same frozen fixtures
  pass on supported production hardware.
* The measured WSL2 path proves the model pipeline, not PoseCap's Windows-first
  installer. A production slice must separately prove native Windows or deliberately
  make WSL2 part of the supported deployment contract.
* MHR cannot be squeezed silently into the existing SMPL-X payload without losing
  semantics. A capability-aware envelope and explicit retarget adapter preserve the
  current Blender workflow while keeping unsupported channels, such as face, honest.

## Alternatives Considered

* Replace PEAR one-to-one with Fast SAM plus MHR — rejected because the wire schema,
  full-rate performance, and facial-expression behavior are not equivalent.
* Convert MHR to SMPL with the upstream publisher — rejected because it requires a
  licensed SMPL model and defeats the purpose of the independent backend.
* Bundle the gated checkpoint immediately — rejected pending legal review of PoseCap
  as a SAM Materials distributor and a safe replacement for the pickle-based loader.
* Treat MHR as an import-and-process-later workflow — rejected because stop-motion
  performers need continuous camera feedback while regulating the physical doll; the
  measured cadence may be adequate without changing PoseCap's live concept.
* Wait for TensorRT before preserving the backend decision — rejected because the
  stop-motion preview case can already tolerate low cadence, and speed cannot resolve
  the schema, face, and license distinctions.
* Use original SAM 3D Body instead of Fast SAM — rejected because it provides the same
  MHR representation at substantially higher published latency.
