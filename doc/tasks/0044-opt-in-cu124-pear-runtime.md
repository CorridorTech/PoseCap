# Task 0044: Let RTX 30/40 owners opt into the cu124 PEAR runtime

**Status:** in-progress
**Created:** 2026-10-19
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:**
**Board ref:**

## Context

ADR-0016's cu128 matrix costs pre-Blackwell GPUs about a third of their live
throughput (RTX 3080: 30.25 -> 20.53 NET FPS). The only recovery available to
users is installing v1.0.6-win.4, which loses every fix since. ADR-0019
proposes shipping the frozen cu124 matrix as a user-selected runtime inside the
current PEAR payload. This task implements it as a bridge until task 0041
recovers cu128 throughput.

## Acceptance Criteria

- [x] The Windows PEAR payload carries `requirements-torch-cu124.lock` and the
      hash-pinned v1.0.6-win.4 PyTorch3D wheel under `wheels/cu124/`. The
      packer refuses one without the other, and scans the extra wheel for
      licensed binaries.
- [x] `install_pear.ps1` installs the runtime named in `pear_runtime.json`
      (default cu128), with the PyTorch3D wheel that matches it.
- [x] `switch_pear_runtime.ps1` persists the choice, reinstalls, refuses cu124
      when a Blackwell GPU is present, and restores the previous choice if
      the reinstall fails. Behavioral tests cover each path.
- [x] Two Start-menu shortcuts on the PEAR component; the release notice
      names them, guarded by a test.
- [x] End to end on an RTX 3080: install the default runtime, switch to
      cu124, doctor green apart from licensed assets, a PyTorch3D CUDA kernel
      runs, switch back.
- [ ] A live NET FPS A/B through the switched runtime on an RTX 30/40, with
      licensed models present, in the `doc/benchmarks.md` format.
- [ ] Maintainer accepts or rejects ADR-0019.

## Plan

- [x] Pin the cu124 torch lock and the PyTorch3D wheel (archive and wheel
      SHA-256).
- [x] Stage both in `packaging/build_pear_payload.ps1`; allow them in
      `tools/build_pear_payload.py`.
- [x] Add `packaging/installer/pear_runtime.ps1`, shared by the PEAR handler
      and the new switch script.
- [x] Register the new files with PEAR component ownership, uninstall
      cleanup, and the bootstrap staging list.
- [x] Update README, getting-started, and the release notice.
- [x] Run the end-to-end check on RTX 30/40 hardware and record it in Notes.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-10-19

Opened from the question of whether users should download an older release
to keep pre-Blackwell throughput. Diffing v1.0.6-win.4 against the current
tree showed the runtime difference is confined to the torch lock, the
installer's index URL, and the PyTorch3D build. The PyPI lock is identical,
and the engine code does not depend on the torch version. That makes an
in-place switch cheaper than a second installer.

### 2026-10-19 — end-to-end on an RTX 3080

Machine: RTX 3080 10 GB (compute capability 8.6), driver 596.21, Windows 10.
No licensed SMPL-X assets present, so `pear_assets` is the one expected doctor
error throughout. The installer tolerates it by design.

1. The modified `build_pear_payload.ps1` ran for real (build label win.99). It
   downloaded the v1.0.6-win.4 payload, verified both hashes, and produced a
   payload containing `wheels/cu124/pytorch3d-0.7.9-cp311-cp311-win_amd64.whl`
   (sha256 `7d78e5a3...`) next to the cu128 build. Both wheels share one
   filename, which is why the cu124 build lives in its own directory.
2. An install tree assembled as the setup exe lays it out, then the real
   `install_pear.ps1`: runtime cu128, torch `2.9.1+cu128`, every doctor check
   ok except `pear_assets`.
3. `switch_pear_runtime.ps1 -Runtime cu124` exited 0. Doctor reported torch
   `2.4.1+cu124`, arch list `sm_50..sm_90`, and again only `pear_assets` as an
   error. `pytorch3d._C` imported, and `knn_points` ran on the GPU with finite
   output, which proves the PyTorch3D build matches the torch ABI.
4. `switch_pear_runtime.ps1 -Runtime cu128` exited 0, removed
   `pear_runtime.json`, and the same smoke passed on `2.9.1+cu128`.

Not yet measured: live NET FPS through the switched runtime. That needs
licensed models, so the A/B criterion stays open. The cu124 arm uses exactly
the pins of the 2026-07-17 A/B's 30.25 FPS arm.
