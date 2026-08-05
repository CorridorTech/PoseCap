---
name: ad-architecture
description: Generate ARCHITECTURE.md at the repo root by scanning the code first, pre-filling layers/patterns/observability/deployment from observed signals, then asking only the genuine gaps. Use when the user wants to bootstrap, scaffold, generate, document, or audit ARCHITECTURE.md (system-level patterns and boundaries, paired with ADRs in doc/adr/). Covers brownfield (code exists) and audit (drift report against existing ARCHITECTURE.md).
summary: Generate or audit `ARCHITECTURE.md` at the repo root.
allowed-tools: Read, Write, Glob, Grep, Bash
---

# /ad-architecture

Produces `ARCHITECTURE.md` at the repo root. Pairs with ADRs in `doc/adr/` — architecture is the binding pattern; ADRs are individual decisions with status. ADRs in `doc/adr/` with `Status: accepted` are binding; read every one before writing.

## Step 0 — Detect mode

Inspect the repo:

* `ARCHITECTURE.md` exists at the repo root → **audit** mode. **Do not rewrite it.** Stop after producing a drift list (see Step 4).
* `ARCHITECTURE.md` absent → **bootstrap** mode. Scan first, pre-fill, ask only the gaps.

## Step 1 — Scan the code

Read in this order, taking the first that exists for each category:

* Top-level directory listing — infer the layered/hexagonal/clean structure.
* Main entry points — servers (`main.go`, `app/server.ts`, `manage.py`, `cmd/`), CLI binaries, background jobs.
* Boundary code — `handlers/`, `controllers/`, `repositories/`, `gateways/`, `middleware/`.
* Config and env loading.
* Observability hooks — logger setup, metrics export, tracing init.
* Deploy config — `Dockerfile`, `docker-compose.yml`, `k8s/`, `terraform/`, `.github/workflows/`, `Procfile`, `serverless.yml`.
* `doc/adr/` — `doc/adr/` is the canonical ADR ledger. Read accepted ADRs to inform pattern descriptions; do not duplicate the index inside `ARCHITECTURE.md`.

Build a model of: layers and boundaries, data access pattern, HTTP middleware chain, async/messaging, error and validation patterns, naming conventions, logging/metrics/tracing, deployment topology.

## Step 2 — Pre-fill

For every `<placeholder>` in the template below, fill from observed signals. **No fabrication.** If a section has no signal, write `<TODO: not yet wired>` in one line and move on.

## Step 3 — Show only the gaps

Print to the user:

* (a) placeholders without a code signal;
* (b) places where the code shows two competing patterns (some handlers go through middleware, some don't; mixed data-access styles, etc.).

One question per gap.

When the host exposes Plan Mode, the agent may render the proposed `ARCHITECTURE.md` body inside the plan for user approval before write. Plan Mode is opt-in — skip for incremental edits where the user already saw the prior content.

## Step 4 — Write the file

On user confirmation, write `ARCHITECTURE.md` at the repo root. Cut every line that does not lock a binding pattern. At the end of the response, list any decision that should become an ADR — flag, do not write the ADR yet (use the `ad-adr` skill for that).

**Audit-mode override:** do **not** write the file. Produce a drift list. Format each line as:

```
[file or section]: spec says X, code says Y. Suggested resolution: change spec / change code / discuss.
```

If something the user says contradicts what the code shows, surface the conflict. Don't silently trust the user; don't silently trust the code.

## Template — `ARCHITECTURE.md`

````markdown
# Architecture

System-level patterns and boundaries. Pair with ADRs in `doc/adr/` for individual decisions.

## Overview

`<one paragraph: what the system does, key external dependencies, deployment shape>`

## Layers & Boundaries

`<the layered/hexagonal/clean structure: what lives in each layer, what crosses boundaries, what doesn't>`

## Patterns

* **Data access:** `<e.g., Repository pattern; raw SQL only inside `internal/db/`>`
* **HTTP handlers:** `<e.g., all go through middleware in `src/middleware/`>`
* **Async/messaging:** `<e.g., Kafka topics owned by their producer service>`
* **Error handling:** `<e.g., domain errors in `errors/`; HTTP mapping at handler edge>`
* **Validation:** `<e.g., Pydantic at boundary, never inside core>`

## Naming Conventions

`<module/file/class naming rules that aren't obvious from language defaults>`

## Observability

* Logs: `<format, level conventions, where they ship>`
* Metrics: `<library, dashboards>`
* Traces: `<provider, sampling strategy>`

## Deployment Topology

`<how services run in prod: containers, orchestration, scaling rules>`
````

## Output contract

A single `ARCHITECTURE.md` at the repo root. Every line locks a binding pattern. ADR candidates flagged in the response, not written. In audit mode: drift list only, no file written.

`ARCHITECTURE.md` is a narrative document, so the Documentation Discipline rules in `WORKFLOW.md` §2 apply at write time:

- No emoji anywhere in the file.
- No dates, version stamps, `DRAFT` markers, or changelog blocks. Architecture is the current binding pattern; the lifecycle of "when did this become true" lives in ADRs and git history.
- `Overview` is the business-context-first paragraph — *what the system does* and *what would break without it* before layers and patterns.
- One scope: system-level patterns and boundaries. Per-decision rationale lives in ADRs; per-project operations live in `AGENTS.md`. Link, do not copy.
- No speculation. If a layer has no observed signal, write `<TODO: not yet wired>` once; do not propose patterns that aren't already in the code.

## Next

- `/ad-spec` when starting a feature whose scope spans the patterns this document records.
- `/ad-adr` for any binding decision that surfaced while writing or auditing this file (one decision per ADR).
- `/ad-drift` periodically to check pattern drift between this document and the code.
