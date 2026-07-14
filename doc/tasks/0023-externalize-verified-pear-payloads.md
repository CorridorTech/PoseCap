# Task `0023`: Externalize verified PEAR payloads

**Status:** in-progress
**Created:** 2026-07-14
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** doc/specs/0003-select-windows-backend-modules.md
**Board ref:**

## Context

The modular Windows installer can omit PEAR at installation time, but its setup
executable still embeds PEAR-only bootstrap payloads and the PEAR source archive is
downloaded without a pinned digest. Spec 0003 and ADR-0011 require a Base-only user
to avoid those downloads and require every hosted component payload to be verified
before installation. This task owns the release-hosting and checksum boundary that
Task 0022 deliberately does not simulate.

## Acceptance Criteria

- [x] The Base installer executable contains no PEAR-only wheel, runtime bootstrap
  binary, source archive, or model weight payload.
- [x] A versioned component manifest records every PEAR payload URL, byte size, and
  SHA-256 digest, and packaging fails when any field is absent or malformed.
- [x] Inno Setup downloads PEAR payloads only when the PEAR component is selected and
  rejects a payload whose observed SHA-256 differs from the manifest.
- [ ] Recommended, Custom Base-only, PEAR install, healthy repair, and interrupted
  download tests leave installer inventory equal to observed disk state.
- [ ] A clean-machine run downloads the published PEAR payloads, passes PEAR doctor,
  and records the exact release manifest used for diagnosis.

## Plan

- [x] Run `ad-ground` against Inno verified external downloads, the CorridorKey
  online component manifest, PoseCap release hosting, and relevant git history.
- [ ] Define the hosted PEAR payload boundary and publish immutable release artifacts
  with URL, size, and SHA-256 metadata.
- [x] Render selected external payloads from `packaging/build_installer.ps1` into the
  Inno installer and persist the source manifest in installed inventory.
- [x] Add generated-script, tampered-payload, selection, repair, and interruption
  tests through `ad-tdd`.
- [ ] Run the full local gate, a clean-machine acceptance run, and `ad-review`.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-14

`ad-ground` selected the native Inno download path. Official Inno Setup 6
documentation defines `[Files]` entries with `external download extractarchive`,
component conditions, `ExternalSize`, and `Hash` as the built-in selected-download
and SHA-256 verification surface. CorridorKey Runtime validates URL, basename, byte
size, and 64-hex SHA before rendering the same external archive pattern from its
component manifest (`scripts/package_suite_installer_windows.ps1`).

PoseCap's current build embeds `uv`, four wheels, and both lockfiles, while its PEAR
handler independently downloads the pinned source archive without a digest. Git
history (`d862990`, `f2640f5`, `421b9ba`) requires preserving the light online
installer, deterministic repair, and the release gate. The happy path is therefore a
two-phase release: build one PEAR bootstrap archive containing all PEAR-only local
payload plus the pinned PEAR source archive; publish it immutably; then build the
Base installer from a versioned manifest containing the archive URL, byte size, and
SHA-256. Inno downloads and extracts it only for `Components: pear`.

TDD public surfaces are the payload builder, installer builder, and rendered Inno
script. The first tracer proves that a valid external-payload manifest renders a
component-conditioned, hash-verified download while the EXE staging tree contains no
PEAR payload. Subsequent behaviors reject malformed metadata, consume the verified
local PEAR source archive, persist payload provenance in installed inventory, and
prove selected versus unselected download behavior. Focused baseline: `31 passed`.

The first `ad-review` found that embedding the upstream PEAR source ZIP would also
redistribute FLAME/SMPL-X/MANO assets present in that archive, violating the task's
license boundary. The corrected release shape keeps Corridor's bootstrap payload to
seven runtime files (uv, two locks, and four wheels) and makes the pinned PEAR source
a separate direct-from-upstream Inno download. Both downloads carry URL, byte size,
and SHA-256 in the installed manifest; the payload builder recursively rejects model
binary extensions hidden inside wheels. The final bootstrap ZIP is 29,519,971 bytes,
SHA-256 `7415e84a69be81654120e0bed41955549a60d173e19f696da0d4040fd9ef9d89`,
with zero forbidden payload paths.

The final Base-only E2E used the compiled `1.0.5-win.2` EXE with SHA-256
`bc4d553de6178d464cbbd754f405eec7f535bd342708a7ec3cf68822d65f0d9e`
and a fully redirected Blender 5.0 user profile. Installation exited 0, recorded only
Base as `ready`, created `SETUP_OK`, installed and enabled the extension, and created
none of the PEAR-owned paths. The same EXE's uninstaller exited 0, removed the Blender
extension and every install-tree file. Fingerprints proved the real Blender profile
unchanged before and after; the prior Windows uninstall registration was restored.
Evidence is at `packaging/work/e2e-base-win2-final4/e2e-result.json` (ignored build
output). The PEAR clean-machine E2E remains pending until the versioned bootstrap is
published at its immutable release URL; publishing before commit/tag/review is not a
valid release test.

The pre-publication PEAR GUI E2E used the same Inno flow against a loopback HTTP
server, so both external downloads, hashes, extraction, bootstrap, Blender extension,
CUDA runtime, weights, backend registration, and final inventory were exercised
without creating a release. The first clean run exposed a real provenance bug:
`git -C <archive-root> rev-parse HEAD` walked up to the enclosing PoseCap checkout and
reported PoseCap commit `bac648e` as the PEAR revision. The official
[`git-rev-parse`](https://git-scm.com/docs/git-rev-parse) manual documents operation
from a directory controlled by a working tree, while GitHub's
[source-archive documentation](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives)
defines commit archives as snapshots without repository history. The fix records the
already hash-verified archive revision in `.posecap-source-revision`; Doctor prefers
that marker and verifies that Git revision checks resolve to the PEAR root before
trusting `HEAD`.

The corrected GUI run installed Base and PEAR into a new isolated root and completed
through the visible Finish page. `SETUP_OK` exists, inventory is `ready` for both
components, Blender reports `posecap [installed]`, CUDA and Hugging Face weights are
ready, and Doctor reports `pear_checkout=ok` with `revision_source=archive`. Its only
error is `pear_assets`, the expected manual licensed-model step accepted by the
installer. The tested bootstrap is 29,520,317 bytes with SHA-256
`7ec02a4a0ba0f252162cba923cf72376777da29733439b2cc3d087375e767728`;
the rebuilt production installer SHA-256 is
`5a9a2c24f214a1f4209bfd0c4124494322e74c5442fc345963108d90852b0446`.
Evidence remains in ignored output under `packaging/work/e2e-ui-pear-v2/`; the full
local gate passed with 462 tests selected and 10 deselected. Published-URL and
interrupted-download acceptance remain pending.

The review caught a repair/upgrade loop before handoff: source extraction previously
short-circuited on `configs/infer.yaml` even when its revision marker was stale. The
corrected handler skips extraction only when the installed revision matches the
manifest; otherwise it overlays the verified source while retaining the complete
`pear` tree. A real repair changed a deliberately stale revision back to the pin,
preserved a fixture under `pear/assets`, restored `ready` inventory, and recreated
`SETUP_OK`; evidence is the ignored `bootstrap-20260714T125359.log` in the same E2E
root.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
