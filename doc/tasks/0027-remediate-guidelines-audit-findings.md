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

- [x] `addon/posecap_addon/panels.py` no longer exceeds the §4 caps:
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
- [x] Domain exception hierarchy is consistent per §2.2: `core` raises
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
- [x] Low-severity sweep: abbreviations `obj`/`env`/`seq` renamed (or the §2.1
      exemption list amended by decision), `else`/`elif` occurrences reduced per
      Calisthenics item 2, missing docstrings added on the five exported public
      functions, the three `# type: ignore` comments outside the bpy boundary fixed
      or justified, and the two test files renamed/moved to mirror their source
      modules.
- [x] §5 is amended by a short ADR resolving the conflict between "no per-frame
      allocations / preallocate numpy buffers" and the deliberate immutable-frame
      design (frozen dataclasses, `setflags(write=False)`); either the guideline
      gains the immutability exemption or a buffer-reuse design is decided.
- [x] The git-history debt is recorded, not rewritten: the 51 `Co-Authored-By`
      commits (merge of PR #35) and the two unsigned web-UI commits are documented
      as known exceptions in this task's Notes with the decision on whether a DCO
      remediation commit (precedent: PR #57) is warranted.
- [x] `doc/benchmarks.md` dated-ledger format is either sanctioned by a one-line
      exemption in a binding document or reformatted; the README Roadmap digest is
      either shrunk to a PRD link or accepted as-is by decision.

## Plan

- [x] Slice 1 — mechanical, no behavior change: import-linter contracts, golden
      job-status fixtures, docstrings, type-ignore fixes, test renames.
- [x] Slice 2 — exception hierarchy (`core` first, then engine adapters), with the
      `mediapipe_cli.py` catch narrowed as the observable proof.
- [x] Slice 3 — `panels.py` decomposition (largest risk; fresh-context review
      required per WORKFLOW §10 before merge).
- [ ] Slice 4 — indentation flattening across the eight flagged functions.
- [x] Slice 5 — decisions: §5 amendment ADR, abbreviation exemptions, benchmarks
      exemption, README roadmap, git-history record.

## Notes

### 2026-07-16 — slice 3 landed (panels.py decomposition)

`panels.py` went from 1406 lines to a 143-line aggregator by extracting eight
cohesive modules in the repo's established `build_*_classes(bpy_module)`
pattern (grounded against the official Blender per-module registration idiom
and the node_wrangler / sun_position / Flamenco reference addons):
`stream_properties` (PropertyGroups, protocols, backend choice),
`preferences_panel`, `capture_readiness` (the single source for the
onboarding/poll/execute gates), `stream_session` (session runtime plus the
public `active_stream_session()` accessor), `stream_operators` (Start/Stop and
`engine_command`), `support_panel`, `live_stream_panel`, `main_panel` (public
`draw_main_panel`), and `scene_sync`; `resolve_engine_executable` moved to
`pear_root.py` and `context_wrap_chars` to `panel_text.py`. Registration order
is unchanged (pinned by the registration-order test) and unregistration stays
the exact reverse mirror. The four remaining `else` sites folded into guard
clauses/helpers — the addon package now has zero `else`/`elif` statements.
The `tests/addon/test_ui_state.py` private accesses from AC section 9 migrated
to the new public seams (`draw_main_panel`, `active_stream_session()`,
`context_wrap_chars`); monkeypatch targets moved to the consuming modules.
Verified: full pre-commit and pre-push gates green (pyright Win+Linux, 513
passed), and the headless Blender 5.0.1 e2e smoke green before and after (the
smoke itself caught the first cut's stale `panels.*` seams — fixed by pointing
it at the new modules). Still open under section 9: `test_model_setup.py`
`_urllib_fetch` (rides slice 4) and the `test_pear_adapter.py`
`_load_pear_modules` seam decision.

Fresh-context review (WORKFLOW section 10, two axes) ran before the PR. Spec
axis: no behavior divergence found; one concern — `_ADDON_VERSION` computed in
three modules — fixed by single-sourcing `ADDON_VERSION` in
`preferences_panel.py`. Standards axis: no blockers; size concerns logged and
accepted: `stream_properties.py` (365 lines) is one declarative property table
(justification in its docstring), `stream_operators.py` (271 lines) is
cohesive, and `start_live_stream` (~80 lines, under the 100 hard cap) was
deliberately moved unchanged — shrinking it further belongs to a separate
change, not this behavior-preserving slice. Both reviewers independently
verified registration order and monkeypatch retargets.

### 2026-07-15 — else-reduction landed, section 9 scoped

The eight `else`/`elif` sites outside `panels.py` were refactored to guard
clauses and extracted helpers with behavior preserved (quaternion branch
helpers in `landmark_pose.py`; `continue` guards in `model_assets.py` and
`repack_wheel.py`; status-first yields in both frame sources; `_capture_target`
helper; `_doctor_checks` early-return in `mediapipe_cli.py` — the sequential-if
rewrite of the aspect-ratio clamp is semantics-preserving because the first
branch establishes the equality that makes the second a no-op). Affected suites:
212 passed. The four remaining `else` sites live in `panels.py` and fold into
slice 3's decomposition rather than being touched twice. This completes the
low-severity sweep AC: abbreviations were resolved by the slice-5 exemption,
docstrings, type-ignores, and test renames landed with slice 1.

Section 9 (private-state tests) scoping: the `test_ui_state.py` accesses
(`_draw_main_panel`, `_ACTIVE_SESSION`, `_panel_wrap_chars`) target exactly the
seams slice 3 will redraw — migrating them now would be double work, so they
move with slice 3. The `test_model_setup.py` `_urllib_fetch` access rides
slice 4 (that function is its worst indentation offender). The remaining
`test_pear_adapter.py` monkeypatch of `_load_pear_modules` needs a deliberate
injection-seam decision and stays open under this AC.

### 2026-07-15 — slice 5 decided and landed

All five open decisions were made by the maintainer: (1) ADR-0012 (accepted)
amends GUIDELINES section 5 — frame immutability wins over buffer preallocation;
"no avoidable per-frame work" replaces the preallocation mandate, and any future
buffer-reuse proposal must arrive with frame-time measurements. (2) Section 2.1
exempts the Python idioms `obj`, `env`, and `seq`, closing the two abbreviation
findings without a noisy rename (the `else`-reduction part of the low sweep
remains open with slice 4). (3) Section 11 sanctions `doc/benchmarks.md` as a
dated measurement ledger. (4) The README Roadmap digest shrank to a PRD pointer,
removing the already-diverged duplicate. (5) Git-history debt: the 51
`Co-Authored-By` commits that entered `main` through the PR #35 merge predate
the squash-only rule (verified by the audit's refuted-claims check) and are
recorded here as a historical exception — `main` is never rewritten; the two
unsigned GitHub web-UI commits (`7d88040`, `9bf6ba9`, 2026-07-12 README edits)
were remediated by an empty signed commit on this branch, following the PR #57
precedent.

### 2026-07-15 — slice 2 landed (domain exception hierarchy)

TDD red-to-green: five new tests pinned the domain contract first (missing,
non-finite, and degenerate landmarks raise `PoseCapError`; both frame-source
constructors reject a non-positive read-failure budget with `EngineError`), then
`landmark_pose.py` switched its three `ValueError` raises to `PoseCapError`, the
MediaPipe and PEAR adapters switched constructor/invariant raises to
`EngineError`, and `mediapipe_cli.py` narrowed its edge catch from
`(EngineError, ValueError)` to `(EngineError, PoseCapError)` — the observable
proof that domain code no longer leaks stdlib exceptions. Full core+engine
suites green (139 passed).

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
