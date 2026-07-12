# Task 0013: End-to-end tutorial — setup.exe install → working stream, with real media

**Status:** in-progress
**Created:** 2026-07-11
**Owner:** alexandremendoncaalvaro
**Execution:** agent (drive real Blender + installer) + HITL (Ale does account/password)
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md · supersedes the SVG-mockup guide doc/guides/smplx-model-setup.md

## Context

Ale wants a **complete, guided tutorial suite** proving PoseCap works for a
non-technical user from a **clean machine**: run the Windows installer, onboard,
download the licensed models, convert a Mixamo character, and drive it live from
a video with the preview window — captured as **real media** (screenshots, GIFs,
a demo video), not mockups. A general "install → working" tutorial plus
feature-specific tutorials. Enabling code fixes already landed (below).

## Acceptance Criteria

- [x] The tutorial STARTS from `setup.exe` — the Inno installer wizard (License →
      Destination → Ready → Installing → Finish), captured. (Ale flagged this as a
      hard requirement; do not skip the installer.)
- [x] General tutorial `doc/guides/getting-started.md`: clean install → onboarding
      checklist → model setup (download) → Mixamo convert → live test — end to end.
- [x] Feature tutorials: model setup (replaces `smplx-model-setup.md`, new
      checklist+wizard UI, progress bar), character setup (Mixamo import + Convert),
      live capture (video source + preview + Start Stream + record).
- [x] Real media: PNG screenshots in `doc/guides/images/`, GIF of the money-shot
      in `doc/media/`. Each step shows the next action + the resulting state. The
      raw demo video (`Ale-PoseCAp.mp4`, 134 MB, a personal clip) is **not**
      committed — `.gitignore` blocks `*.mp4` outside test fixtures and the repo
      goes public; the captured `posecap-live-capture.gif` is the shipped payoff.
- [x] HITL end-to-end: models download for real (progress bar), Mixamo `Y Bot.fbx`
      converts, and the stream on `Ale-PoseCAp.mp4` drives the converted armature
      with the preview window visible — money-shot GIF captured.

## Enabling fixes (already landed this session)

- [x] `9f9f51f` task 0012 — Getting Started checklist + guided model-setup dialog.
- [x] `443fbd2` **cookie fix** — the credential download NEVER worked: `download.php`
      sets a session cookie + 302-redirects to the file; urllib dropped the cookie →
      HTML login page. Fixed with `HTTPCookieProcessor` (root-caused live). Also:
      download **progress bar** (`layout.progress`), **Start Stream/Record gated**
      until onboarding complete + hint, ✓/error completion icons.
- [x] `5d054b7` test robustness (session join cap 60s for slow CI). CI green.
- [x] **win.7 installer built** with the fixes: `packaging/dist/PoseCap_v0.1.3-win.7_Windows_Setup.exe`
      (21.8 MB, sha256 DEE03FAFB7D7DD7957593B338DF06F37244DE670DC65029056F4E070CE959AF1;
      cookie fix verified inside the bundled extension zip).

## Plan

- [ ] Uninstall the current PoseCap (clean machine): `%LOCALAPPDATA%\PoseCap\unins000.exe //VERYSILENT`,
      then remove residual `%LOCALAPPDATA%\PoseCap` + the Blender extension
      (`.../Blender/5.0/extensions/user_default/posecap` + vendored `posecap_*`).
- [ ] Install from `PoseCap_v0.1.3-win.7_Windows_Setup.exe`; capture each wizard screen.
- [ ] Blender → onboarding checklist → Set Up wizard → real download (progress bar).
- [ ] Mixamo `Y Bot.fbx` → Target Armature → Convert Character for PoseCap.
- [ ] Source = Video File `Ale-PoseCAp.mp4`, Preview on, Start Stream → capture.
- [ ] Author the `.md` tutorials + assemble media (ffmpeg for GIFs).

## Notes

Append-only. Date each entry.

### 2026-07-11 — Created + enabling fixes landed

Split out of the task 0012 HITL when the end-to-end run exposed the cookie bug.
Fixes above landed + CI green + win.7 built. Full media production handed off to a
fresh session (context budget) — handoff doc carries the machine state, GUI-driving
tips, media asset paths, and the security constraint.

**SECURITY (binding):** the agent must NOT create accounts nor type passwords —
those are Ale's steps (he registers/confirms on the 3 MPI sites and types the
password in the wizard; the agent clicks OK with his per-action permission). Never
put the real password in any tutorial artifact — placeholders only; never film the
password field. Ale's accounts (`ale.corridor@gmail.com`) are registered + confirmed
on SMPL / SMPL-X / FLAME. Registration screenshots (showing the all-3 requirement +
the spam-confirmation gotcha) are at `C:\Users\alexa\Downloads\Register\`.

### 2026-07-11 — Media run: install + onboarding + convert verified; 2 usability bugs fixed; SMPL download bug open

Real-media run from win.7. Verified live in real Blender:
- Clean uninstall + install from `PoseCap_v0.1.3-win.7_Windows_Setup.exe`; five wizard
  screens captured (License → Destination → Ready → Installing → Finish). Doctor after
  install: everything green except the licensed `pear_assets` (expected).
- Onboarding checklist + Set Up wizard + credential download **progress bar** — the bar
  renders live ("Downloading SMPL…zip — N/315 MB"); the cookie fix downloads for real.
- Character convert: Mixamo `Y Bot.fbx` → Target Armature → Convert → "Character
  converted (Mixamo) — probe error 0.0000".

Two usability bugs surfaced by the run and fixed (branch
`fix/panel-truncation-and-installer-encoding`, full gate green, fresh-context review in
flight):
- **Panel text truncation** — Blender labels don't wrap, so the narrow N-panel
  middle-truncated status/error text ("The downloaded …m the official site.") and
  squeezed the checklist label ("Install the bo…"). Added `panel_text.py`
  (wrap_lines / draw_wrapped_label / region_wrap_chars); checklist label full-width with
  CTA below; status/error/hint wrap. Verified live. (commit `ad2bece`)
- **Installer StatusMsg mojibake** — UTF-8 em-dash read as ANSI by PS 5.1 baked `â€"`
  into the compiled installer. Template → ASCII `--`; build reads `-Encoding UTF8`.
  (commit `c2cc3ad`)

**OPEN — SMPL credential download extraction bug (blocks money-shot):** the credential
download fetched the full `SMPL_python_v.1.1.0.zip` (valid, non-HTML) but `_extract_member`
found the wrong number of `("neutral", ".pkl")` members (0 or >1 — the two error strings
both truncate to "…from the official site."). Grounded: request params are correct
(`domain=smpl&sfile=SMPL_python_v.1.1.0.zip`) and the *standard* zip has exactly one
matching neutral, so the real download differs from standard. Root-cause needs the real
archive's member list; awaiting a browser download of the zip to inspect + fix for real
(no workaround, no POC-asset copy — Ale's directive). Security held: declined to store
Ale's pasted password; password stays in Ale's hands (masked wizard field) or the
Watch-Downloads path.

### 2026-07-11 — SMPL download root-caused + fixed; blocked on MPI IP rate-limit

Drove the real credential download to root-cause (no workaround, no POC-asset copy).
Two real bugs found + fixed (branch `fix/panel-truncation-and-installer-encoding`,
full gate green, commits `93284f5`, `36d4f19`; plus the review-driven panel hardening):

- **Magic-byte check too strict (the real "does not look like SMPL_NEUTRAL.pkl"):**
  extraction found the neutral member fine (tokens correct), but validation rejected
  it because `.pkl` magic only accepted `\x80` (pickle protocol 2+). SMPL ships the
  neutral as a **protocol-0** pickle (opens with `(` — confirmed against the POC's
  `SMPL_NEUTRAL.pkl`). Broadened the pickle magic; regression-tested with the real
  protocol-0/2 byte signatures.
- **Misleading refusal error:** a 403 (`HTTPError`, a `URLError` subclass) was reported
  as "Could not reach the download server. Check your internet connection." Now 401/403
  names the real causes (credentials / unconfirmed account / rate-limit).
- Panel hardening from the fresh-context review: lifecycle status line + progress-bar
  text + Set Up dialog now wrap (dialog widened); `wrap_lines` keeps long filenames
  whole; `models_missing("")` no longer falsely ticks models-installed.

**BLOCKED (external, not a bug):** after ~3-4 download attempts today, MPI's
`download.is.tue.mpg.de` **IP-blocked this machine** — every request now 403s (even the
page GET that returned 200 earlier). The magic fix is unit-tested but **not yet verified
end-to-end** because the download can't reach extraction until the block lifts (cooldown;
retry later). Character is already imported + Convert verified, so once models install:
set Target Armature → Convert → Source=Video `Ale-PoseCAp.mp4` + Preview + Start Stream →
money-shot.

### 2026-07-11 — MPI block cleared; credential download VERIFIED end-to-end

Reinstalled a clean **committed** extension build (the running one was a dev-hacked
win.7: vendored `model_assets.py` matched but `model_setup.py` was a stale intermediate
missing the committed 401/403 handling and carrying an uncommitted debug helper). Built
dev-stamped via `tools/build_extension.py`, installed with `blender --command extension
install-file`, confirmed every addon `.py` byte-identical to source.

MPI block had lifted (plain `download.php` GET → 200). Ale typed his password into the
masked wizard field (agent never handled it); clicked OK. **The whole credential download
succeeded in 201s** — all 5 required assets installed under `%LOCALAPPDATA%\PoseCap\pear\assets\`:

- `SMPL/SMPL_NEUTRAL.pkl` — 247 MB, head bytes `28 64 70 30` (`(dp0`): first byte `0x28` = `(`,
  the **protocol-0 pickle** signature the magic fix (`93284f5`) broadened `_PICKLE_MAGIC` to
  accept. The download advanced past SMPL into SMPL-X only because that validation passed —
  **the magic fix is now proven end-to-end**, closing the prior blocker.
- `SMPLX/SMPLX_NEUTRAL_2020.npz` (167 MB), `SMPLX/flame_generic_model.pkl` (53 MB),
  `FLAME/FLAME2020/generic_model.pkl` (53 MB), `SMPLX/smpl_mean_params.npz` (public, present).

Engine doctor (`posecap-engine.exe doctor --pear-root …`): **`pear_assets => ok`**,
`torch_cuda => ok` (torch 2.4.1+cu124, CUDA 12.4, pytorch3d 0.7.9); only the two documented
warns (pear_checkout git-unverified, hf_weights pending first Start Stream). Onboarding
checklist ticked *Install the body models*.

Minor observation (not a task-0013 blocker): the in-panel post-download doctor double-check
showed *"Model files are in place (doctor could not be run to double-check)"* — the standalone
doctor runs clean in 5s warm, so this is a cold-first-run vs the addon's 120s subprocess
timeout (or engine-path pref). Start Stream shares that engine path and will disambiguate.

### 2026-07-11 — Money-shot captured; forward-lean root-caused + fixed (Camera Pitch)

Drove the live stream on `Ale-PoseCAp.mp4` end-to-end (first Start Stream fetched the
~2.7 GB PEAR weights; torch 2.4.1+cu124 / CUDA ok). The converted Mixamo character is
driven live and its **limbs track** the person, but the whole body showed a **systematic
~45° forward pitch** (person upright → character leaning).

Grounded (no guessing, per Ale): toggling `PEAR Orientation Fix` off flipped the character
upside-down, so the fix is needed and correct; the residual pitch is a global-orient bias.
The POC (`CorridorRig-Original`) had a **`smplx_camera_pitch`** control ("Camera tilt angle:
positive = looking down, negative = looking up") that the rewrite **dropped** — the video's
webcam tilts up at standing Ale, and a fixed 180° flip can't remove camera tilt.

**Fix (Ale chose "fix in code"):** ported the Camera Pitch compensation. The flip and the
camera pitch share the camera X axis, so `flip_global_orient` now rotates by `pi +
camera_pitch` (default 0 = no regression). Threaded through `plan_pose_application` →
`PoseApplyTimer` → a new `camera_pitch` FloatProperty (degrees, Advanced section, POC
convention). TDD (`tests/core/test_orientation.py`), full gate green (ruff, format, pyright
Win+Linux, import-linter, 329 tests). Rebuilt + reinstalled the extension; live tuning gave
**Camera Pitch −22°** → character stands upright, matching the person. Money-shot captured:
`doc/media/posecap-live-capture.gif` (4 MB) + `doc/guides/images/live-capture-stream.png`.

## Definition of Done

- [x] Installer wizard + onboarding + Mixamo convert verified in real Blender, media captured.
- [x] Download extraction/validation bug fixed for real + regression-tested (magic protocol-0).
- [x] Download verified end-to-end (all 5 assets installed; magic fix proven; doctor `pear_assets` ok).
- [x] HITL money-shot (stream drives converted Mixamo char + preview) captured — GIF + still, character upright after the Camera Pitch fix.
- [x] All tutorial docs finalized with real media (4 guides + installer/onboarding/convert/stream media).
- [ ] Status → done; Notes closes the task (on merge).
