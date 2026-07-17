# Competitive Landscape — PoseCap

Status: accepted
Created: 2026-07-17
Updated: 2026-07-17
Owner: alexandremendoncaalvaro

> **Purpose.** Honest diagnosis, not marketing. This document maps where PoseCap
> genuinely wins, where it loses **today**, and what to improve — so competitive
> reality feeds the roadmap. If a rival is better on something, it is stated
> plainly and turned into an actionable item. Every "win" below is tested against
> one question: *does this matter to a non-technical animator, or is it just
> technically true?*

## Method & provenance

Built from **two** fan-out deep-research passes (each: 5 search angles → ~20
primary sources fetched → 100 claims extracted → 25 adversarially verified with a
3-voter refute panel; a claim survived only if ≤1 of 3 skeptics could refute it).
Pass 1 covered pricing/real-time/Blender for the main field; Pass 2 closed the
coverage gaps (FreeMoCap, Autodesk Flow Studio, Cascadeur, Move Live, MocapNET)
and attempted output-quality/user-complaint research. Prices and tiers were
fetched live against official pages on **2026-07-17**.

A **third pass** (2026-07-17) then targeted the output-quality / user-complaint
axis and succeeded where passes 1–2 failed: it grounded the field-wide artifact
cluster in primary CV literature (PhysCap, SIGGRAPH Asia 2020) plus vendors' own
release notes and issue trackers. Competitor output quality is now grounded;
**PoseCap's own** output quality remains unmeasured (needs the eval harness —
code, not research).

**Confidence tiers used below:**

* **Verified (3-0)** — survived unanimous adversarial verification against a
  primary source. Safe to cite.
* **Extracted** — pulled from a primary source during fetch but not run through
  the verifier (verification budget was spent on pricing/real-time/Blender
  claims). Directionally reliable, revalidate before external use.
* **Unverified gap** — named in scope but no claim survived; do not assert.

## The landscape in one breath

Every **commercial** markerless mocap tool verified here meters capture by the
second and processes **offline in the cloud** behind an account. The real free
tiers are trials: 30s/month (Rokoko Vision), 60s/month non-commercial
(DeepMotion), 15s/day (Plask), ~50s/month (QuickMagic), 30 credits once-per-
lifetime (Move One), 30s/capture (Remocapp). **None** delivers free, unlimited,
real-time webcam→Blender. The one open-source tool that shared PoseCap's exact
architecture — BlendArMocap (native addon, MediaPipe, local, real-time) — is
abandoned since 2023 and broken on modern Blender.

That leaves PoseCap effectively alone on the combination **free-unlimited +
real-time + 100% local/private + native Blender addon + GUI installer**. But
"alone on the combination" is not "best at each part" — see *Where PoseCap loses
today*.

## Archetypes

The field sorts into three groups. PoseCap does not beat any of them head-to-head
on their own turf; it occupies a gap between them.

1. **Cloud video→animation services** — Rokoko Vision, DeepMotion, Plask,
   QuickMagic, Move One. Upload a clip, wait in a queue, download FBX/BVH,
   re-import into Blender. Free tier is bait; real use is paid and metered.
   Strength: polished output, post-processing (foot-lock, physics), retarget to
   many rigs. Weakness vs PoseCap: no real-time, file round-trip friction, your
   footage leaves your machine.
2. **Low-cost real-time commercial** — Remocapp (closest functional threat),
   Rokoko Studio Live (needs their hardware or paid stream), Move Live
   (enterprise multi-camera). Real-time exists but costs a subscription/account
   and/or extra cameras.
3. **Open-source / local** — BlendArMocap (dead), FreeMoCap (offline, multi-cam,
   dependency-heavy), MocapNET / Open Mocap (research-grade, not for
   non-technical users). PoseCap's real peer group — and it is thin and neglected.

## Per-competitor verified facts

| Tool | Free tier (real) | Real-time? | Blender path | Processing | Cost (paid) | Confidence |
|---|---|---|---|---|---|---|
| **Rokoko Vision 3.0** | 30s/month Vision AI | ❌ offline; **webcam removed in 3.0** | FBX/BVH round-trip | Cloud + account | Basic $10/m, Plus $20/m (unlocks live stream + DCC plugins), Pro $50/m | Verified 3-0 |
| **Rokoko Studio Live** | — (needs hardware or Plus) | ✅ but from Rokoko Studio app / their suits | Native addon (GPL, GitHub) | Local app, but capture = their hardware | Plus $20/m for third-party live stream | Verified 3-0 |
| **DeepMotion Animate 3D** | 60s/month, non-commercial | ❌ offline (real-time only via paid API/SDK) | FBX/BVH/GLB export | Cloud + account | ~$15+/m; hands & face each +0.5 credit/s (2× base) | Verified 3-0 |
| **Plask Motion** | 15s/**day** | ❌ offline queue | Export only, **no addon** | Cloud + account | Standard $18/m (10 min/m), Pro $50/m (1 h/m) | Verified 3-0 |
| **QuickMagic** | ~50s/month (50 V Coins), FBX only | ❌ offline async queue | Has a Blender/BVH path (see caveat) | Cloud + account | Starter $9.9/m, Pro $49.9/m | Verified 3-0 |
| **Move One (Move.ai)** | 30 credits **once, ever** (~30s) | ❌ offline; 60s/clip hard cap even paid | FBX export round-trip | Cloud + account | $18/m (60 cr) → $490/m (700 cr); Gen2 = 2 cr/person/s | Verified 3-0 |
| **Remocapp** | 30s/capture (trial); 30-day Pro trial | ✅ real-time markerless webcam | Live to Blender | Their app/infra + account | Advanced $9.99/m, Pro $19.99/m — both unlimited capture | Verified 3-0 |
| **BlendArMocap** | Fully free, GPL-3.0 | ✅ (on paper) | **Native addon** | 100% local | — | Verified 3-0 — **abandoned since 2023, broken on Blender 4.0+** |
| **FreeMoCap** | Fully free, AGPL-3.0 | ❌ own FAQ: "does not currently work in realtime" | Native addon, **import-only** (loads processed sessions) | 100% local | — | Verified 3-0 — recommends **3+ cameras** for best results; "working on" real-time |
| **Autodesk Flow Studio** (ex-Wonder Dynamics/Wonder Studio; absorbed RADiCAL ~Apr 2026) | Freemium (720p, watermarked) | ❌ offline cloud batch | Blender addon = validation/export utility only | **Cloud + account** | Lite $10/m, Standard, higher res "tier-locked" | Verified 3-0 |
| **Move Live (Move.ai)** | ❌ none | ✅ real-time | — | Local, **enterprise** | Subscription/custom | Verified 3-0 — **4–8 machine-vision cameras, Ubuntu, RTX A6000, ~96 GB RAM** |
| **MocapNET** | Free, **but non-commercial FORTH license (not OSS)** | ✅ ~30 Hz body+hands+face on a laptop (needs MediaPipe) | BVH export, not an addon | 100% local | — | Verified 3-0 — commercial use **forbidden**; "no-GPU/70fps" claim refuted |
| **Cascadeur** | Free tier exists | ❌ offline; video mocap "not yet at practical accuracy" | Unreal Live Link out (not webcam in) | Local | Paid tiers | Verified 3-0 — different category (AI keyframing); has weak offline video mocap |
| **Open Mocap (Blender)** | Free | ⚠️ real-time hands only; body offline | Native addon | Local | — | Extracted — **Blender ≤4.0 only, effectively obsolete** |

## Where PoseCap wins — and does it matter?

Each win filtered through "does the non-technical animator feel this?"

1. **Privacy / 100% local — YES, matters.** Every commercial rival uploads the
   user's footage to their cloud with an account. For an animator working on
   unreleased client/studio footage (Corridor's exact case), "my video never
   leaves my machine" is a real, felt differentiator, not a technicality.
   *Verified: all of Rokoko/DeepMotion/Plask/QuickMagic/Move are cloud+account.*
2. **Free with no second-meter — YES, matters.** Rivals' free tiers are
   trials (30s/month to 30-credits-ever). An animator iterating on a shot burns
   that in one take. Unlimited local capture removes the anxiety of a running
   meter. *Verified.*
3. **Real-time inside Blender — YES, matters, but narrower than it looks.** The
   cloud services are upload-and-wait by design; Rokoko even *removed* webcam
   capture and its FAQ admits real-time AI mocap means "cutting big corners" on
   quality. So PoseCap owns real-time-in-Blender among the free/accessible
   tools — but Remocapp does real-time markerless for $9.99/m, so this is a lead,
   not a moat.
4. **The only live open-source addon peer is dead — YES, strategically.**
   BlendArMocap is the natural thing a savvy user would reach for; it's abandoned
   and broken on Blender 4.0+. PoseCap can be "BlendArMocap, but maintained and
   installable." *Verified.*
5. **GUI installer for non-technical users — YES, matters.** The open-source
   peers (BlendArMocap, FreeMoCap, MocapNET) all demand elevated Blender,
   manual pip, or a research toolchain. This is exactly the friction the PRD
   forbids for our user. *Extracted.*

## Where PoseCap loses today — honest

These are real gaps, ordered by how much they hurt the target user. Each is
written to be actionable.

1. **Our own output quality is unmeasured — biggest blind spot.** We now know the
   field's artifact cluster (verified, Pass 3): every single-camera markerless
   tool suffers **temporal jitter, foot sliding, and occlusion/depth errors** —
   physics-inherent to monocular capture (PhysCap, SIGGRAPH Asia 2020). What we
   *don't* know is where **PoseCap** sits on that cluster, because we've never
   measured our own output. Worse: MediaPipe-based tools (our CPU fallback's
   family) are reported **worst on raw jitter** (BlendArMocap #121: "really
   jittery… limbs known to be still jitter and jump around"). So this cuts against
   us until measured. Requires the eval harness.
2. **No post-processing / cleanup layer.** Cloud services ship foot-lock,
   physics/stabilization, and confidence filtering. PoseCap applies raw pose.
   For believable results the user currently has to clean up by hand.
3. **Retargeting is SMPL-X-only.** Rokoko/DeepMotion/Move retarget to arbitrary
   rigs, Mixamo, UE5/HumanIK out of the box. PoseCap's non-destructive binding
   (spec 0005) is progress but not yet the mature multi-rig experience rivals
   ship. (Consistent with PRD non-goal, but it *is* a competitive loss.)
4. **Hands and face are not a mature feature.** DeepMotion sells body+hands+face
   (charges 2× for it, but delivers). PoseCap's face/expression is a PRD
   non-goal for now; hands via PEAR are in progress (task 0025). Competitively,
   "body only" is behind.
5. **Multi-person capture — absent.** Move/DeepMotion handle multi-person; PoseCap
   is single-subject.
6. **Hardware gate.** PEAR needs an NVIDIA CUDA GPU. The MediaPipe CPU fallback
   (ADR-0008) narrows this, but the flagship-quality path excludes AMD/Intel/Mac
   users the cloud tools serve from any browser.
7. **Brand, distribution, ecosystem, trust.** Rivals have years of tutorials,
   community, and marketplace presence. A new private repo has none yet — and the
   PRD itself flags distribution as the priority (Dean's read: distribution/UX >
   model quality).

## Prioritized improvement backlog (what this analysis says to build)

Ranked by leverage for the target user, grounded in the losses above:

1. **Build the eval harness and actually measure jitter/foot-sliding/occlusion.**
   Not to gate model swaps (PRD deprioritized that) — to *know our own quality
   position*. We cannot claim quality we haven't measured, and this is the field's
   weakest spot. (Addresses loss #1; PRD "Later" item, but analysis argues it's
   more urgent than positioned.)
2. **Add a cleanup pass — de-jitter + foot/depth stabilization TOGETHER, not
   foot-lock alone.** Pass 3 corrected a natural assumption: foot sliding is *not*
   the standalone #1 artifact. The top complaint is **temporal jitter** (strongest
   evidence: DeepMotion built and monetized a dedicated jitter-smoothing filter;
   loudest user voice is about jitter; every "foot-sliding-is-#1" claim was
   *refuted* in verification). Foot sliding is the most-patched but is consistently
   framed as "easily corrected." Occlusion/depth-drift is the third, rooted in
   monocular depth ambiguity. **Roadmap implication:** treat de-jitter (temporal
   stability) and foot-contact/depth stabilization as one joint cleanup priority.
   A jitter filter is likely the highest-leverage first move. (Loss #2.)
3. **Mature the non-destructive retarget beyond SMPL-X** toward at least one
   common target (Mixamo/Rigify). (Loss #3; builds on spec 0005 / task 0034.)
4. **Ship hands honestly (task 0025), keep face explicitly out** rather than
   faking zeros — matches PRD honesty principle and closes part of loss #4.
5. **Lead the messaging with privacy + free-unlimited + real-time**, the three
   *verified* wins — but never claim quality superiority until #1 proves it.
6. **Publish and seed the ecosystem** (public repo, tutorials) — the PRD's
   stated priority; nothing above matters if nobody can find or trust it.

## Closest functional threat

**Remocapp** — it is the only verified rival doing real-time markerless webcam
capture into Blender at low cost ($9.99–19.99/month, unlimited capture). It beats
PoseCap on polish and multi-camera; PoseCap beats it on price (free), privacy
(local vs their infra+account), and open-source. If Remocapp shipped a free tier
that covered real use, PoseCap's practical edge would narrow to privacy +
open-source.

**Strategic / future threats (verified as roadmap, not shipped):**

* **Autodesk Flow Studio + RADiCAL.** Autodesk acquired RADiCAL's real-time
  single-camera tech (~Apr 2026; getrad.co portal shutting ~2026-07-06) and
  "intends to selectively integrate" it into Flow Studio's roadmap. If shipped,
  it becomes the first **cloud** real-time single-camera competitor — still not
  local, but a well-funded name entering the real-time space. Not a feature today.
* **FreeMoCap going real-time.** Its FAQ says real-time is "being worked on." It
  already shares PoseCap's free+local+open-source DNA; if it adds real-time it
  becomes the most direct open-source rival. No public timeline — the one to watch.
* **A BlendArMocap revival** would directly re-contest the open-source-addon niche.
* **Rokoko or Move bringing real-time down-market** would erase the "only
  real-time accessible tool" lead.

## Answers to the three closing questions

**1. Do the added competitors change PoseCap's positioning? No — it is still
alone on the four-axis intersection (free + real-time + 100% local + native
Blender live-addon).** Verified axis-by-axis: FreeMoCap is free+local+OSS but
offline + import-only + multi-cam; Flow Studio is cloud + freemium + offline
batch + export-only; Move.ai is paid (Move One offline cloud; Move Live real-time
but multi-cam enterprise); MocapNET is real-time+local but proprietary
non-commercial + a BVH exporter, not an addon; Cascadeur is offline, different
category. The closest on *real-time+local* is MocapNET (fails free/OSS and
native-addon); the closest on *free+local+OSS* is FreeMoCap (fails real-time and
native-live-addon). **No tool hits all four.**

**2. The single quality artifact PoseCap must beat — now GROUNDED (Pass 3).** It
is **not** foot sliding. The top-3 is a coupled cluster: **#1 temporal jitter**
(strongest evidence), **#2 foot sliding** (most-patched but "easily corrected";
its primacy claims were refuted in verification), **#3 occlusion / monocular
depth ambiguity** (the physics root cause). Best single-cam quality reputation:
**Move.ai** (which itself concedes multi-cam Pro is where accuracy lives).
Most-panned budget tier: **DeepMotion + Plask**. Worst on raw jitter:
MediaPipe-based tools — including the family of PoseCap's own CPU fallback, which
is a warning, not a comfort. **Roadmap:** de-jitter first, foot/depth alongside.
Aligns with what PoseCap already knows — world position is pelvis-locked *because*
monocular can't recover depth (PRD).

**3. Is FreeMoCap a threat to PoseCap's open-source niche? Not today — it's the
nearest neighbor, not a head-to-head rival.** It is the only other
free+local+open-source webcam mocap tool, but it lives in an adjacent niche:
offline, record-then-process, import-into-Blender, 3+ cameras for good results —
research-grade, not "plug one webcam, capture live inside Blender." It is
complementary more than competitive. **The watch item:** it has publicly
committed to pursuing real-time; if it delivers, it becomes PoseCap's most direct
open-source competitor.

## Coverage gaps & caveats

* **Competitor output quality now grounded (Pass 3); PoseCap's own is not.** The
  field-wide artifact cluster (jitter > foot-sliding > occlusion/depth) is verified
  from primary CV literature + vendor release notes. Residual gaps: **hand/finger
  quality** (only indirect evidence survived), **root-float/sink** (mapped only to
  PhysCap's "shifting in depth", no standalone user complaint), and raw
  forum-voice coverage for Remocapp / FreeMoCap / QuickMagic (QuickMagic's quality
  praise was *refuted*, so unverified). Above all: **how PoseCap itself scores is
  unmeasured** — that is the eval harness (code), not more research.
* **Competitor set now covered (Pass 2).** FreeMoCap, Autodesk Flow Studio,
  Cascadeur, Move Live, and MocapNET are now verified 3-0. Only Open Mocap remains
  *extracted*. "No competitor offers X" now holds across the named field, not just
  Pass 1's subset.
* **Honesty corrections from adversarial verification — do NOT repeat these
  overstatements:**
  * Move.ai *does* have a free tier — Move One, 30 perpetual credits, but it is
    **offline single-camera cloud**. Only "no free *real-time* tier" is true.
  * MocapNET is **not** "no-GPU / CPU-only / 70 fps" — that claim was refuted
    (1-2). Its ~30 Hz is a self-reported single-laptop benchmark that *requires*
    MediaPipe. And it is **not OSS** (non-commercial FORTH license).
  * Cascadeur is **not** "not a mocap tool at all" — that label was refuted (0-3).
    It has offline, weak, file-based video mocap; it's a different category, not
    absent from it.
  * QuickMagic: "no native Blender integration" was **refuted 0-3** (Pass 1) —
    some Blender/BVH path exists; verify directly before asserting.
* **Price volatility.** All prices verified 2026-07-17; SaaS pricing changes
  without notice. Flow Studio tiers are an Aug-2025 SIGGRAPH snapshot. Revalidate
  before any externally published comparison.
* **Rokoko FAQ framing.** Rokoko's "real-time AI mocap is impractical" claim is
  commercially motivated (justifies their hardware) — cited as their position,
  not industry fact.

## Open questions (feed the next research pass)

1. **How does PoseCap's own output score** on jitter / foot-sliding / occlusion vs
   the field cluster? Not a web question — requires the **eval harness** (backlog
   #1), which is code, not research. This is now the #1 unknown.
2. **Hand/finger quality** across tools — only indirect evidence survived Pass 3
   (DeepMotion extended its jitter filter to hands). Hands are the notoriously
   weakest joint; worth targeted research when hands land (task 0025).
3. Will **Autodesk ship RADiCAL's real-time single-camera tech into Flow Studio**,
   and when? Would create the first cloud real-time single-camera competitor.
4. Does **FreeMoCap's "working on real-time" have a public timeline?** Determines
   whether the nearest open-source neighbor becomes a direct threat.
5. Did the **2025 model refreshes** (Move AI Gen 2; Rokoko Vision 3.0 solver)
   materially lower jitter/foot-sliding severity enough to re-order the top three?
6. What exactly is **QuickMagic's Blender/BVH path** (the absence claim was refuted)?

## Related

* [PRD.md](PRD.md) — product scope; several losses here are stated non-goals,
  noted as such.
* [doc/specs/0005-non-destructive-character-binding.md](../specs/0005-non-destructive-character-binding.md) — retarget work (loss #3).
* [doc/specs/0004-offline-video-batch-animation.md](../specs/0004-offline-video-batch-animation.md) — video→animation flow.
* [doc/adr/0008-offer-mediapipe-lite-backend.md](../adr/0008-offer-mediapipe-lite-backend.md) — CPU/non-NVIDIA path (loss #6).

## Sources (primary, verified 2026-07-17)

* Rokoko pricing — https://www.rokoko.com/pricing
* Rokoko Vision 3.0 — https://www.rokoko.com/products/vision
* Rokoko Studio Live for Blender — https://github.com/Rokoko/rokoko-studio-live-blender
* DeepMotion Animate 3D pricing — https://www.deepmotion.com/pricing-animate3d
* QuickMagic pricing — https://www.quickmagic.ai/Pricing/
* Move One pricing — https://docs.move.ai/knowledge/move-one-pricing
* Move.ai capture limits — https://developers.move.ai/docs/limits/
* Plask pricing — https://plask.ai/en-US/pricing
* Remocapp pricing — https://remocapp.com/pricing
* BlendArMocap — https://github.com/cgtinker/BlendArMocap
* FreeMoCap — https://github.com/freemocap/freemocap · docs https://docs.freemocap.org/documentation/multi-camera-calibration.html
* FreeMoCap Blender addon — https://github.com/freemocap/freemocap_blender_addon
* MocapNET — https://github.com/FORTH-ModelBasedTracker/MocapNET (license: non-commercial FORTH)
* Autodesk Flow Studio (ex-Wonder Studio) — https://investors.autodesk.com/news-releases/news-release-details/autodesk-launches-freemium-access-autodesk-flow-studio-new · https://help.wonderdynamics.com/blender-add-on/
* Move.ai developer pricing — https://developers.move.ai/docs/pricing/ · Move Live specs via CG Channel (Jun 2024)
* Cascadeur video mocap — https://cascadeur.com/help/category/203

### Quality / artifact evidence (Pass 3)

* PhysCap (monocular artifact cluster, SIGGRAPH Asia 2020) — https://arxiv.org/pdf/2008.08880
* DeepMotion release notes (6+ anti-foot-gliding fixes; jitter Motion Smoothing) — https://www.deepmotion.com/release-updates
* BlendArMocap jitter report (MediaPipe) — https://github.com/cgtinker/BlendArMocap/issues/121
* Move.ai Gen 2 single-cam ceiling / occlusion — https://www.lessidance.com/post/move-ai-gen-2-vs-xsens-traditional-mocap-killer-or-just-hype-part-1
* DeepMotion single-person capture guidelines (occlusion) — https://www.deepmotion.com/article/single-person-capture-guidelines-for-animate-3d
