# Task 0027: Remediate the GUIDELINES audit findings

**Status:** in-progress
**Created:** 2026-07-15
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:**
**Board ref:**

## Context

A full repository audit ran on 2026-07-15 against `main` (`ff4be83`): every item of
every `GUIDELINES.md` section was audited against the code by one agent per section,
and every reported violation was independently challenged by an adversarial verifier
before acceptance. 84 items were audited; 24 violations survived verification and 6
were refuted. Sections 8 (Quality Gates) and 12 (Security) were fully clean, and the
hexagonal dependency rule holds in the code itself. The surviving findings cluster
into the work below. A parallel docs-drift audit was reconciled separately (AGENTS.md
stack/layout/ADR digest, spec 0002 status, tasks 0004/0006 status).

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] `addon/posecap_addon/panels.py` no longer exceeds the §4 caps:
      `_build_blender_classes` (378 lines) is decomposed below the 100-line hard cap
      and the file (1406 lines) is split toward the ~200-line target, or any function
      that genuinely cannot shrink carries the §4 one-line justification comment.
- [ ] The eight functions exceeding indentation depth 3 (worst: `_urllib_fetch` in
      `addon/posecap_addon/model_setup.py:547`, depth 5) are flattened with guard
      clauses or extracted helpers.
- [x] import-linter enforcement matches the §1 promise: contracts for
      `posecap_engine` (inward-only imports) and the addon layer (no
      `posecap_engine`, no `torch`) exist and run in CI, and the `contracts/`
      contract rejects any non-stdlib third-party import rather than a fixed
      forbidden list.
- [ ] Domain exception hierarchy is consistent per §2.2: `core` raises
      `PoseCapError` subclasses (not bare `ValueError`) in `landmark_pose.py`, engine
      adapters raise `EngineError` subclasses for constructor validation, and
      `mediapipe_cli.py` no longer needs to catch stdlib `ValueError` from domain
      code.
- [x] The job-status wire format is pinned by golden JSON fixtures under
      `tests/contracts/fixtures/`, mirroring the pose-frame fixtures, so a
      coordinated encode/decode change cannot slip through round-trip tests.
- [ ] Tests reach behavior through public interfaces per §9: the private-state
      accesses in `tests/addon/test_ui_state.py`, `tests/addon/test_model_setup.py`
      and `tests/engine/test_pear_adapter.py` are migrated to public seams, or the
      seams are promoted and documented.
- [ ] Low-severity sweep: abbreviations `obj`/`env`/`seq` renamed (or the §2.1
      exemption list amended by decision), `else`/`elif` occurrences reduced per
      Calisthenics item 2, missing docstrings added on the five exported public
      functions, the three `# type: ignore` comments outside the bpy boundary fixed
      or justified, and the two test files renamed/moved to mirror their source
      modules.
- [ ] §5 is amended by a short ADR resolving the conflict between "no per-frame
      allocations / preallocate numpy buffers" and the deliberate immutable-frame
      design (frozen dataclasses, `setflags(write=False)`); either the guideline
      gains the immutability exemption or a buffer-reuse design is decided.
- [ ] The git-history debt is recorded, not rewritten: the 51 `Co-Authored-By`
      commits (merge of PR #35) and the two unsigned web-UI commits are documented
      as known exceptions in this task's Notes with the decision on whether a DCO
      remediation commit (precedent: PR #57) is warranted.
- [ ] `doc/benchmarks.md` dated-ledger format is either sanctioned by a one-line
      exemption in a binding document or reformatted; the README Roadmap digest is
      either shrunk to a PRD link or accepted as-is by decision.

## Plan

- [x] Slice 1 — mechanical, no behavior change: import-linter contracts, golden
      job-status fixtures, docstrings, type-ignore fixes, test renames.
- [ ] Slice 2 — exception hierarchy (`core` first, then engine adapters), with the
      `mediapipe_cli.py` catch narrowed as the observable proof.
- [ ] Slice 3 — `panels.py` decomposition (largest risk; fresh-context review
      required per WORKFLOW §10 before merge).
- [ ] Slice 4 — indentation flattening across the eight flagged functions.
- [ ] Slice 5 — decisions: §5 amendment ADR, abbreviation exemptions, benchmarks
      exemption, README roadmap, git-history record.

## Notes

### 2026-07-15 — slice 1 landed (mechanical enforcement and hygiene)

import-linter gains the `engine imports inward only` contract (3 contracts kept,
0 broken). The addon layer and the contracts stdlib-allowlist could not become
import-linter contracts — the addon package is not installed in the workspace
venv, so grimp cannot import it, and a forbidden-list cannot prove "stdlib
only" — so both are enforced by `tests/test_import_boundaries.py`, a
deterministic AST scan running in the same CI gate. This is a recorded deviation
from the AC's letter that satisfies its intent (every layer machine-enforced,
none by review memory). Job-status golden fixtures pin the wire format
(`tests/contracts/fixtures/job_status_{running,failed}.json`). Docstrings added
on `ue_preset`, `mixamo_preset`, `LimbFilter.is_active`,
`LandmarkPoseConverter.convert`. All three out-of-boundary `# type: ignore`
comments were removed by real typing fixes (`**kwargs: Any`; `HTTPError` built
with `email.message.Message()` and `BytesIO`). The two test files were
renamed/moved to mirror their source modules.

### 2026-07-15 — audit provenance

Full findings with file:line evidence and verifier verdicts are preserved in the
audit session transcript; the summarized breakdown is: 2 high (both
`panels.py` size caps), 10 medium (enforcement gap, exceptions, indentation,
per-frame allocations, job-status fixture, private-state tests, git trailers/DCO),
12 low. Refuted-by-verifier claims (6) were discarded and are not part of this task.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
