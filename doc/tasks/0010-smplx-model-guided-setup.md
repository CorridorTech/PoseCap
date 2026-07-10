# Task 0010: SMPL-X body models — guided, near-automated setup

**Status:** in-progress
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

- [x] Panel (and installer final page) shows a "Set Up Body Models" action
      whenever the expected model files are absent; it opens the official
      sign-up page and explains that registering there is the license step.
- [x] Credential path: with the user's MPI account email/password, the wizard
      downloads the pinned archives from the official endpoint and installs
      them end to end; credentials live in memory only — never written to
      disk, settings, or logs; a wrong password yields a friendly retry
      message.
- [x] Fallback path: folder watcher detects a manually downloaded archive in
      Downloads, validates names/sizes, extracts and installs to the engine's
      expected paths without any manual file operation.
- [x] Corrupted/wrong download produces a friendly message naming what was
      expected, not a traceback.
- [x] Doctor check (models present + loadable) runs after install and its
      result is visible in the UI.
- [x] No model file is ever bundled, redistributed or fetched without the
      user's own action on the official site (license gate preserved).
- [x] Illustrated guide (with images) lands in doc/ and is linked from the
      installer text and release notes; Dean can forward it as-is.
- [ ] HITL: one clean-machine run by someone who is not us (Dean/Emmet
      re-test) completes the model step without questions.

## Plan

- [x] Ground: what exactly does the engine/PEAR need from SMPL-X (file list,
      versions, paths) — pin the canonical list with hashes.
- [x] Ground: how Meshcapade's own Blender addon and comparable tools walk
      users through this step (best-in-class reference).
- [x] Wizard slice (TDD): missing-model detection + file list UI.
- [x] Watcher slice (TDD): archive detection, validation, extraction,
      placement, friendly failures.
- [x] Doctor slice: post-install verification surfaced in the panel.
- [x] Illustrated guide + installer/release-notes links.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-10

Created from Dean's Discord message (Emmet's install experience) and Ale's
"must be automated" directive, hours after v0.1.2-win.1 shipped. Slotted into
the v0.1.3 slice together with tasks 0008 (remainder) and 0009 — install
friction is the top PRD metric (15-minute clean-machine install) and this is
the step that broke it in the field.

### 2026-07-10 (implementation, v0.1.3 slice)

Ground pass (four sources) pinned the download mechanics: the official
endpoint is `download.is.tue.mpg.de/download.php?domain=<site>&sfile=<file>`
with the user's credentials POSTed url-encoded — the pattern used by ICON
fetch_data.sh, PIXIE fetch_model.sh, DECA fetch_data.sh and WHAM. Three MPI
accounts are required (smpl / smpl-x / flame — MPI accounts are per-site);
the guide instructs same email + password on all three so the wizard asks
once. File-to-source map: `SMPL_python_v.1.1.0.zip` (smpl) contains the
neutral pkl renamed to `SMPL_NEUTRAL.pkl`; `SMPLX_NEUTRAL_2020.npz` (smplx)
is a direct file; `FLAME2020.zip` (flame) yields `generic_model.pkl` placed
at both FLAME and SMPLX paths. `smpl_mean_params.npz` is NOT hosted by MPI
anywhere (origin: SPIN's public research data) — fetched from a pinned
public HuggingFace revision, sha256-enforced (verified identical to the
local known-good copy: 6fd6dd68…, 1310 bytes). Deviation from "everything
from MPI" recorded and justified in the manifest docstring.

Built TDD (36 new tests): shared manifest in `contracts/model_assets.py`
(doctor now derives its licensed-asset check from it — single source of
truth); addon `model_setup.py` (credential install pipeline, Downloads
watcher, doctor verification, all failures user-facing); `model_setup_panel.py`
(Body Models section, WindowManager-held credentials — never saved to
.blend, cleared on start, redacted from repr). Illustrated guide at
doc/guides/smplx-model-setup.md with SVG illustrations (browser screenshot
capture was unavailable this session; swapping in real site screenshots is
an open nice-to-have). Installer final text now points at the panel wizard
and the guide instead of a manual file list.

Open: HITL clean-machine re-test by Dean/Emmet (AC), and the panel
screenshot for the release notes.

### 2026-07-10 (field results, Corridor — Dean/Emmet via Discord)

Emmet completed the MANUAL model setup successfully on his machine: engine
doctor reported `"ok": true`, `pear_assets` ok; the v0.1.3-win.1 installer
is confirmed in the field (`%LOCALAPPDATA%\PoseCap\{runtime\venv, pear}`).
Expected warns appeared and are by-design: `pear_checkout` (installed PEAR
tree has no `.git`, so the revision cannot be git-verified) and `hf_weights`
(pose-model weights not downloaded until the first Start Stream).

Field UX findings folded back into the slice (→ v0.1.3-win.2):
1. First Start Stream downloads the pinned PEAR pose weight
   (`ehm_model_stage1.pt`, ~2.7 GB) with no feedback — the panel sits on
   "Starting" for minutes and a non-technical user thinks it hung. Fix: after
   ~10 s in STARTING the panel status becomes an explicit first-run-download
   message (no main-thread block, no fake detection). A cleaner seam (engine
   emitting a JSON progress event before `hf_hub_download`) would change the
   wire format and needs an ADR — deferred, not improvised.
2. The `hf_weights` doctor warn used CLI-speak ("rerun doctor with
   --download-weights") and reached an end user through the PoseCap Doctor
   shortcut, causing real confusion. Reworded to plain language.
3. SMPL zip member pin (`archive_member_suffix`) was an exact filename; Ale's
   local `SMPL_NEUTRAL.pkl` is 109 MB (300-shape-component variant), so the
   in-zip neutral member name may differ. Match hardened to any member whose
   basename contains "neutral" and ends ".pkl" (case-insensitive).

Items 1-4 above built TDD and committed (v0.1.3-win.2 slice). Doctor warn,
tolerant SMPL member match, and the first-run-download panel hint all landed
with tests; the PoseCap e2e smoke (register/unregister/apply) passed on the
real Blender 5.0.

Smoke test — official SMPL-X add-on spawn → Start Stream (Item 5): NOT RUN.
The official MPI SMPL-X Blender add-on is not installed on this machine
(`extensions/user_default/` has only `posecap`), and the add-on download is
license-gated behind Ale's MPI account, so it was not auto-installed. The
claim made to Dean ("a body spawned by the SMPL-X add-on works directly as
Target Armature") is therefore STILL UNVALIDATED end to end. The illustrated
guide deliberately does NOT cite the SMPL-X-add-on route as an easy path.
Flagged to Ale; run this once locally with the add-on installed before that
claim goes into any release note.

Guide screenshots: real MPI-site captures need Ale's logged-in browser (the
in-app browser timed out on these pages and Claude-in-Chrome is not
connected); the guide ships with SVG illustrations meanwhile.

(Correction to the numbered list above: it has three items, 1-3; "items 1-4"
was a miscount — read it as "items 1-3 plus the guide work".)

Fresh-context /ad-review of the win.2 delta (two axes) found no Blockers;
two convergent Concerns on the tolerant member match were fixed before ship:
(a) a "." token is now an extension SUFFIX check, so ".pkl" never matches
"model.pkl.bak"; (b) an archive with more than one member matching the
tokens now raises a friendly ModelSetupError instead of silently taking the
first. The first-run panel hint was reworded so it is not false on a later
slow start (GPU init / cold cache) after the one-time weight download:
"Still starting — this can take a few minutes; the very first run also
downloads the AI model (~2.7 GB)." Logged Notes (not fixed): the ~2.7 GB
figure is duplicated across doctor / panel / guide with no shared constant
(the guide is markdown and cannot import one); the STARTING-hint clock is
injected via a private `_now` module seam rather than the constructor.

### 2026-07-10 (field friction — Emmet, clean v0.1.2 install, ~18:07)

On a clean install, clicking Start Stream with a freshly installed panel
raised "Start failed: PEAR Root is required" — the user had typed nothing.
`addon/posecap_addon/panels.py` `_engine_command` only resolved
`settings.pear_root` → `preferences.pear_root` and errored when both were
empty, even though the installer knows the paths (Emmet's:
`C:\Users\Corridor\AppData\Local\PoseCap\pear` and
`...\PoseCap\runtime\venv\Scripts\posecap-engine.exe`).

Ground (read, not assumed): the doctor resolves the checkout from the
`POSECAP_PEAR_ROOT` env var (`engine/src/posecap_engine/doctor.py`), but the
installer does NOT persist that env var — the "PoseCap Doctor" Start Menu
shortcut passes `--pear-root '{app}\pear'` explicitly (`posecap.iss.template`
line 52), and the bootstrap runs doctor with an explicit `--pear-root` flag
(`bootstrap_install.ps1` line 179). Install dir is Inno `{localappdata}\PoseCap`.

Fix (addon-only, TDD): `_engine_command` now resolves PEAR Root by
explicit-value → `POSECAP_PEAR_ROOT` env (if the dir exists) →
`%LOCALAPPDATA%\PoseCap\pear` (if it exists); and the engine launcher by
explicit-existing-path → `%LOCALAPPDATA%\PoseCap\runtime\venv\Scripts\posecap-engine.exe`
(the app-local venv exe is not on PATH, so the old "posecap-engine" default
could never have launched a real install) → bare "posecap-engine". The error
fires only when nothing resolves and now says where to fill it in.

Decision on installer env-var persistence (task step 3): NOT adding `setx`
to the bootstrap. The `%LOCALAPPDATA%\PoseCap` fallback deterministically
fixes both future installs AND already-made v0.1.2 installs (Emmet's) with
zero installer change; a persisted env var adds surface (per-user scope,
uninstall cleanup, leak into unrelated processes) for redundancy the
fallback already covers. Env-var READ support is kept for free in case a dev
sets it.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [x] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
