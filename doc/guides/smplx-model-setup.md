# Setting up the body models

> **New to PoseCap?** The [Getting Started guide](getting-started.md) covers this
> step inside the whole install-to-capture flow. This page is the focused
> reference for the licensed download — the account detail, the no-password
> **Watch my Downloads Folder** option, and troubleshooting.

PoseCap drives a research body model (SMPL-X) that is **licensed by the
Max Planck Institute and cannot ship inside PoseCap**. You download it
once with your own free account; PoseCap automates everything else — no
unzipping, no file moving, no folders to find.

Total time: about five minutes plus a ~500 MB download.

> Commercial production use of the body models requires a separate
> [Meshcapade license](https://meshcapade.com/). The free accounts below
> cover non-commercial research use.

PoseCap shows you exactly where you are the whole way. The **Getting
Started with PoseCap** checklist at the top of the panel ticks off each
step as you finish it, and the capture buttons stay disabled until the
models are in — so you can never click into a missing-model error.

![The Getting Started checklist with the models step still open](images/model-onboarding-checklist.png)

## Step 1 — Create your free accounts (this is the license step)

Create an account on each of the three official sites, using the **same
email and password** on all three (that keeps step 2 to a single login):

| Site | Register |
|---|---|
| SMPL | <https://smpl.is.tue.mpg.de/register.php> |
| SMPL-X | <https://smpl-x.is.tue.mpg.de/register.php> |
| FLAME | <https://flame.is.tue.mpg.de/register.php> |

On each form: enter your email, choose a password (**at least 8
characters**), and **turn every license toggle green**. Turning those
toggles on **is** the license acceptance — there is nothing else to sign.
You can leave *Receive Emails* off.

The toggles differ slightly per site — turn on **all** of them except
*Receive Emails*:

**SMPL** — *Accept terms* and *Accept license*:

![SMPL registration with Accept terms and Accept license turned on](images/register-smpl-toggles.png)

**SMPL-X** — *Accept terms*, *Accept model license*, and *Accept body license*:

![SMPL-X registration with Accept terms, model license and body license turned on](images/register-smplx-toggles.png)

**FLAME** — *Accept terms*, *Accept model license*, and *Accept data license*:

![FLAME registration with Accept terms, model license and data license turned on](images/register-flame-toggles.png)

All three registrations are required: PoseCap needs one file from each
site (SMPL, SMPL-X, and the FLAME head model that SMPL-X uses).

> **Confirm your email before step 2.** Each site emails you a
> verification link that must be clicked before downloads work — and that
> mail often lands in **spam/junk**. If a download later fails with a
> login error, an unconfirmed account is the usual cause.

The confirmation email regularly lands in the spam folder — look for it
there and open it, then click its **Confirm my account** link:

![The MPI confirmation email sitting in the Gmail spam folder](images/register-confirmation-in-spam.png)

## Step 2 — Let PoseCap download and install everything

In Blender, open the **PoseCap panel** (3D Viewport → press `N` →
**PoseCap** tab). In the **Getting Started with PoseCap** checklist, the
first row — *Install the body models* — has a **Set Up** button. Click it.

A guided setup dialog opens:

![The Set Up Body Models dialog](images/model-setup-wizard.png)

1. Enter the **email** and **password** from step 1.
2. Click **OK**.

Your password is used once, in memory, to download from the official MPI
server. It is never saved, never logged, and the field clears itself the
moment the download starts. A wrong password shows a friendly message —
just re-open **Set Up** and try again.

A progress bar in the panel shows each file downloading, so you can see it
move instead of guessing whether it hung:

![The Body Models download progress bar](images/model-download-progress.png)

When every file is in, the *Install the body models* row turns to a green
tick and the checklist step is done.

### Prefer not to type your password into Blender?

In the same dialog, click **Watch my Downloads Folder** instead, then
download these files yourself from the official sites with your browser
(log in first):

| Download this file | From |
|---|---|
| `SMPL_python_v.1.1.0.zip` | [SMPL downloads](https://smpl.is.tue.mpg.de/download.php) |
| `SMPLX_NEUTRAL_2020.npz` | [SMPL-X downloads](https://smpl-x.is.tue.mpg.de/download.php) |
| `FLAME2020.zip` | [FLAME downloads](https://flame.is.tue.mpg.de/download.php) |

PoseCap watches your Downloads folder, detects each file as it lands,
validates it, extracts what it needs, and installs it. It even picks up a
browser-renamed re-download such as `FLAME2020 (1).zip`.

## First Start Stream downloads the AI model (~2.7 GB, one time)

The very first time you click **Start Stream**, PoseCap downloads the
pinned pose-estimation model (~2.7 GB) before the first frame appears. If
a start takes a while the panel shows **"Still starting — this can take a
few minutes; the very first run also downloads the AI model (~2.7 GB)."**
That is the download, not a freeze — leave it running. Every later start
is immediate.

## Check everything is green

Run **PoseCap Doctor** (Start Menu → PoseCap → PoseCap Doctor) any time.
Every check must be green before your first live capture. Two warnings are
normal: the PEAR checkout has no git history to verify, and the AI model
weights read as "not verified" until that first Start Stream downloads
them.

## Troubleshooting

| Message | Meaning | Fix |
|---|---|---|
| "…returned a web page instead of the file" | Wrong email/password, or the account for that site isn't confirmed | Confirm the verification email (check spam) for the site named in the message, then re-open **Set Up** and retry |
| "…is incomplete" | The download was interrupted | Click **Set Up** again — finished files are kept, only missing ones are fetched |
| "…archive is corrupted" | A manual download was cut short | Delete the file from Downloads and download it again |
| Doctor still red on `pear_assets` | A file is missing or in the wrong place | Re-open the panel; the checklist step and the Doctor output both name what is still missing |

---

*Next: [Set up a character](character-setup.md) to drive, then [capture it
live](live-capture.md). Full walk-through in the
[Getting Started guide](getting-started.md).*
