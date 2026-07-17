# Task 0017: Harden contribution governance

**Status:** done
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

- [x] Pull requests into `main` require the sole code reviewer's explicit merge
      decision, resolved threads, a green required CI result, and valid DCO sign-offs;
      force-pushes and deletion of `main` are blocked.
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
- [x] A protected release workflow builds the distributable surfaces, verifies the
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
- [x] Apply repository security, Actions, merge, environment, and ruleset settings
      through GitHub's API after their referenced checks exist.
- [x] Run the local CI mirror, inspect remote checks, complete `/ad-review`, and
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

Active ruleset `18852724` now protects `main` with squash-only linear history, one
CODEOWNER approval from someone other than the last pusher, stale-review dismissal,
resolved threads, strict `CI required`, CodeQL error/high-severity gating, and blocks
on deletion and force-push. It has no administrative bypass actors.

PR #37 publishes the signed implementation history. GitHub observed `CI required`,
DCO, Linux/Windows gates, package smoke, dependency audit, workflow
security, licensed-binary scan, and both CodeQL language analyses passing under the
active ruleset. The PR remains blocked for the independent CODEOWNER decision.

Alê decided that he is currently the sole code reviewer; Dean is not a programmer and
does not perform technical reviews. GitHub cannot record an approval from a PR's own
author, so the ruleset no longer requires an impossible independent approval. The
maintainer's squash-merge action records the review decision while CI, DCO, CodeQL,
resolved-thread, linear-history, deletion, and force-push controls remain mandatory.

### 2026-07-17 — closed by registry hygiene verification

The remaining criterion — the protected release workflow — is now
demonstrably satisfied. `.github/workflows/release.yml` triggers only on
`v*-win.*` tag pushes and manual `workflow_dispatch`, so no untrusted fork
code reaches the release runner; it builds the installer, extension, and
backend payloads, verifies the draft asset inventory before publication, and
publishes SHA-256 sidecars plus GitHub artifact attestations (commits
`f389e12`, `226286e`, `3f482db`). Protected runs completed end to end and
produced the published stable releases `v1.0.6-win.3` (run 29388916869) and
`v1.0.6-win.4` (run 29434488085), each with all 12 artifacts, checksums, and
attestations independently verified (task 0026 Notes, 2026-07-15). The
maintainer's unsigned-Windows-distribution decision (task 0026 Notes,
2026-07-14) removed Authenticode from the release gate, so signing is
intentionally not part of this criterion. Status flipped to done.

### 2026-07-17 — precision note on the release-workflow evidence

Clarifying the previous entry after review: the `release.yml` "Verify draft
release asset inventory" step is a filename-inventory verification, not a
functional installer run. The functional verification of the installer was
the human-driven GUI qualification recorded in task 0026 (`v1.0.6-win.3`);
the `v1.0.6-win.4` evidence is workflow-run completion with artifacts,
checksums, and attestations, not an independent functional re-verification.
The criterion stands on that combined evidence; the workflow alone does not
functionally verify the installer.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
