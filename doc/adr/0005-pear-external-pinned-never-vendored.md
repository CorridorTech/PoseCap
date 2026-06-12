# ADR-0005: Keep upstream PEAR external and pinned, never vendored

**Status:** accepted
**Date:** 2026-06-11
**Deciders:** Ale (alexandremendoncaalvaro), Dean (Corridor Digital)

## Context

The POC vendored the entire PEAR research repository, including MPI-licensed body-model assets (SMPL-X, FLAME, MANO — a 1.26 GB FLAME texture among them). This repo is public-history-by-design: licensed material can never be committed, even transiently. PEAR's own code license is still unverified (open PRD question), and its model weights download from HuggingFace (`BestWJH/PEAR_models`) at runtime. The engine bridge needs PEAR's EHM pipeline but the repo must stay distributable.

## Decision

We will never vendor PEAR source or assets into this repository. The engine bridge imports PEAR from an external location installed by the environment setup at a pinned git revision; model weights download at first run from a pinned HuggingFace revision with `weights_only=True`. The bridge wraps PEAR behind the engine-side adapter so the rest of the system never imports PEAR directly.

## Consequences

* The repo stays license-clean and small; the public flip needs no history surgery.
* Upstream PEAR changes are explicit pin bumps with review, not silent drift.
* Environment setup requires network access to fetch PEAR and weights — the installer must handle fetch failure with actionable messages (setup-simplicity tradeoff).
* A pinned revision can rot if upstream moves or disappears; mitigation is the pin itself (reproducible as long as the source exists) plus the adapter boundary that keeps a backend swap contained (ADR-0001).
* PEAR's license verification remains a release blocker tracked in the PRD — this decision contains the risk but does not resolve it.

## Alternatives Considered

* Vendor PEAR into the repo (POC approach) — license contamination of public history, gigabytes of weight, unverified upstream terms baked in; rejected outright.
* Public fork of PEAR under our control — same license problem plus permanent maintenance of research code we do not own.
* Reimplement the inference pipeline — removes the dependency entirely but is far out of MVP scope; the adapter boundary keeps this option open later.
