# Getting started with PoseCap

This is the full walk-through: from a clean Windows machine to a character
moving live from your webcam or a video. It takes about 20 minutes, most
of it downloads you can leave running.

Along the way PoseCap keeps a **Getting Started** checklist at the top of
its panel and disables the capture buttons until you are ready — so you
are always guided to the next step and can never click into an error.

**The four stops:**

1. [Install PoseCap](#1-install-posecap) — run the Windows installer.
2. [First run in Blender](#2-first-run-in-blender) — open the panel.
3. [Set up the body models](#3-set-up-the-body-models) — a one-time licensed download.
4. [Set up a character and capture it live](#4-set-up-a-character-and-capture-it-live).

## What you need

| | |
|---|---|
| **OS** | Windows 10 or 11 |
| **GPU** | NVIDIA RTX 30 / 40 / 50 series with an up-to-date driver (CUDA is required — there is no CPU mode) |
| **Blender** | 4.2 LTS or newer (5.x supported) — install it first from [blender.org](https://www.blender.org/download/) |
| **Camera** | Any webcam, or a video file to test with |

## 1. Install PoseCap

Download the latest `PoseCap_..._Windows_Setup.exe` from the
[releases page](https://github.com/CorridorTech/PoseCap/releases/latest)
and run it. The installer needs no administrator rights — it installs into
your user folder.

**License** — PoseCap itself is free and open source. Accept the agreement
and click **Next**.

![Installer license page](images/install-license.png)

**Destination** — the default (`…\AppData\Local\PoseCap`) is fine. Click
**Next**.

![Installer destination folder](images/install-destination.png)

**Ready** — review the summary and click **Install**.

![Installer ready to install](images/install-ready.png)

**Installing** — the installer downloads and sets up the GPU runtime
(PyTorch, the PEAR engine, and supporting files — about 4 GB). This is the
long step; leave it running.

![Installer downloading the GPU runtime](images/install-progress.png)

**Finish** — when it is done, click **Finish**. PoseCap has also installed
its panel into Blender for you.

![Installer finished](images/install-finish.png)

> The installer bundles only what has no canonical download source;
> everything heavy (Python, PyTorch, the PEAR model code) is fetched from
> official pinned sources during this step. The licensed body models are
> **not** downloaded here — that is the one-time step below, done with your
> own account.

## 2. First run in Blender

Open Blender. In the 3D Viewport, press **`N`** to open the sidebar, then
click the **PoseCap** tab. You will see the **Getting Started with PoseCap**
checklist:

![The Getting Started checklist](images/model-onboarding-checklist.png)

- **Install the body models** — not done yet; it has a **Set Up** button.
- **Choose a target character** — the armature capture will drive.
- **Ready to capture** — ticks green once the first two are done.

Until the checklist is complete, **Start Stream** stays disabled with the
hint *"Finish Getting Started above to enable capture."* That is by design —
it points you at the next step instead of failing.

> Don't see the PoseCap tab? The installer enables the extension
> automatically, but if Blender was open during install, restart it. You
> can also enable it by hand in **Edit → Preferences → Add-ons**, searching
> for *PoseCap*.

## 3. Set up the body models

Click **Set Up** on the first checklist row. This is a **one-time, free**
download of the SMPL-X research body models, which are licensed by the Max
Planck Institute and cannot ship inside PoseCap.

In short: create free accounts on three official sites, then enter that
email and password in the dialog and click **OK** — PoseCap downloads and
installs every file, showing a progress bar as it goes.

**→ Full step-by-step, with the license details and troubleshooting:
[Setting up the body models](smplx-model-setup.md).**

When the download finishes, the first checklist row turns to a green tick.

## 4. Set up a character and capture it live

**Choose a character.** Import any Mixamo or Unreal Engine character (or use
the built-in SMPL-X body), pick it as the **Target Armature**, and click
**Convert Character for PoseCap** — one click reorients and renames the
skeleton so live capture can drive it.

**→ Full guide: [Setting up a character](character-setup.md).**

**Capture it live.** Pick your **Source** — a webcam, or a video file to
test — turn on **Show Preview Window**, and click **Start Stream**. Your
character now moves with the person in front of the camera, in real time.
Turn on **Record Live MoCap** to bake the motion to keyframes.

![Live capture: the source video on the left drives the character on the right, in real time](../media/posecap-live-capture.gif)

Inside Blender it looks like this — the converted Mixamo character driven live,
with the source preview window:

![A converted Mixamo character driven live from a video, with the source preview](images/live-capture-stream.png)

**→ Full guide: [Live capture](live-capture.md).**

---

That's the whole pipeline: install → models → character → live capture.
Every flow above has its own detailed guide linked inline, and **PoseCap
Doctor** (Start Menu → PoseCap) confirms your setup is healthy any time.
