"""Behavior tests for the guided SMPL-X body-model setup (task 0010)."""

import hashlib
import io
import json
import subprocess
import zipfile
from dataclasses import replace
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import pytest
from posecap_addon.model_setup import (
    ModelSetupError,
    ModelSetupSession,
    MpiCredentials,
    _urllib_fetch,
    find_downloaded_model_archives,
    install_from_downloaded_archive,
    install_missing_models,
    missing_model_assets,
)
from posecap_contracts import MPI_DOWNLOAD_URL, REQUIRED_MODEL_ASSETS, PublicDownload

CREDENTIALS = MpiCredentials(email="emmet@corridor.example", password="s3cret!pw")


def test_forbidden_download_is_reported_as_an_authorization_problem(monkeypatch, tmp_path) -> None:
    # A 403 (HTTPError, a URLError subclass) is the server refusing the account,
    # not a connectivity problem — the message must not send the user to check
    # their internet when the real fix is the credentials/verification/rate limit.
    import urllib.error
    import urllib.request

    class _ForbiddenOpener:
        def open(self, request, timeout=0.0):  # noqa: A003 - mirrors urllib API
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: _ForbiddenOpener())

    with pytest.raises(ModelSetupError) as raised:
        _urllib_fetch(
            "https://download.example/download.php", b"user=x", tmp_path / "f", lambda d, t: None
        )

    message = str(raised.value).lower()
    assert "internet" not in message, "a 403 is not a connectivity error"
    assert "authorized" in message or "password" in message


@cache
def _zip_payload(member_name: str, member_bytes: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, member_bytes)
    return buffer.getvalue()


@cache
def _pkl_bytes(minimum: int) -> bytes:
    # A minimal valid pickle opcode opening (PROTO, EMPTY_DICT, BINPUT) so the
    # magic check sees a real opcode stream, padded past the size floor.
    return b"\x80\x02}q\x01" + bytes(minimum)


@cache
def _npz_bytes(minimum: int) -> bytes:
    return b"PK\x03\x04" + bytes(minimum)


_MEAN_PARAMS_PAYLOAD = b"PK\x03\x04" + bytes(2_000)


def _test_assets() -> tuple:
    """The real manifest with the public pin recomputed for the canned payload."""
    assets = []
    for asset in REQUIRED_MODEL_ASSETS:
        if isinstance(asset.source, PublicDownload):
            source = replace(asset.source, sha256=hashlib.sha256(_MEAN_PARAMS_PAYLOAD).hexdigest())
            asset = replace(asset, source=source)
        assets.append(asset)
    return tuple(assets)


class _RecordingFetcher:
    """Serves canned payloads and records every request."""

    def __init__(self, payload_overrides: dict[str, bytes] | None = None) -> None:
        self.requests: list[tuple[str, bytes | None]] = []
        self._overrides = payload_overrides or {}

    def __call__(self, url: str, post_data: bytes | None, sink_path: Path, progress) -> None:
        self.requests.append((url, post_data))
        payload = self._payload_for(url)
        sink_path.write_bytes(payload)
        progress(len(payload), len(payload))

    def _payload_for(self, url: str) -> bytes:
        for marker, payload in self._overrides.items():
            if marker in url:
                return payload
        if "sfile=SMPL_python_v.1.1.0.zip" in url:
            return _zip_payload(
                "SMPL_python_v.1.1.0/smpl/models/basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl",
                _pkl_bytes(20_000_001),
            )
        if "sfile=SMPLX_NEUTRAL_2020.npz" in url:
            return _npz_bytes(100_000_001)
        if "sfile=FLAME2020.zip" in url:
            return _zip_payload("generic_model.pkl", _pkl_bytes(20_000_001))
        if "smpl_mean_params.npz" in url:
            return _MEAN_PARAMS_PAYLOAD
        raise AssertionError(f"unexpected download url: {url}")


def _create_asset_files(pear_root: Path, *names: str) -> None:
    for asset in REQUIRED_MODEL_ASSETS:
        if asset.target_path[-1] in names:
            target = pear_root.joinpath(*asset.target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"\x80stub")


def test_all_assets_missing_on_a_fresh_pear_checkout(tmp_path: Path) -> None:
    missing = missing_model_assets(tmp_path)
    assert {asset.target_path[-1] for asset in missing} == {
        "SMPL_NEUTRAL.pkl",
        "SMPLX_NEUTRAL_2020.npz",
        "flame_generic_model.pkl",
        "smpl_mean_params.npz",
        "generic_model.pkl",
    }


def test_present_assets_are_not_reported_missing(tmp_path: Path) -> None:
    _create_asset_files(tmp_path, "SMPLX_NEUTRAL_2020.npz", "smpl_mean_params.npz")
    missing_names = {asset.target_path[-1] for asset in missing_model_assets(tmp_path)}
    assert "SMPLX_NEUTRAL_2020.npz" not in missing_names
    assert "SMPL_NEUTRAL.pkl" in missing_names


def test_credential_path_installs_every_missing_model_end_to_end(tmp_path: Path) -> None:
    fetcher = _RecordingFetcher()

    report = install_missing_models(tmp_path, CREDENTIALS, fetch=fetcher, assets=_test_assets())

    assert missing_model_assets(tmp_path) == ()
    assert set(report.installed) == {
        "SMPL_NEUTRAL.pkl",
        "SMPLX_NEUTRAL_2020.npz",
        "flame_generic_model.pkl",
        "smpl_mean_params.npz",
        "generic_model.pkl",
    }
    mpi_requests = [(url, post) for url, post in fetcher.requests if "download.php" in url]
    assert len(mpi_requests) == 3, "one fetch per MPI archive — FLAME zip must not repeat"
    for url, post_data in mpi_requests:
        assert url.startswith(MPI_DOWNLOAD_URL)
        assert post_data is not None
        assert b"username=emmet%40corridor.example" in post_data
        assert b"password=s3cret%21pw" in post_data
    public_requests = [(url, post) for url, post in fetcher.requests if "download.php" not in url]
    assert len(public_requests) == 1
    assert public_requests[0][1] is None, "public download must not carry MPI credentials"


def test_wrong_password_yields_a_friendly_retry_message_and_no_partial_files(
    tmp_path: Path,
) -> None:
    login_page = b"<!DOCTYPE html><html><body>Sign in</body></html>"
    fetcher = _RecordingFetcher(payload_overrides={"download.php": login_page})

    with pytest.raises(ModelSetupError, match="password"):
        install_missing_models(tmp_path, CREDENTIALS, fetch=fetcher, assets=_test_assets())

    leftovers = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert leftovers == [], "a failed download must not leave partial files behind"


def test_tampered_public_download_is_rejected_by_hash(tmp_path: Path) -> None:
    fetcher = _RecordingFetcher(
        payload_overrides={"smpl_mean_params.npz": b"PK\x03\x04" + bytes(3_000)}
    )

    with pytest.raises(ModelSetupError, match="smpl_mean_params.npz"):
        install_missing_models(tmp_path, CREDENTIALS, fetch=fetcher, assets=REQUIRED_MODEL_ASSETS)

    assert not tmp_path.joinpath("assets", "SMPLX", "smpl_mean_params.npz").exists()


def test_present_files_are_not_downloaded_again(tmp_path: Path) -> None:
    _create_asset_files(tmp_path, "SMPL_NEUTRAL.pkl")
    fetcher = _RecordingFetcher()

    install_missing_models(tmp_path, CREDENTIALS, fetch=fetcher, assets=_test_assets())

    assert not any("SMPL_python" in url for url, _post in fetcher.requests)


def test_credentials_never_reach_disk_or_repr(tmp_path: Path) -> None:
    fetcher = _RecordingFetcher()

    install_missing_models(tmp_path, CREDENTIALS, fetch=fetcher, assets=_test_assets())

    assert "s3cret" not in repr(CREDENTIALS)
    assert "s3cret" not in str(CREDENTIALS)
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"s3cret" not in path.read_bytes()


def test_manually_downloaded_flame_archive_installs_both_flame_targets(
    tmp_path: Path,
) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    (downloads / "FLAME2020.zip").write_bytes(
        _zip_payload("generic_model.pkl", _pkl_bytes(20_000_001))
    )

    found = find_downloaded_model_archives(downloads, pear_root)
    assert [path.name for path in found] == ["FLAME2020.zip"]

    report = install_from_downloaded_archive(pear_root, found[0])

    assert set(report.installed) == {"flame_generic_model.pkl", "generic_model.pkl"}
    assert pear_root.joinpath("assets", "SMPLX", "flame_generic_model.pkl").is_file()
    assert pear_root.joinpath("assets", "FLAME", "FLAME2020", "generic_model.pkl").is_file()
    assert [path.name for path in downloads.iterdir()] == ["FLAME2020.zip"], (
        "installing must not litter the user's Downloads folder"
    )


def test_smpl_zip_neutral_member_matches_variant_names(tmp_path: Path) -> None:
    """The in-zip neutral member name varies by SMPL variant (e.g. 300 shapes)."""
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    # A neutral member named differently from the exact pin, capital M, extra tag.
    (downloads / "SMPL_python_v.1.1.0.zip").write_bytes(
        _zip_payload(
            "SMPL_python_v.1.1.0/models/basicModel_NEUTRAL_lbs_300_207_0_v1.1.0.pkl",
            _pkl_bytes(20_000_001),
        )
    )

    found = find_downloaded_model_archives(downloads, pear_root)
    report = install_from_downloaded_archive(pear_root, found[0])

    assert "SMPL_NEUTRAL.pkl" in report.installed
    assert pear_root.joinpath("assets", "SMPL", "SMPL_NEUTRAL.pkl").is_file()


def test_smpl_zip_member_requires_pkl_suffix_not_substring(tmp_path: Path) -> None:
    """A 'neutral' file whose name only contains '.pkl' mid-string must not match."""
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    (downloads / "SMPL_python_v.1.1.0.zip").write_bytes(
        _zip_payload(
            "SMPL_python_v.1.1.0/models/basicmodel_neutral.pkl.bak", _pkl_bytes(20_000_001)
        )
    )

    with pytest.raises(ModelSetupError, match="SMPL_NEUTRAL.pkl"):
        install_from_downloaded_archive(pear_root, downloads / "SMPL_python_v.1.1.0.zip")


def test_ambiguous_neutral_members_fail_rather_than_guess(tmp_path: Path) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    buffer = __import__("io").BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("models/basicmodel_neutral_a.pkl", _pkl_bytes(20_000_001))
        archive.writestr("models/basicmodel_neutral_b.pkl", _pkl_bytes(20_000_001))
    (downloads / "SMPL_python_v.1.1.0.zip").write_bytes(buffer.getvalue())

    with pytest.raises(ModelSetupError, match="more than one|multiple|ambiguous"):
        install_from_downloaded_archive(pear_root, downloads / "SMPL_python_v.1.1.0.zip")


def test_smpl_zip_without_a_neutral_member_fails_friendly(tmp_path: Path) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    # Only gendered members — no neutral model to install.
    (downloads / "SMPL_python_v.1.1.0.zip").write_bytes(
        _zip_payload(
            "SMPL_python_v.1.1.0/models/basicModel_m_lbs_10_207_0_v1.1.0.pkl",
            _pkl_bytes(20_000_001),
        )
    )

    with pytest.raises(ModelSetupError, match="SMPL_NEUTRAL.pkl"):
        install_from_downloaded_archive(pear_root, downloads / "SMPL_python_v.1.1.0.zip")


def test_watcher_matches_browser_renamed_duplicate_downloads(tmp_path: Path) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    # A re-download the browser renamed to avoid clobbering the first attempt.
    (downloads / "FLAME2020 (1).zip").write_bytes(
        _zip_payload("generic_model.pkl", _pkl_bytes(20_000_001))
    )

    found = find_downloaded_model_archives(downloads, pear_root)
    assert [path.name for path in found] == ["FLAME2020 (1).zip"]

    report = install_from_downloaded_archive(pear_root, found[0])
    assert "generic_model.pkl" in report.installed


def test_watcher_ignores_unrelated_and_already_installed_files(tmp_path: Path) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    (downloads / "holiday-photo.zip").write_bytes(b"PK\x03\x04junk")
    (downloads / "SMPLX_NEUTRAL_2020.npz").write_bytes(_npz_bytes(100_000_001))
    _create_asset_files(pear_root, "SMPLX_NEUTRAL_2020.npz")

    assert find_downloaded_model_archives(downloads, pear_root) == ()


def test_credential_session_reports_progress_then_success(tmp_path: Path) -> None:
    session = ModelSetupSession(fetch=_RecordingFetcher(), assets=_test_assets())

    session.start_credential_install(tmp_path, CREDENTIALS)
    session.join(timeout_seconds=60.0)

    assert session.state == "DONE"
    assert "installed" in session.status_message.lower()
    assert missing_model_assets(tmp_path, _test_assets()) == ()


def test_credential_session_surfaces_friendly_failure(tmp_path: Path) -> None:
    login_page = b"<!DOCTYPE html><html><body>Sign in</body></html>"
    session = ModelSetupSession(
        fetch=_RecordingFetcher(payload_overrides={"download.php": login_page}),
        assets=_test_assets(),
    )

    session.start_credential_install(tmp_path, CREDENTIALS)
    session.join(timeout_seconds=60.0)

    assert session.state == "FAILED"
    assert "password" in session.status_message.lower()
    assert "Traceback" not in session.status_message


def test_watcher_session_installs_archives_as_they_appear(tmp_path: Path) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    session = ModelSetupSession(fetch=_RecordingFetcher(), assets=_test_assets())
    session.start_watching(pear_root, downloads)

    session.tick()
    assert session.state == "WATCHING"

    (downloads / "FLAME2020.zip").write_bytes(
        _zip_payload("generic_model.pkl", _pkl_bytes(20_000_001))
    )
    session.tick()
    assert pear_root.joinpath("assets", "SMPLX", "flame_generic_model.pkl").is_file()
    assert session.state == "WATCHING"

    (downloads / "SMPLX_NEUTRAL_2020.npz").write_bytes(_npz_bytes(100_000_001))
    (downloads / "SMPL_python_v.1.1.0.zip").write_bytes(
        _zip_payload(
            "SMPL_python_v.1.1.0/smpl/models/basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl",
            _pkl_bytes(20_000_001),
        )
    )
    # Completion (public fetch + doctor) runs on a background thread so the
    # Blender UI never blocks; the tick only spawns it.
    session.tick()
    session.join(timeout_seconds=60.0)

    assert session.state == "DONE", "public mean-params file must be fetched automatically"
    assert missing_model_assets(pear_root, _test_assets()) == ()


def test_watcher_completion_does_not_block_the_calling_thread(tmp_path: Path) -> None:
    """The Blocker fix: tick() must hand the network/doctor finish to a thread."""
    import threading

    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    for name, payload in (
        ("FLAME2020.zip", _zip_payload("generic_model.pkl", _pkl_bytes(20_000_001))),
        ("SMPLX_NEUTRAL_2020.npz", _npz_bytes(100_000_001)),
        (
            "SMPL_python_v.1.1.0.zip",
            _zip_payload(
                "SMPL_python_v.1.1.0/smpl/models/basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl",
                _pkl_bytes(20_000_001),
            ),
        ),
    ):
        (downloads / name).write_bytes(payload)

    release = threading.Event()

    def blocking_fetch(url, post_data, sink_path, progress) -> None:
        release.wait(timeout=5.0)
        _RecordingFetcher()(url, post_data, sink_path, progress)

    session = ModelSetupSession(fetch=blocking_fetch, assets=_test_assets())
    session.start_watching(pear_root, downloads)

    session.tick()  # must return immediately even though the fetch is blocked
    assert session.state == "RUNNING"
    release.set()
    session.join(timeout_seconds=60.0)
    assert session.state == "DONE"


def test_watcher_keeps_watching_when_the_public_fetch_fails(tmp_path: Path) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    for name, payload in (
        ("FLAME2020.zip", _zip_payload("generic_model.pkl", _pkl_bytes(20_000_001))),
        ("SMPLX_NEUTRAL_2020.npz", _npz_bytes(100_000_001)),
        (
            "SMPL_python_v.1.1.0.zip",
            _zip_payload(
                "SMPL_python_v.1.1.0/smpl/models/basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl",
                _pkl_bytes(20_000_001),
            ),
        ),
    ):
        (downloads / name).write_bytes(payload)

    login_page = b"<!DOCTYPE html><html><body>Sign in</body></html>"
    session = ModelSetupSession(
        fetch=_RecordingFetcher(payload_overrides={"smpl_mean_params.npz": login_page}),
        assets=_test_assets(),
    )
    session.start_watching(pear_root, downloads)

    session.tick()
    session.join(timeout_seconds=60.0)

    assert session.state == "WATCHING", "a failed finish must resume watching, not wedge"
    session.tick()  # must be able to retry, not be stuck finalizing


def test_watcher_session_keeps_watching_while_a_download_is_still_growing(
    tmp_path: Path,
) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    (downloads / "SMPLX_NEUTRAL_2020.npz").write_bytes(b"PK\x03\x04still downloading")
    session = ModelSetupSession(fetch=_RecordingFetcher(), assets=_test_assets())
    session.start_watching(pear_root, downloads)

    session.tick()

    assert session.state == "WATCHING"
    assert not pear_root.joinpath("assets", "SMPLX", "SMPLX_NEUTRAL_2020.npz").exists()


def test_session_runs_the_doctor_verification_after_a_successful_install(
    tmp_path: Path,
) -> None:
    session = ModelSetupSession(
        fetch=_RecordingFetcher(),
        assets=_test_assets(),
        verify=lambda _pear_root: "Models installed — doctor check passed.",
    )

    session.start_credential_install(tmp_path, CREDENTIALS)
    session.join(timeout_seconds=60.0)

    assert session.state == "DONE"
    assert session.status_message == "Models installed — doctor check passed."


def test_doctor_verification_reports_green_when_engine_doctor_finds_assets(
    tmp_path: Path,
) -> None:
    from posecap_addon.model_setup import verify_models_with_doctor

    def fake_run(command, **_kwargs):
        assert "doctor" in command
        report = {
            "ok": True,
            "checks": [{"name": "pear_assets", "status": "ok", "message": "present"}],
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr="")

    message = verify_models_with_doctor(tmp_path, "posecap-engine", run=fake_run)
    assert "installed" in message.lower()


def test_doctor_verification_names_missing_assets(tmp_path: Path) -> None:
    from posecap_addon.model_setup import verify_models_with_doctor

    def fake_run(command, **_kwargs):
        report = {
            "ok": False,
            "checks": [
                {
                    "name": "pear_assets",
                    "status": "error",
                    "message": "Licensed SMPL/SMPL-X/FLAME assets are missing",
                }
            ],
        }
        return SimpleNamespace(returncode=1, stdout=json.dumps(report), stderr="")

    message = verify_models_with_doctor(tmp_path, "posecap-engine", run=fake_run)
    assert "missing" in message.lower()


def test_doctor_verification_degrades_gracefully_without_the_engine(tmp_path: Path) -> None:
    from posecap_addon.model_setup import verify_models_with_doctor

    def fake_run(command, **_kwargs):
        raise OSError("engine executable not found")

    message = verify_models_with_doctor(tmp_path, "missing-engine", run=fake_run)
    assert message != ""
    assert "Traceback" not in message


def test_doctor_verification_reassures_when_the_cold_check_times_out(tmp_path: Path) -> None:
    """A cold torch/pytorch3d import can exceed the doctor timeout right after
    the download. The wizard already validated every file, so the fallback must
    read as success, not as doubt about whether the models are there."""
    from posecap_addon.model_setup import verify_models_with_doctor

    def fake_run(command, **kwargs):
        assert kwargs.get("timeout", 0) >= 300.0
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 300.0))

    message = verify_models_with_doctor(tmp_path, "posecap-engine", run=fake_run)
    assert "installed" in message.lower()
    assert "validated" in message.lower()
    assert "could not" not in message.lower()


def test_corrupted_manual_download_produces_a_friendly_message(tmp_path: Path) -> None:
    downloads = tmp_path / "Downloads"
    pear_root = tmp_path / "pear"
    downloads.mkdir()
    corrupted = downloads / "FLAME2020.zip"
    corrupted.write_bytes(b"PK\x03\x04this is not a real archive")

    with pytest.raises(ModelSetupError) as excinfo:
        install_from_downloaded_archive(pear_root, corrupted)

    message = str(excinfo.value)
    assert "FLAME2020.zip" in message or "generic_model.pkl" in message
    assert "Traceback" not in message


def test_urllib_fetch_carries_the_session_cookie_across_the_download_redirect(tmp_path):
    """The real MPI download authenticates the POST, sets a session cookie, and
    302-redirects to the file; the redirect target serves the file only if that
    cookie rides along. urllib's default opener follows the redirect but drops
    the cookie, so the shipped credential download returned an HTML login page
    instead of the model (confirmed live against download.is.tue.mpg.de,
    2026-07-11). This guards the cookie-across-redirect behavior."""
    import http.server
    import threading

    from posecap_addon.model_setup import _urllib_fetch

    file_bytes = b"PK\x03\x04" + b"BODYMODEL" * 512
    html_login = b"<!DOCTYPE html><html><head><title>Login</title></head></html>"

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(302)
            self.send_header("Set-Cookie", "sid=abc123; Path=/")
            self.send_header("Location", "/file")
            self.end_headers()

        def do_GET(self):
            gated = "sid=abc123" in (self.headers.get("Cookie") or "")
            body = file_bytes if gated else html_login
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/octet-stream" if gated else "text/html",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sink = tmp_path / "out.bin"
        _urllib_fetch(
            f"http://127.0.0.1:{port}/download.php",
            b"username=x&password=y",
            sink,
            lambda _done, _total: None,
        )
        assert sink.read_bytes() == file_bytes, (
            "the session cookie must ride the redirect, or the download is an HTML login page"
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_install_forwards_download_progress_instead_of_discarding_it(tmp_path: Path) -> None:
    # The per-file byte progress used to be dropped (_noop_progress), so the UI
    # could only show a spinner. It must now reach the caller for a real bar.
    seen: list[tuple[int, int]] = []
    install_missing_models(
        tmp_path,
        CREDENTIALS,
        fetch=_RecordingFetcher(),
        progress=lambda done, total: seen.append((done, total)),
        assets=_test_assets(),
    )
    assert seen, "per-file progress must reach the caller"
    assert all(total > 0 for _done, total in seen)


def test_download_progress_surfaces_as_a_bar_fraction_and_mb_readout(tmp_path: Path) -> None:
    captured: list[tuple[float | None, str]] = []
    base = _RecordingFetcher()
    session_box: dict[str, ModelSetupSession] = {}

    def fetch(url: str, post_data: bytes | None, sink_path: Path, progress) -> None:
        progress(25 * 1024 * 1024, 100 * 1024 * 1024)  # 25 of 100 MB
        session = session_box["session"]
        captured.append((session.progress_fraction, session.status_message))
        base(url, post_data, sink_path, progress)

    session = ModelSetupSession(fetch=fetch, assets=_test_assets())
    session_box["session"] = session
    session.start_credential_install(tmp_path, CREDENTIALS)
    session.join(timeout_seconds=60.0)

    fraction, status = captured[0]
    assert fraction == pytest.approx(0.25)
    assert "25" in status and "MB" in status
    # When everything is installed the bar clears so it does not sit at a stale value.
    assert session.progress_fraction is None
