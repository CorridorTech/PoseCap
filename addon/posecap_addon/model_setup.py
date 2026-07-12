"""Guided setup for the licensed SMPL-X body models (task 0010).

Automates everything around the one legally required manual step: the user
registers on the official MPI sites (that registration is the license
acceptance) and their credentials are used in memory only to download the
pinned files straight from the official endpoint. Nothing is bundled,
persisted, or fetched anonymously.
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread

from posecap_contracts import (
    MPI_DOWNLOAD_URL,
    REQUIRED_MODEL_ASSETS,
    ModelAsset,
    MpiDownload,
    PublicDownload,
)
from posecap_contracts.model_assets import archive_member_matches, download_failure_reason

# fetch(url, post_data, sink_path, progress(bytes_done, bytes_total_or_zero))
ProgressCallback = Callable[[int, int], None]
Fetcher = Callable[[str, "bytes | None", Path, ProgressCallback], None]
StatusCallback = Callable[[str], None]

_DOWNLOAD_CHUNK_BYTES = 1024 * 256
_VALIDATION_HEAD_BYTES = 64 * 1024


class ModelSetupError(RuntimeError):
    """A model-setup failure with a user-facing message."""


@dataclass(frozen=True)
class MpiCredentials:
    """The user's own MPI-site login, held in memory only.

    repr/str never include the password so it cannot leak through logs or
    error messages.
    """

    email: str
    password: str = field(repr=False)

    def __str__(self) -> str:
        return f"MpiCredentials(email={self.email!r})"


@dataclass(frozen=True)
class InstallReport:
    """File names placed into the PEAR checkout by a setup run."""

    installed: tuple[str, ...]


def missing_model_assets(
    pear_root: Path,
    assets: tuple[ModelAsset, ...] = REQUIRED_MODEL_ASSETS,
) -> tuple[ModelAsset, ...]:
    """Return the required model assets absent from the PEAR checkout."""
    return tuple(asset for asset in assets if not pear_root.joinpath(*asset.target_path).is_file())


def install_missing_models(
    pear_root: Path,
    credentials: MpiCredentials,
    *,
    fetch: Fetcher | None = None,
    status: StatusCallback | None = None,
    progress: ProgressCallback | None = None,
    assets: tuple[ModelAsset, ...] = REQUIRED_MODEL_ASSETS,
) -> InstallReport:
    """Download and place every missing model with the user's own credentials.

    One fetch per unique source archive; every placement is validated before
    it lands and written atomically. ``progress`` receives per-file
    (bytes_done, bytes_total) so the UI can show a real bar, not a spinner.
    Raises ModelSetupError with a user-facing message on any failure, leaving
    no partial files behind.
    """
    fetch_callable = fetch or _urllib_fetch
    report_status = status or (lambda _message: None)
    report_progress = progress or _noop_progress
    missing = missing_model_assets(pear_root, assets)
    targets_by_source: dict[MpiDownload | PublicDownload, list[ModelAsset]] = {}
    for asset in missing:
        targets_by_source.setdefault(asset.source, []).append(asset)

    installed: list[str] = []
    staging_dir = Path(tempfile.mkdtemp(prefix="posecap-models-"))
    try:
        for source, targets in targets_by_source.items():
            file_name = _source_file_name(source)
            report_status(f"Downloading {file_name}…")
            payload_path = staging_dir / file_name
            url, post_data = _request_for(source, credentials)
            fetch_callable(url, post_data, payload_path, report_progress)
            report_status(f"Installing {file_name}…")
            installed.extend(_place_targets(pear_root, source, targets, payload_path))
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
    return InstallReport(installed=tuple(installed))


def find_downloaded_model_archives(
    downloads_dir: Path,
    pear_root: Path,
    assets: tuple[ModelAsset, ...] = REQUIRED_MODEL_ASSETS,
) -> tuple[Path, ...]:
    """Return recognized model downloads whose targets are still missing."""
    useful_names = {
        _source_file_name(asset.source)
        for asset in missing_model_assets(pear_root, assets)
        if isinstance(asset.source, MpiDownload)
    }
    if not downloads_dir.is_dir():
        return ()
    return tuple(
        sorted(
            path
            for path in downloads_dir.iterdir()
            if path.is_file() and _matched_source_name(path.name, useful_names) is not None
        )
    )


def install_from_downloaded_archive(
    pear_root: Path,
    archive_path: Path,
    assets: tuple[ModelAsset, ...] = REQUIRED_MODEL_ASSETS,
) -> InstallReport:
    """Install every missing target served by a manually downloaded archive."""
    candidate_names = {
        _source_file_name(asset.source)
        for asset in missing_model_assets(pear_root, assets)
        if isinstance(asset.source, MpiDownload)
    }
    matched = _matched_source_name(archive_path.name, candidate_names)
    if matched is None:
        return InstallReport(installed=())
    targets = [
        asset
        for asset in missing_model_assets(pear_root, assets)
        if isinstance(asset.source, MpiDownload) and _source_file_name(asset.source) == matched
    ]
    if not targets:
        return InstallReport(installed=())
    installed = _place_targets(pear_root, targets[0].source, targets, archive_path)
    return InstallReport(installed=tuple(installed))


def _matched_source_name(file_name: str, source_names: set[str]) -> str | None:
    """Match a Downloads file to an expected archive, tolerant of browser renames.

    Browsers append ' (1)', ' (2)', … before the extension on a re-download;
    the guide tells users to retry, so those variants must still be picked up.
    """
    if file_name in source_names:
        return file_name
    for source_name in source_names:
        stem, _, extension = source_name.rpartition(".")
        prefix = f"{stem} (" if stem else f"{source_name} ("
        suffix = f").{extension}" if stem else ")"
        if file_name.startswith(prefix) and file_name.endswith(suffix):
            middle = file_name[len(prefix) : len(file_name) - len(suffix)]
            if middle.isdigit():
                return source_name
    return None


def _noop_progress(_bytes_done: int, _bytes_total: int) -> None:
    return None


def _source_file_name(source: MpiDownload | PublicDownload) -> str:
    if isinstance(source, MpiDownload):
        return source.sfile
    return source.url.rsplit("/", 1)[-1]


def _request_for(
    source: MpiDownload | PublicDownload,
    credentials: MpiCredentials,
) -> tuple[str, bytes | None]:
    if isinstance(source, MpiDownload):
        query = urllib.parse.urlencode(
            {"domain": source.domain, "sfile": source.sfile, "resume": "1"}
        )
        post_data = urllib.parse.urlencode(
            {"username": credentials.email, "password": credentials.password}
        ).encode("ascii")
        return f"{MPI_DOWNLOAD_URL}?{query}", post_data
    return source.url, None


def _place_targets(
    pear_root: Path,
    source: MpiDownload | PublicDownload,
    targets: list[ModelAsset],
    payload_path: Path,
) -> list[str]:
    _reject_html_payload(targets[0], payload_path)
    if isinstance(source, PublicDownload):
        _verify_public_hash(source, targets[0], payload_path)
    extraction_dir = Path(tempfile.mkdtemp(prefix="posecap-extract-"))
    try:
        member_tokens = getattr(source, "archive_member_tokens", ())
        if member_tokens:
            payload_path = _extract_member(payload_path, member_tokens, targets[0], extraction_dir)
        installed = []
        for asset in targets:
            _validate_payload(asset, payload_path)
            target = pear_root.joinpath(*asset.target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".part")
            shutil.copyfile(payload_path, temporary)
            os.replace(temporary, target)
            installed.append(asset.target_path[-1])
        return installed
    finally:
        shutil.rmtree(extraction_dir, ignore_errors=True)


def _reject_html_payload(asset: ModelAsset, payload_path: Path) -> None:
    head = _read_head(payload_path)
    stripped = head.lstrip()[:16].lower()
    if stripped.startswith((b"<!doctype", b"<html", b"<head", b"<body")):
        reason = download_failure_reason(asset, head, payload_path.stat().st_size)
        raise ModelSetupError(reason or "The download returned a web page, not the file.")


def _verify_public_hash(source: PublicDownload, asset: ModelAsset, payload_path: Path) -> None:
    digest = hashlib.sha256()
    with payload_path.open("rb") as payload:
        for chunk in iter(lambda: payload.read(_DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    if digest.hexdigest() != source.sha256:
        file_name = asset.target_path[-1]
        raise ModelSetupError(
            f"The downloaded {file_name} did not match its expected checksum. Please try again."
        )


def _extract_member(
    payload_path: Path,
    member_tokens: tuple[str, ...],
    asset: ModelAsset,
    extraction_dir: Path,
) -> Path:
    file_name = asset.target_path[-1]
    try:
        with zipfile.ZipFile(payload_path) as archive:
            members = [
                name
                for name in archive.namelist()
                if not name.endswith("/") and archive_member_matches(name, member_tokens)
            ]
            if not members:
                raise ModelSetupError(
                    f"The downloaded archive does not contain {file_name}. "
                    "Please retry, or download it manually from the official site."
                )
            if len(members) > 1:
                raise ModelSetupError(
                    f"The downloaded archive has more than one file that could be "
                    f"{file_name}; cannot tell which is correct. Please download it "
                    "manually from the official site."
                )
            member = members[0]
            extracted = extraction_dir / file_name
            with archive.open(member) as source, extracted.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            return extracted
    except zipfile.BadZipFile as exc:
        raise ModelSetupError(
            f"The downloaded archive for {file_name} is corrupted. Please try again."
        ) from exc


def _validate_payload(asset: ModelAsset, payload_path: Path) -> None:
    reason = download_failure_reason(asset, _read_head(payload_path), payload_path.stat().st_size)
    if reason is not None:
        raise ModelSetupError(reason)


def _read_head(payload_path: Path) -> bytes:
    with payload_path.open("rb") as payload:
        return payload.read(_VALIDATION_HEAD_BYTES)


CommandRunner = Callable[..., object]


def verify_models_with_doctor(
    pear_root: Path,
    engine_executable: str,
    *,
    run: CommandRunner | None = None,
) -> str:
    """Run the engine doctor's asset check and return a user-facing summary.

    The wizard has already validated every placed file (magic + size) before this
    runs, so a doctor that cannot confirm is reassurance-or-deferral, never doubt —
    but the two are kept distinct instead of collapsed into one always-success line.

    A *timeout* is the expected cold-start case: this runs right after the
    download, when the engine's torch/pytorch3d import is cold — a warm doctor
    returns in ~5 s, a first cold import can take a couple of minutes — so a
    timeout reads as "installed and validated" (the files are; the doctor was just
    slow). A doctor that *fails to launch* or returns nothing usable is a different
    state (a broken engine install): that defers the user to PoseCap Doctor rather
    than asserting an engine self-check that never ran. It runs on the setup daemon
    thread (the panel already shows "Models installed."), so a long wait blocks
    nothing the user is looking at.
    """
    runner = run or _run_doctor_process
    validated = "Models installed and validated."
    deferred = "Models installed. Run PoseCap Doctor to confirm your engine setup."
    try:
        completed = runner(
            [engine_executable, "doctor", "--pear-root", str(pear_root)],
            capture_output=True,
            text=True,
            check=False,
            timeout=300.0,
        )
        report = json.loads(getattr(completed, "stdout", ""))
        checks = report.get("checks", []) if isinstance(report, dict) else []
        asset_check = next((check for check in checks if check.get("name") == "pear_assets"), None)
    except subprocess.TimeoutExpired:
        return validated
    except (OSError, ValueError, subprocess.SubprocessError):
        return deferred
    if asset_check is None:
        return deferred
    if asset_check.get("status") == "ok":
        return "Models installed — doctor check passed."
    return str(asset_check.get("message", "Doctor reported a model problem."))


def _run_doctor_process(command: list[str], **kwargs: object) -> object:
    return subprocess.run(command, **kwargs)  # type: ignore[call-overload]  # kwargs forwarded verbatim


SessionState = str  # "IDLE" | "RUNNING" | "WATCHING" | "DONE" | "FAILED"


class ModelSetupSession:
    """One guided-setup run, polled from Blender's timer thread.

    Credential installs run on a daemon thread (downloads take minutes and
    must not block the UI); the Downloads-folder watcher is synchronous per
    tick. Status strings are user-facing.
    """

    def __init__(
        self,
        *,
        fetch: Fetcher | None = None,
        assets: tuple[ModelAsset, ...] = REQUIRED_MODEL_ASSETS,
        verify: Callable[[Path], str] | None = None,
    ) -> None:
        self._fetch = fetch
        self._assets = assets
        self._verify = verify
        self._thread: Thread | None = None
        self._pear_root: Path | None = None
        self._downloads_dir: Path | None = None
        self._finalizing = False
        self.state: SessionState = "IDLE"
        self.status_message = ""
        # Fraction (0..1) of the current file's download, or None when there is
        # nothing measurable to show — drives a real progress bar, not a spinner.
        self.progress_fraction: float | None = None
        self._status_base = ""

    def start_credential_install(self, pear_root: Path, credentials: MpiCredentials) -> None:
        """Download every missing model with the user's credentials, in background."""
        if self._thread is not None and self._thread.is_alive():
            return
        self.state = "RUNNING"
        self.status_message = "Starting download…"
        self._thread = Thread(
            target=self._run_credential_install,
            args=(pear_root, credentials),
            name="posecap-model-setup",
            daemon=True,
        )
        self._thread.start()

    def start_watching(self, pear_root: Path, downloads_dir: Path) -> None:
        """Watch the Downloads folder; installs happen on tick()."""
        self._pear_root = pear_root
        self._downloads_dir = downloads_dir
        self.state = "WATCHING"
        self.status_message = "Watching your Downloads folder…"

    def tick(self) -> None:
        """Install any recognized finished download; finish when nothing is missing.

        Runs on Blender's timer (main) thread, so only cheap local work
        happens here — archive placement is fast disk I/O. The completion
        step (a network fetch of the public file plus the doctor subprocess)
        is handed to a background thread so the UI never blocks.
        """
        if self.state != "WATCHING" or self._finalizing:
            return
        pear_root, downloads_dir = self._pear_root, self._downloads_dir
        if pear_root is None or downloads_dir is None:
            return
        for archive in find_downloaded_model_archives(downloads_dir, pear_root, self._assets):
            try:
                report = install_from_downloaded_archive(pear_root, archive, self._assets)
            except ModelSetupError as exc:
                # The file may still be downloading — report and keep watching.
                self.status_message = str(exc)
                continue
            if report.installed:
                self.status_message = f"Installed {', '.join(report.installed)}"
        remaining = missing_model_assets(pear_root, self._assets)
        if any(isinstance(asset.source, MpiDownload) for asset in remaining):
            return
        # Every license-gated file is present; finish off the main thread.
        self._finalizing = True
        self.state = "RUNNING"
        self.status_message = "Finishing setup…"
        self._thread = Thread(
            target=self._finish_watch,
            args=(pear_root,),
            name="posecap-model-setup-finish",
            daemon=True,
        )
        self._thread.start()

    def join(self, *, timeout_seconds: float) -> None:
        """Wait for a background credential install (tests and teardown)."""
        if self._thread is not None:
            self._thread.join(timeout=timeout_seconds)

    def _run_credential_install(self, pear_root: Path, credentials: MpiCredentials) -> None:
        try:
            install_missing_models(
                pear_root,
                credentials,
                fetch=self._fetch,
                status=self._set_status,
                progress=self._set_progress,
                assets=self._assets,
            )
        except ModelSetupError as exc:
            self.state = "FAILED"
            self.progress_fraction = None
            self.status_message = str(exc)
            return
        except Exception:
            self.state = "FAILED"
            self.status_message = (
                "Model setup failed unexpectedly — see the PoseCap log for details."
            )
            logging.getLogger(__name__).exception("model setup failed")
            return
        self._complete(pear_root)

    def _finish_watch(self, pear_root: Path) -> None:
        """Fetch the remaining public file and run the doctor, off the main thread."""
        try:
            if missing_model_assets(pear_root, self._assets):
                # Only the public, non-MPI-gated file can be left here.
                install_missing_models(
                    pear_root,
                    MpiCredentials(email="", password=""),
                    fetch=self._fetch,
                    status=self._set_status,
                    progress=self._set_progress,
                    assets=self._assets,
                )
        except ModelSetupError as exc:
            self.state = "WATCHING"
            self.status_message = str(exc)
            self._finalizing = False
            return
        except Exception:
            self.state = "FAILED"
            self.status_message = (
                "Model setup failed unexpectedly — see the PoseCap log for details."
            )
            logging.getLogger(__name__).exception("model setup finalize failed")
            self._finalizing = False
            return
        self._complete(pear_root)
        self._finalizing = False

    def _complete(self, pear_root: Path) -> None:
        if missing_model_assets(pear_root, self._assets):
            self.state = "FAILED"
            self.status_message = "Some model files are still missing."
            return
        self.state = "DONE"
        self.progress_fraction = None
        self.status_message = "Models installed."
        if self._verify is not None:
            self.status_message = self._verify(pear_root)

    def _set_status(self, message: str) -> None:
        # A new phase (Downloading X… / Installing X…) starts fresh: forget the
        # previous file's byte count so the bar text isn't stale.
        self._status_base = message
        self.progress_fraction = None
        self.status_message = message

    def _set_progress(self, bytes_done: int, bytes_total: int) -> None:
        """Turn per-file byte counts into a bar fraction plus a MB read-out."""
        if bytes_total <= 0:
            self.progress_fraction = None
            return
        self.progress_fraction = min(1.0, bytes_done / bytes_total)
        megabyte = 1024 * 1024
        base = self._status_base.rstrip("…") or "Downloading"
        self.status_message = f"{base} — {bytes_done // megabyte} / {bytes_total // megabyte} MB"


def _urllib_fetch(
    url: str,
    post_data: bytes | None,
    sink_path: Path,
    progress: ProgressCallback,
) -> None:
    # download.php authenticates the POST, sets a session cookie, and 302-redirects
    # to the file; the redirect target serves the file only if that cookie rides
    # along. urllib's default opener follows redirects but has no cookie handling,
    # so the redirect landed on an HTML login page instead of the model — every
    # credential download failed until this opener carried the cookie through
    # (root-caused live against download.is.tue.mpg.de, 2026-07-11).
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    request = urllib.request.Request(url, data=post_data)
    try:
        with opener.open(request, timeout=60.0) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with sink_path.open("wb") as sink:
                while True:
                    chunk = response.read(_DOWNLOAD_CHUNK_BYTES)
                    if chunk == b"":
                        return
                    sink.write(chunk)
                    done += len(chunk)
                    progress(done, total)
    except urllib.error.HTTPError as exc:
        # HTTPError is a URLError subclass, so it must be handled first. A refused
        # request is not a connection problem: 401/403 means the credentials, an
        # unconfirmed account, or rate-limiting after repeated downloads — saying
        # "check your internet" would send the user down the wrong path.
        if exc.code in (401, 403):
            raise ModelSetupError(
                "The download server refused the request (the account is not "
                "authorized). Check the email and password, confirm the account "
                "verification email, and — if you have downloaded several times "
                "just now — wait a few minutes before trying again."
            ) from exc
        raise ModelSetupError(
            f"The download server returned an error (HTTP {exc.code}). Please try again."
        ) from exc
    except urllib.error.URLError as exc:
        raise ModelSetupError(
            "Could not reach the download server. Check your internet connection and try again."
        ) from exc
