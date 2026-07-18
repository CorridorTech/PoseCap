# Install PoseCap on Linux

> **On Windows?** Use the [packaged installer](getting-started.md#1-install-posecap)
> instead — this page is Linux-specific. Once you're through it, the rest of the
> [Getting Started guide](getting-started.md) (body models, character setup, live
> capture) applies exactly the same way on both platforms.

Linux doesn't have a downloadable pre-built installer yet — Windows users
download a ready-made `.exe`; publishing an equivalent pre-built Linux
artifact is release-engineering follow-up work, not something this page can
give you today. What it can give you is a single command that builds
everything from source and installs it, using the same installer code
(`packaging/linux_installer/`) the Windows package uses under the hood.

Total time: 15–25 minutes for MediaPipe Lite (mostly unattended downloads);
add another 20–30 minutes for PEAR, most of it the CUDA runtime and pose-model
downloads.

## What you need

| | |
|---|---|
| **OS** | Linux x86_64. Validated on CachyOS (Arch-based); any distribution with a working `glibc` and Python 3.11 should work |
| **Blender** | 4.2 LTS minimum, 5.x supported — install from [blender.org](https://www.blender.org/download/) or your distro's package manager. Auto-detected from common install locations and Steam; set a `blender_override.txt` in your install directory if yours isn't found |
| **uv** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` if you don't have it |
| **MediaPipe Lite** | CPU-first body capture. No GPU required |
| **PEAR** | NVIDIA GPU with a working driver (`nvidia-smi` must succeed). Validated on an RTX 5090 (Blackwell) with driver 610.43.03 — see the [runtime matrix note](#pear-runtime-matrix-note) below for older GPU generations |
| **Camera** | Any webcam, including virtual cameras |

Clone this repo (the `feat/linux-support` branch).

## Quick install

From the repo root, one command builds the extension and your backend(s) and
installs everything:

```bash
uv run python packaging/install_linux.py
```

With no `--components`, this installs MediaPipe Lite always, plus PEAR too
if it detects a healthy NVIDIA driver — the same default the installer
itself uses. Pin it explicitly if you want to choose:

```bash
uv run python packaging/install_linux.py --components base,mediapipe
uv run python packaging/install_linux.py --components base,mediapipe,pear
```

A successful run ends with `PoseCap setup complete.` That's the whole
install. If you selected PEAR, it also prints an **ACTION REQUIRED** notice
about the licensed body models — expected on a fresh install; see
[Set up the body models](smplx-model-setup.md), then confirm with
[Checking readiness](#checking-readiness). MediaPipe Lite needs no body-model
download — open Blender, press `N` in the 3D Viewport, choose the **PoseCap**
tab, and continue with [Getting Started](getting-started.md) step 3.

The rest of this page is the same pipeline broken into individual steps, for
when you want to see what's happening, customize a piece of it, or debug a
failure.

## Install the Blender extension

```bash
uv run python tools/build_extension.py --output-dir /tmp/posecap-extension --release
blender --command extension install-file -r user_default -e /tmp/posecap-extension/*.zip
blender --command extension list   # should print "posecap [installed]"
```

If `blender` isn't on your `PATH`, use its full path in both commands instead.

## MediaPipe Lite (recommended first path)

Account-free, CPU-only, and the fastest way to confirm everything works. This
builds and installs through the same code path validated end-to-end on real
hardware (real `uv build`, a real isolated venv, a real live pose stream).

```bash
INSTALL="$HOME/.local/share/PoseCap"
mkdir -p "$INSTALL/extension"
cp /tmp/posecap-extension/*.zip "$INSTALL/extension/"

# Build the payload (wheels + uv binary + MediaPipe lock, zipped)
uv run python packaging/build_mediapipe_payload_linux.py \
  --base-url https://github.com/CorridorTech/PoseCap/releases/download/local-build \
  --output-dir /tmp/posecap-mediapipe-payload

# Stage it where the installer expects it
mkdir -p "$INSTALL/payloads/mediapipe" "$INSTALL/backends/mediapipe/models"
unzip -o /tmp/posecap-mediapipe-payload/posecap-mediapipe-bootstrap-*.zip \
  -d "$INSTALL/payloads/mediapipe"
chmod +x "$INSTALL/payloads/mediapipe/bin/uv"

# Fetch the pinned Holistic Landmarker model bundle
curl -sL -o "$INSTALL/backends/mediapipe/models/holistic_landmarker.task" \
  "https://storage.googleapis.com/mediapipe-models/holistic_landmarker/holistic_landmarker/float16/1/holistic_landmarker.task"

# installer_manifest.json (version must match pyproject.toml)
python3 -c "import json; open('$INSTALL/installer_manifest.json','w').write(json.dumps({'version': '1.0.7'}))"

# Run the installer
PYTHONPATH=packaging uv run python -m linux_installer.bootstrap_install \
  --install-dir "$INSTALL" --components base,mediapipe
```

A successful run ends with `PoseCap setup complete.` Open Blender, press `N`
in the 3D Viewport, choose the **PoseCap** tab, and MediaPipe Lite should be
ready to select. Continue with [Getting Started](getting-started.md) from
step 3 (character setup) — MediaPipe Lite needs no body-model download.

## PEAR (NVIDIA GPU)

PEAR additionally needs the licensed SMPL-X/FLAME/MANO body models (see
[Set up the body models](smplx-model-setup.md) — the in-Blender download
wizard works unchanged on Linux) and an isolated CUDA runtime, built through
the same installer script as MediaPipe Lite above. The one manual piece is
PyTorch3D: it has no official Linux wheel, so the payload builder repacks one
from an already-installed copy rather than building from source.

```bash
INSTALL="$HOME/.local/share/PoseCap"

# 1. A throwaway venv with the pinned CUDA matrix (ADR-0016), just to get a
#    real PyTorch3D install the payload builder can repack into a wheel
uv venv /tmp/posecap-pytorch3d-venv --python 3.11
uv pip install --python /tmp/posecap-pytorch3d-venv/bin/python \
  torch==2.9.1+cu128 torchvision==0.24.1+cu128 \
  --index-url https://download.pytorch.org/whl/cu128
uv pip install --python /tmp/posecap-pytorch3d-venv/bin/python \
  --extra-index-url https://miropsota.github.io/torch_packages_builder \
  "pytorch3d==0.7.9+d9839a9pt2.9.1cu128"

# 2. Build the payload (wheels + repacked PyTorch3D + uv binary + locks, zipped)
uv run python packaging/build_pear_payload_linux.py \
  --pytorch3d-site-packages /tmp/posecap-pytorch3d-venv/lib/python3.11/site-packages \
  --base-url https://github.com/CorridorTech/PoseCap/releases/download/local-build \
  --output-dir /tmp/posecap-pear-payload

# 3. Stage it where the installer expects it (unlike MediaPipe, this extracts
#    to the install root directly, not a payloads/ subdirectory)
mkdir -p "$INSTALL/payloads/pear"
unzip -o /tmp/posecap-pear-payload/posecap-pear-bootstrap-*.zip -d "$INSTALL"
chmod +x "$INSTALL/bin/uv"

# 4. Download PEAR's own source, external and pinned (ADR-0005, never
#    vendored into this repo), and verify it against the pinned hash
curl -sL -o "$INSTALL/payloads/pear/pear-source.zip" \
  "https://github.com/Pixel-Talk/PEAR/archive/977331937ea8c3d08ae0254d8831d640d46a5cf6.zip"
python3 -c "
import hashlib, json
expected = json.load(open('packaging/pear-source.lock.json'))['sha256']
actual = hashlib.sha256(open('$INSTALL/payloads/pear/pear-source.zip', 'rb').read()).hexdigest()
assert actual == expected, f'hash mismatch: {actual} != {expected}'
print('PEAR source hash OK')
"

# 5. installer_manifest.json (version must match pyproject.toml)
python3 -c "
import json
open('$INSTALL/installer_manifest.json', 'w').write(json.dumps({
    'version': '1.0.7',
    'torchIndexUrl': 'https://download.pytorch.org/whl/cu128',
    'pearRevision': '977331937ea8c3d08ae0254d8831d640d46a5cf6',
}))
"

# 6. Run the installer (add base,mediapipe,pear to install both backends at once)
PYTHONPATH=packaging uv run python -m linux_installer.bootstrap_install \
  --install-dir "$INSTALL" --components base,pear
```

A successful run ends with `PoseCap setup complete.` and an **ACTION
REQUIRED** notice pointing at the body-model download — that's expected on a
fresh install. Follow [Set up the body models](smplx-model-setup.md) to get
the licensed SMPL-X/FLAME/MANO files in place; the same in-Blender wizard
works here since `addon/posecap_addon/model_setup.py` has no
Blender-specific dependency beyond the UI it's called from.

### Checking readiness

```bash
"$INSTALL/runtime/venv/bin/posecap-engine" doctor --pear-root "$INSTALL/pear" --download-weights
```

`"ok": true` with every check `"status": "ok"` means ready (`--download-weights`
also pre-fetches the ~2.6 GB pose-model weights so your first Start Stream
doesn't wait on them). Until the body models are in place, `pear_assets` is
the one expected error — the installer surfaces the same message.

### PEAR runtime matrix note

The Torch 2.9.1+cu128 / PyTorch3D 0.7.9 matrix above is the same one
[ADR-0016](../adr/0016-blackwell-cu128-runtime-matrix.md) validated for
Windows RTX 50-series (Blackwell) GPUs, reused here unmodified. That ADR also
records a measured ~32% live-frame-rate regression on RTX 30/40-series
(Ampere/Ada) versus the older cu124 matrix — a real cost of one runtime
serving every supported GPU generation, not a Linux-specific issue.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `install_linux.py` fails partway through | Each stage prints `==>` before it starts, so the last one shown is where it failed. Fix the underlying issue (network, disk space, missing `uv`) and re-run — it rebuilds and re-downloads its own staging files each time (uv's package cache still makes repeat `pip`/`venv` calls fast), but `bootstrap_install`'s own steps skip reinstalling an already-healthy runtime |
| `blender --command extension list` doesn't show `posecap [installed]` | Re-run the install-file command; check the zip built successfully in `/tmp/posecap-extension/` |
| `nvidia-smi` fails or isn't found | Install/update your NVIDIA driver before attempting the PEAR path; MediaPipe Lite needs no GPU at all |
| `doctor` reports `pear_assets` as the only error | The licensed body models aren't installed yet — see [Set up the body models](smplx-model-setup.md) |
| PoseCap panel doesn't list a ready backend | Confirm `~/.local/share/PoseCap/backends/<id>/backend.json` exists and `$XDG_DATA_HOME` (or `$HOME`) resolves to where you installed — the addon auto-detects `~/.local/share/PoseCap` by default |

---

*Once a backend is ready, the rest of the flow — body models, character setup,
live capture — is identical to Windows: continue with the
[Getting Started guide](getting-started.md).*
