# Task 0017: Harden contribution governance

**Status:** in-progress
**Created:** 2026-07-12
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:**
**Board ref:**

## Context

PoseCap now receives external contributions and publishes a Windows installer, but
the GitHub repository does not yet enforce the standards already documented in
`AGENTS.md`, `GUIDELINES.md`, and `CONTRIBUTING.md`. A red check, unsigned
contribution, unresolved review, mutable Action, leaked secret, or manually built
release can currently cross a human-only gate. This task converts those expectations
into observable repository controls while keeping small documentation contributions
easy to submit.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] Pull requests into `main` require one independent approval, resolved threads,
      a green required CI result, and valid DCO sign-offs; force-pushes and deletion
      of `main` are blocked.
- [x] GitHub Actions run with explicit least privilege, immutable Action SHAs,
      concurrency cancellation, bounded timeouts, Python 3.11, workflow linting, and
      the existing Linux/Windows quality gates.
- [x] Contributor-facing PR and issue forms collect purpose, reproduction context,
      test evidence, licensing/security routing, and human accountability for any
      agent-assisted contribution.
- [x] `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`, and
      `CODEOWNERS` define the current contribution, vulnerability, support, conduct,
      and ownership paths without duplicating binding engineering rules.
- [x] Dependabot, vulnerability alerts/security updates, secret scanning and push
      protection, CodeQL, private vulnerability reporting, and OpenSSF Scorecard are
      enabled or exercised through committed configuration.
- [ ] A protected release workflow builds the distributable surfaces, verifies the
      installer, publishes checksums and artifact attestations, and never executes
      untrusted fork code on the release runner.
- [x] GitHub repository merge settings use squash-only history, conventional PR
      titles, automatic head updates, auto-merge, and branch deletion after merge.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] Add a public DCO checker under `tools/` with behavior tests and wire it into
      local hooks and `.github/workflows/ci.yml`.
- [x] Harden `.github/workflows/ci.yml`; add workflow static analysis, dependency
      automation, CodeQL/Scorecard, and a stable required-check aggregator.
- [x] Add `.github` PR/issue forms, `CODEOWNERS`, and the repository community and
      security policy files.
- [x] Add a protected release workflow that builds PyTorch3D on the controlled
      Windows/CUDA runner before assembling and signing the installer.
- [ ] Apply repository security, Actions, merge, environment, and ruleset settings
      through GitHub's API after their referenced checks exist.
- [ ] Run the local CI mirror, inspect remote checks, complete `/ad-review`, and
      publish atomic signed commits through a pull request.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-12

The four-source `/ad-ground` audit compared GitHub and OpenSSF guidance, Ruff,
Pydantic, pytest, the PoseCap repository, its remote settings, and git history. It
found a strong test signal but no ruleset, no branch protection, mutable Actions,
disabled security features, no contribution templates, and no release provenance.
The accepted happy path is to enforce the existing standards with a low-friction
squash-only contribution flow. GPU, Blender, and licensed-asset execution remains
restricted to reviewed code in a protected release environment; external fork code
must never run on a persistent release runner.

Repository settings now enforce squash-only merges, web DCO, immutable selected
Actions, automatic branch updates and deletion, vulnerability alerts and fixes,
private vulnerability reporting, CodeQL default setup, secret scanning, and push
protection. The `release` environment requires a different reviewer from its
initiator. GitHub left non-provider secret patterns and validity checks disabled on
the current plan; standard secret scanning and push protection are active.

The local CI mirror passed Ruff, format, both Pyright platforms, import-linter, 387
tests, Markdown links, actionlint, zizmor, and pip-audit with no known
vulnerabilities. The release workflow is committed and protected, but exercising it
still requires a dedicated Windows/CUDA runner and a trusted Authenticode
certificate installed on that runner; neither credential nor machine belongs in the
repository.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
