# ADR-0008: Offer MediaPipe as a license-clean Lite backend

**Status:** accepted
**Date:** 2026-07-13
**Deciders:** alexandremendoncaalvaro

## Context

PoseCap's PEAR backend produces the SMPL-X rotations expected by the current wire
contract, but a working installation also depends on separately acquired
SMPL-X/FLAME/MANO assets. Those assets cannot be redistributed with PoseCap, their
research license is non-commercial, and commercial production requires a separate
Meshcapade license. This makes the highest-friction part of onboarding a licensing
and account workflow rather than PoseCap itself.

A gated spike compared two account-free candidates on the project's RTX 3080 using
13 frozen video fixtures, including low light, partial occlusion, fast motion,
handstand, no-person, malformed, and empty inputs. MediaPipe Holistic `0.10.35`
passed the distribution, function, and performance gates: its body, hand, and face
models have Apache-2.0 model cards; it processed 1,666 production frames at 62.0
FPS, with 15.8 ms median and 17.9 ms p95 inference latency. Body coverage was at
least 99.4% on person-present clips. Both hands were simultaneously visible in
60.4% to 99.2% of ordinary test clips and 33.3% of the handstand clip.

The same spike proved that MediaPipe landmarks can drive stable torso, palm, and
foot rotations through two-vector orthonormal frames. Across 1,666 frames, coverage
was 99.9% for torso and feet, 82.4% for the left hand, and 79.1% for the right hand.
A nearest-plane temporal disambiguation reduced palm flips above 90 degrees from
90 to 12 on the left and from 69 to 3 on the right, putting every tested rotation
stream below the 1% discontinuity gate. The conversion itself cost 0.098 ms p95.

That result does not make landmarks equivalent to PEAR. A straight limb's joint
centres determine its direction but not rotation around its own axis. Consequently,
MediaPipe cannot observe upper-arm, forearm, thigh, or shin axial twist without
surface cues; that component must be approximated from bend planes and temporal
continuity. PEAR's image-conditioned parametric-body fit can infer information that
the landmark stream does not contain.

RTMW3D had comparable measured throughput, but did not pass the distribution gate.
Its implementation is Apache-2.0, while the convenient ONNX files are a third-party
conversion and the published `cocktail14` training mixture includes datasets whose
commercial and redistribution permissions were not established by the spike. Its
GPU install also required approximately 1.6 GB of CUDA/cuDNN runtime packages plus
approximately 470 MB of models, and ONNX Runtime silently fell back to CPU until
the NVIDIA libraries were explicitly installed and loaded.

## Decision

We will offer MediaPipe Holistic as an optional license-clean **PoseCap Lite**
backend behind the existing engine port, while retaining PEAR plus SMPL-X as the
optional high-fidelity backend. The Lite path must expose its approximated limb
twist and reduced hand/occlusion fidelity honestly; it must not claim output parity
with PEAR.

The first released Lite capability is **body**: pelvis, torso, head, arms, legs,
and feet are converted from canonical MediaPipe world landmarks into the existing
TCP JSON pose contract. Finger joints are deliberately not applied. This preserves a
truthful body-capture/previs path while a future hand capability awaits its own
retargeting and Blender acceptance evidence. The Lite manifest declares that it does
not require PoseCap body-model assets and does not use PEAR's orientation correction.

The isolated component pins the official
[Holistic Landmarker task bundle](https://developers.google.com/mediapipe/solutions/vision/holistic_landmarker),
its SHA-256 digest, and the MediaPipe package version. Its runtime opens the same
external source-preview window as PEAR, so live stop-motion adjustment remains part
of the normal capture workflow.

## Consequences

* A user can evaluate and learn PoseCap without creating model-provider accounts,
  accepting research-only body-model terms, or purchasing a commercial body-model
  license.
* The tutorial can lead with a fast, reproducible Lite setup and explain PEAR as an
  upgrade for shots that need parametric-body fidelity, instead of spending screen
  time on three registrations and licensed downloads.
* The existing TCP JSON wire contract remains shared: the Lite runtime normalizes
  landmarks into the canonical SMPL-X-order body rotation payload before streaming.
  The Blender consumer applies only the manifest-declared body bones, so zero-value
  placeholders cannot silently alter finger joints.
* Lite output is suitable for accessible live mocap and previs, but axial limb twist,
  self-occlusion, edge-on hands, and extreme inversions can require cleanup or the
  PEAR backend. The first Lite release does not actuate fingers.
* MediaPipe model/package versions and hashes must be pinned, Apache notices must be
  retained, and upgrades require rerunning the frozen quality and continuity gates.
* This ADR does not remove or supersede the PEAR runtime in ADR-0007. It creates a
  lower-friction tier with a different fidelity promise.

## Alternatives Considered

* Replace PEAR with MediaPipe for every user — rejected because landmarks do not
  observe long-bone axial twist and the spike did not establish equal capture
  fidelity.
* Keep PEAR as the only backend — rejected because the licensed asset workflow is
  avoidable for onboarding, tutorials, evaluation, and lower-fidelity production.
* Adopt RTMW3D as the license-clean backend — rejected until the exact checkpoint,
  conversion, training-dataset, and commercial redistribution chain receives written
  clearance.
* Use Kinect or Azure Kinect as the default alternative — rejected because it adds
  discontinued or specialized hardware and does not solve detailed hand articulation
  as a camera-only default.
* Adopt SAM 3D Body or Fast SAM 3D Body as the Lite backend — rejected because the
  official weights require gated access and the tested Fast SAM path measured 339.3
  ms p95 on the RTX 3080, so it does not satisfy Lite's account-free live-capture
  promise. ADR-0009 records it separately: the SAM License permits conditional
  redistribution and does not state a commercial-use prohibition, but still requires
  legal review before PoseCap distributes the checkpoint.
