from posecap_contracts import REQUIRED_MODEL_ASSETS, MpiDownload, PublicDownload
from posecap_contracts.model_assets import download_failure_reason

_SMPLX_NPZ = next(
    asset for asset in REQUIRED_MODEL_ASSETS if asset.target_path[-1] == "SMPLX_NEUTRAL_2020.npz"
)


def test_required_assets_cover_the_five_pear_runtime_files() -> None:
    targets = {asset.target_path for asset in REQUIRED_MODEL_ASSETS}
    assert targets == {
        ("assets", "SMPL", "SMPL_NEUTRAL.pkl"),
        ("assets", "SMPLX", "SMPLX_NEUTRAL_2020.npz"),
        ("assets", "SMPLX", "flame_generic_model.pkl"),
        ("assets", "SMPLX", "smpl_mean_params.npz"),
        ("assets", "FLAME", "FLAME2020", "generic_model.pkl"),
    }


def test_mpi_gated_assets_download_with_user_credentials_from_official_domains() -> None:
    mpi_sources = {
        asset.source for asset in REQUIRED_MODEL_ASSETS if isinstance(asset.source, MpiDownload)
    }
    assert {(source.domain, source.sfile) for source in mpi_sources} == {
        ("smpl", "SMPL_python_v.1.1.0.zip"),
        ("smplx", "SMPLX_NEUTRAL_2020.npz"),
        ("flame", "FLAME2020.zip"),
    }
    assert all(source.signup_url.startswith("https://") for source in mpi_sources)


def test_archive_member_matches_treats_dot_token_as_a_suffix() -> None:
    from posecap_contracts.model_assets import archive_member_matches

    tokens = ("neutral", ".pkl")
    assert archive_member_matches("dir/basicModel_NEUTRAL_lbs.pkl", tokens)
    assert not archive_member_matches("dir/basicmodel_neutral.pkl.bak", tokens)
    assert not archive_member_matches("dir/basicmodel_male.pkl", tokens)
    # backslash-separated members (zip written on Windows) resolve by basename
    assert archive_member_matches("SMPL\\models\\neutral_model.pkl", tokens)


def test_mean_params_is_the_only_public_download_and_is_hash_pinned() -> None:
    public = [asset for asset in REQUIRED_MODEL_ASSETS if isinstance(asset.source, PublicDownload)]
    assert [asset.target_path[-1] for asset in public] == ["smpl_mean_params.npz"]
    source = public[0].source
    assert isinstance(source, PublicDownload)
    assert len(source.sha256) == 64


def test_html_response_is_reported_as_a_sign_in_problem_not_a_traceback() -> None:
    login_page = b"<!DOCTYPE html><html><body>You must sign in</body></html>"
    reason = download_failure_reason(_SMPLX_NPZ, login_page, len(login_page))
    assert reason is not None
    assert "password" in reason.lower() or "sign in" in reason.lower()
    assert "SMPLX_NEUTRAL_2020.npz" in reason


def test_truncated_download_names_the_expected_file() -> None:
    head = b"PK\x03\x04partial"
    reason = download_failure_reason(_SMPLX_NPZ, head, 12_345)
    assert reason is not None
    assert "SMPLX_NEUTRAL_2020.npz" in reason


def test_wrong_content_names_the_expected_file() -> None:
    head = b"\x00\x00\x00\x00garbage" + b"\x00" * 64
    reason = download_failure_reason(_SMPLX_NPZ, head, _SMPLX_NPZ.min_bytes + 1)
    assert reason is not None
    assert "SMPLX_NEUTRAL_2020.npz" in reason


def test_valid_looking_download_passes_validation() -> None:
    head = b"PK\x03\x04" + b"\x00" * 64
    assert download_failure_reason(_SMPLX_NPZ, head, _SMPLX_NPZ.min_bytes + 1) is None


_SMPL_PKL = next(
    asset for asset in REQUIRED_MODEL_ASSETS if asset.target_path[-1] == "SMPL_NEUTRAL.pkl"
)


def test_protocol_0_pickle_passes_validation() -> None:
    # SMPL ships SMPL_NEUTRAL.pkl as a protocol-0 (ASCII) pickle that opens with
    # "(dp0" — real bytes from the official model. A magic check accepting only
    # 0x80 (protocol 2+) falsely rejected it as "does not look like the file".
    protocol_0 = b"(dp0\nS'J_regressor_prior'\np1\n" + b"\x00" * 64
    assert download_failure_reason(_SMPL_PKL, protocol_0, _SMPL_PKL.min_bytes + 1) is None


def test_protocol_2_pickle_passes_validation() -> None:
    protocol_2 = b"\x80\x02}q\x01(" + b"\x00" * 64
    assert download_failure_reason(_SMPL_PKL, protocol_2, _SMPL_PKL.min_bytes + 1) is None


def test_a_pkl_that_is_not_a_pickle_is_still_rejected() -> None:
    head = b"\x00\x01\x02\x03 not a pickle at all " + b"\x00" * 64
    reason = download_failure_reason(_SMPL_PKL, head, _SMPL_PKL.min_bytes + 1)
    assert reason is not None
    assert "SMPL_NEUTRAL.pkl" in reason


def test_ascii_that_is_not_a_pickle_stream_is_rejected() -> None:
    # The opcode-walking check must not wave through arbitrary ASCII just because
    # its bytes happen to be mid-stream pickle opcodes: a real pickle OPENS with
    # a stream-opening opcode (PROTO / MARK / a global / an empty container),
    # never with APPEND/SETITEM. This over-size, non-HTML text must be rejected.
    head = b"this is not a pickle, just prose that clears the html and size gates " * 4
    reason = download_failure_reason(_SMPL_PKL, head, _SMPL_PKL.min_bytes + 1)
    assert reason is not None
    assert "SMPL_NEUTRAL.pkl" in reason
