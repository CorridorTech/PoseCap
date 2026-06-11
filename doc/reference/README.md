# Reference Material

Third-party papers and upstream docs the rewrite is grounded in. Read-only; none of this is project documentation — decisions derived from it go to `doc/adr/`.

## PEAR — live pose estimation backbone

* `pear-paper-2601.22693.pdf` — "PEAR: Pixel-aligned Expressive humAn mesh Recovery" (Wu et al., IDEA). Source: https://arxiv.org/abs/2601.22693
* `pear-github-readme.md` — upstream repo readme. Source: https://github.com/Pixel-Talk/PEAR
* Project page: https://wujh2001.github.io/PEAR/
* Why: the engine bridge wraps PEAR's EHM pipeline (ViT backbone + SMPL-X transformer decoder head). Single image in, SMPL-X parameters out, >100 FPS claimed.

## Fast SAM 3D Body — candidate future backend

* `fast-sam-3d-body-paper-2603.15603.pdf` — "Fast SAM 3D Body" (Yang et al.). Source: https://arxiv.org/abs/2603.15603 — MIT license
* `fast-sam-3d-body-readme.md` — upstream repo readme. Source: https://github.com/yangtiming/Fast-SAM-3D-Body
* `fast-sam-3d-body-realworld-deployment.md` — upstream deployment doc (asset paths, publisher setup). Same repo, `docs/`.
* Why: Dean's stated interest, two open problems from the POC: (1) the MHR-127 to SMPL feedforward conversion never worked in the POC (required mapping assets and experiment dirs were missing — see `C:\Dev\CorridorRig-Original\engine\`), (2) multi-camera estimation (`run_multiview_publisher.py`) unexplored. A second engine adapter behind the `PoseStream` port is the integration path if revisited.

## Meshcapade SMPL Blender addon — addon lineage

* `meshcapade-smpl-addon-readme.md` — upstream repo readme. Source: https://github.com/Meshcapade/SMPL_blender_addon — GPL-3.0, repo discontinued (moved to MPI GitLab)
* Why: the POC addon is a fork of this addon family. License lineage: any code carried over stays GPL-3.0; model files are licensed separately (MPI academic / Meshcapade commercial).

## POC source

* Dean's original drop: Google Drive, https://drive.google.com/file/d/1LlOcCRu_J6Q6xxjpJxI576pLoIx-q23B/view — local working copy at `C:\Dev\CorridorRig-Original` (read-only reference, see AGENTS.md).
