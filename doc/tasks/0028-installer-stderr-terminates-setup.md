# Task 0028: Stop Blender stderr noise from terminating the installer

**Status:** proposed
**Created:** 2026-07-16
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:**
**Board ref:**

## Context

Field report from Dean (2026-07-16, Discord, with `bug_report.txt` and the
bootstrap transcript): `PoseCap_v1.0.6-win.4_Windows_Setup.exe` aborts during
"Install and verify the Blender extension" on a machine whose Blender prints
startup warnings to stderr (third-party add-ons such as KeenTools, and a
`TBBmalloc` runtime notice). The extension itself installs fine; the installer
still reports `SETUP FAILED`.

Root cause, confirmed against the repo scripts: the handlers set
`$ErrorActionPreference = "Stop"` and invoke Blender with `2>&1`. Windows
PowerShell 5.1 wraps every stderr line of a native command whose error stream
is redirected into an `ErrorRecord`, and under `Stop` the first such line
becomes a terminating exception — success exit codes never get checked. Any
stderr output at all fails the install, and third-party add-on chatter is
outside PoseCap's control.

The pattern is systemic, not one line: seven `2>&1` native invocations across
four handlers run under `Stop` — `install_base.ps1` (three: list, remove,
list), `uninstall_base.ps1` (two: list, list), `blender_discovery.ps1` (one:
`--version`, so a noisy Blender can also break discovery for every component),
and `install_pear.ps1` (one: `nvidia-smi`).

This directly violates the project tradeoff statement (GUIDELINES preamble):
a working install on the first try beats everything.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] A Blender (or nvidia-smi) that writes any text to stderr while exiting 0
      no longer aborts any installer or uninstaller step; success/failure is
      decided by exit code and parsed stdout only.
- [ ] Stderr text still reaches the bootstrap transcript log, so field logs
      keep their diagnostic value (Dean's log carried the real traceback).
- [ ] All seven `2>&1` native invocations under `$ErrorActionPreference =
      "Stop"` go through one shared helper (single place for the policy), not
      seven per-site workarounds.
- [ ] A regression test pins the contract: a fake `blender.cmd` that prints a
      warning to stderr and a valid extension list to stdout passes the
      install/verify step (extend `tests/test_installer_components.py` or the
      PowerShell-level harness it drives).
- [ ] Dean's report is answered with the fix version once released; the
      installed-machine repair path (PoseCap Setup repair) is confirmed to
      pick up the corrected bootstrap scripts.

## Plan

- [ ] Ground (`ad-ground`) the canonical PowerShell 5.1 pattern for capturing
      native stdout while tolerating stderr under `Stop` — candidate shape: a
      scoped helper whose function-local `$ErrorActionPreference = "Continue"`
      confines the relaxation (preference variables are dynamically scoped) and
      which stringifies merged output; weigh against Dean's save/restore patch
      and dropping `2>&1` (rejected if it silences stderr in hidden-window
      installs).
- [ ] Red test first against the fake-Blender fixture, then the helper, then
      migrate the seven call sites.
- [ ] Fresh-context review (WORKFLOW section 10) before the PR; the fix ships
      to users only with the next installer build (win.N bump, release is HITL).

## Notes

### 2026-07-16 — report received

Dean supplied a proposed patch (save/restore `$ErrorActionPreference` around
the Blender calls in `install_base.ps1`). The patch is directionally correct
and confirms the diagnosis; the repo fix generalizes it because the same
landmine exists in discovery, uninstall, and the PEAR GPU probe, and a
try/finally-safe scoped helper avoids leaving the preference relaxed on an
unexpected throw.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
