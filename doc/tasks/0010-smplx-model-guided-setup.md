# Task 0010: SMPL-X body models — guided, near-automated setup

**Status:** proposed
**Created:** 2026-07-10
**Owner:** alexandremendoncaalvaro
**Execution:** agent + HITL (clean-machine validation)
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

First field feedback from Corridor (Dean, 2026-07-10): Emmet got stuck on the
SMPL-X model step — didn't know where to download or where to put the files,
ended up googling the site on his own. Ale's directive: this needs an
automated alternative, not just better prose.

Hard constraint (PRD Constraints): SMPL-X model files are MPI
research-licensed — the user must accept MPI/Meshcapade terms personally; we
may never bundle, redistribute, or headlessly download them. So "automated"
means: automate EVERYTHING around the one legally-required manual click.

Grounded upgrade (2026-07-10, evening): the MPI download endpoint
(download.is.tue.mpg.de) accepts the USER'S OWN site credentials via POST —
the established pattern used by community and MPI-affiliated projects
(ICON fetch_data.sh, WHAM fetch_demo_data.sh, BUDDI, PyMAF). The user
registers once on smpl-x.is.tue.mpg.de (that registration IS the license
acceptance); everything after that is automatable with their account.

Target flow (wizard, primary path — credential-based):

1. User clicks **Set Up Body Models** (installer final step and/or PoseCap
   panel button when models are missing).
2. Wizard: "Create your free SMPL-X account (opens official page; the site's
   sign-up is where you accept the MPI license) — then enter that email and
   password here."
3. Wizard downloads the pinned model archive(s) with the user's credentials
   directly from the official MPI endpoint (HTTPS, in-memory credentials,
   never persisted, never logged), validates names/sizes/hashes, extracts and
   places files in the engine's expected paths.
4. Doctor check runs automatically and shows green "Models installed".

Fallback path (no credentials typed into our UI): wizard opens the official
download page + a Downloads-folder watcher detects the manual download,
validates, extracts and places it — zero manual file moving either way.

Plus the immediate low-tech half (Dean's ask): an illustrated step-by-step
guide (screenshots of the MPI site, which files, one image of the final
result) in the repo and linked from the installer and the release notes.

## Acceptance Criteria

- [ ] Panel (and installer final page) shows a "Set Up Body Models" action
      whenever the expected model files are absent; it opens the official
      sign-up page and explains that registering there is the license step.
- [ ] Credential path: with the user's MPI account email/password, the wizard
      downloads the pinned archives from the official endpoint and installs
      them end to end; credentials live in memory only — never written to
      disk, settings, or logs; a wrong password yields a friendly retry
      message.
- [ ] Fallback path: folder watcher detects a manually downloaded archive in
      Downloads, validates names/sizes, extracts and installs to the engine's
      expected paths without any manual file operation.
- [ ] Corrupted/wrong download produces a friendly message naming what was
      expected, not a traceback.
- [ ] Doctor check (models present + loadable) runs after install and its
      result is visible in the UI.
- [ ] No model file is ever bundled, redistributed or fetched without the
      user's own action on the official site (license gate preserved).
- [ ] Illustrated guide (with images) lands in doc/ and is linked from the
      installer text and release notes; Dean can forward it as-is.
- [ ] HITL: one clean-machine run by someone who is not us (Dean/Emmet
      re-test) completes the model step without questions.

## Plan

- [ ] Ground: what exactly does the engine/PEAR need from SMPL-X (file list,
      versions, paths) — pin the canonical list with hashes.
- [ ] Ground: how Meshcapade's own Blender addon and comparable tools walk
      users through this step (best-in-class reference).
- [ ] Wizard slice (TDD): missing-model detection + file list UI.
- [ ] Watcher slice (TDD): archive detection, validation, extraction,
      placement, friendly failures.
- [ ] Doctor slice: post-install verification surfaced in the panel.
- [ ] Illustrated guide + installer/release-notes links.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-10

Created from Dean's Discord message (Emmet's install experience) and Ale's
"must be automated" directive, hours after v0.1.2-win.1 shipped. Slotted into
the v0.1.3 slice together with tasks 0008 (remainder) and 0009 — install
friction is the top PRD metric (15-minute clean-machine install) and this is
the step that broke it in the field.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
