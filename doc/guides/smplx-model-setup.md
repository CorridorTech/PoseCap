# Setting up the SMPL-X body models

PoseCap drives a research body model (SMPL-X) that is **licensed by the
Max Planck Institute and cannot ship inside PoseCap**. You download it
once with your own free account; PoseCap automates everything else.
Total time: about 5 minutes plus a ~500 MB download.

> Commercial production use of the body models requires a separate
> [Meshcapade license](https://meshcapade.com/) — the free accounts below
> cover non-commercial research use.

## Step 1 — Create your free accounts (the license step)

Create an account on each of the three official sites, using the **same
email and password** on all three (that keeps step 2 to a single login):

| Site | Link |
|---|---|
| SMPL | <https://smpl.is.tue.mpg.de/register.php> |
| SMPL-X | <https://smpl-x.is.tue.mpg.de/register.php> |
| FLAME | <https://flame.is.tue.mpg.de/register.php> |

Signing up (and ticking the license checkboxes) **is** the license
acceptance — there is nothing else to sign.

![The register form on the official sites](images/model-signup.svg)

Check your inbox: each site sends a verification email you must confirm
before downloads work.

## Step 2 — Let PoseCap download and install everything

In Blender, open the **PoseCap panel** (3D Viewport → press `N` →
PoseCap tab). While model files are missing, the panel shows a
**Body Models — one-time setup** section:

1. Enter the email and password from step 1.
2. Click **Download & Install Models**.
3. Wait for the green **Models installed — doctor check passed** status.

![The Body Models section in the PoseCap panel](images/model-wizard-panel.svg)

Your password is used once, in memory, to download from the official MPI
server — it is never saved, never logged, and the field clears itself
the moment the download starts. A wrong password shows a friendly
message; just re-type and click again.

### Prefer not to type your password into Blender?

Click **Watch my Downloads Folder** instead, then download these files
from the official sites with your browser (log in first):

| Download this file | From |
|---|---|
| `SMPL_python_v.1.1.0.zip` | [SMPL downloads](https://smpl.is.tue.mpg.de/download.php) |
| `SMPLX_NEUTRAL_2020.npz` | [SMPL-X downloads](https://smpl-x.is.tue.mpg.de/download.php) |
| `FLAME2020.zip` | [FLAME downloads](https://flame.is.tue.mpg.de/download.php) |

PoseCap detects each file as it lands in your Downloads folder,
validates it, extracts what it needs, and installs it — no unzipping, no
file moving. It also picks up a browser-renamed re-download like
`FLAME2020 (1).zip`.

### Or place the files fully by hand (advanced)

Confirmed working in the field (Corridor, 2026-07-10). Log in on each site
first, then:

- **SMPL** — the Downloads page is login-gated. Download the Python package,
  open it, take the **neutral** model `.pkl`, rename it to `SMPL_NEUTRAL.pkl`,
  and put it in `assets\SMPL\`.
- **SMPL-X** — download `SMPLX_NEUTRAL_2020.npz` into `assets\SMPLX\`.
- **FLAME** — the Downloads page is login-gated; the entry is **"FLAME 2020"**.
  From it take `generic_model.pkl` and place it in **two** locations:
  `assets\FLAME\FLAME2020\generic_model.pkl` and, renamed,
  `assets\SMPLX\flame_generic_model.pkl`.
- **smpl_mean_params.npz** — this one is public (not MPI-gated). Download it
  from the pinned Hugging Face copy and put it in `assets\SMPLX\`:
  <https://huggingface.co/spaces/brjathu/HMR2.0/resolve/998dfa865dddc3cdd4f4bed22a7c78a61cf9b32a/data/smpl_mean_params.npz>

## First Start Stream downloads the AI model (~2.7 GB, one time)

The very first time you click **Start Stream**, PoseCap downloads the pinned
pose-estimation model (~2.7 GB) before the first frame appears. The panel
shows **"Still starting — first run downloads the AI model (~2.7 GB), this
can take several minutes."** This is the download, not a freeze — leave it
running. Every later start is immediate.

## What you end up with

![Final file layout inside the PEAR folder](images/model-final-layout.svg)

Run **PoseCap Doctor** (Start Menu shortcut) any time — every check must
be green before the first live capture. Two warnings are normal: the PEAR
checkout has no git history to verify, and the AI model weights show as
"not verified" until that first Start Stream downloads them.

## Troubleshooting

| Message | Meaning | Fix |
|---|---|---|
| "…returned a web page instead of the file" | Wrong email/password for that site | Re-check the account on the site named in the message; re-enter and retry |
| "…is incomplete" | The download was interrupted | Click Download & Install again — finished files are kept, only missing ones are fetched |
| "…archive is corrupted" | A manual download was cut short | Delete the file from Downloads and download it again |
| Doctor still red on `pear_assets` | A file is missing or in the wrong place | Re-open the panel; the Body Models section lists what is still missing |
