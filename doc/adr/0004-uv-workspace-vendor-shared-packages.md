# ADR-0004: uv workspace with build-time vendoring into the extension wheel

**Status:** accepted
**Date:** 2026-06-11
**Deciders:** Ale (alexandremendoncaalvaro), Dean (Corridor Digital)

## Context

Shared code must run in two Python interpreters that cannot share an environment: Blender's bundled Python (the addon, which cannot pip-install) and the engine bridge's venv. The POC solved this with three divergent copies of ~200 identical preprocessing lines — the copy-paste drift this rewrite exists to kill. Blender's extension platform supports bundling wheels inside the extension package, which gives a sanctioned path for shipping shared code into Blender.

## Decision

We will manage the repo as a uv workspace with `contracts/`, `core/`, and `engine/` as members, `pyproject.toml` as the source of truth, and `uv.lock` committed. The extension build script packages `contracts/` and `core/` as wheels and vendors them into the addon zip, so Blender's interpreter and the engine venv consume the same single source. The addon installs through Blender's extension system, not directory junctions.

## Consequences

* One definition of every wire format and domain type; drift between addon and engine becomes structurally impossible instead of review-policed.
* `uv sync` plus the lockfile is the reproducible-install story the setup-simplicity tradeoff (GUIDELINES.md) demands.
* Installing the addon from source requires running the build script first — raw checkout is not directly installable into Blender.
* Changes to `contracts/` or `core/` require an extension rebuild to reach Blender; the build script owns staleness detection.

## Alternatives Considered

* Single copy inside the addon, engine imports via path manipulation — couples the engine to the addon's internal layout and to Blender's packaging; inverted dependency direction.
* Two copies kept in sync by contract tests — drift detection instead of drift prevention; permanent maintenance tax.
* pip-installing shared packages into Blender's Python — fragile across Blender updates, fights the extension sandbox model, fails the install-on-first-try tradeoff.
