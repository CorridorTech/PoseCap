"""Licensed body-model assets the PEAR runtime requires.

Single source of truth for the files that must exist under the external
PEAR checkout's ``assets/`` tree (proven at runtime, task 0007), where each
file officially comes from, and how an installer validates a download.

License rule (PRD constraint): MPI-gated files are downloaded with the
user's own site credentials — registering on the official site is the
license-acceptance step — and are never bundled, redistributed, or fetched
anonymously. ``smpl_mean_params.npz`` is not hosted or gated by MPI (origin
is SPIN's public research data); it is fetched from a pinned public
revision and hash-enforced.
"""

from dataclasses import dataclass

MPI_DOWNLOAD_URL = "https://download.is.tue.mpg.de/download.php"


@dataclass(frozen=True)
class MpiDownload:
    """One ``download.php`` POST fetch (the ICON/PIXIE/DECA fetch pattern).

    ``archive_member_tokens`` selects a file inside a downloaded zip by the
    lowercased tokens its basename must all contain — tolerant of the naming
    drift between SMPL variants (the neutral member differs between the
    10- and 300-shape-component packages). Empty means the download is the
    target file itself, not an archive.
    """

    domain: str
    sfile: str
    signup_url: str
    archive_member_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class PublicDownload:
    """One pinned public fetch, hash-enforced because we control the pin."""

    url: str
    sha256: str


@dataclass(frozen=True)
class ModelAsset:
    """One required file under the PEAR checkout root."""

    target_path: tuple[str, ...]
    min_bytes: int
    source: MpiDownload | PublicDownload


# A pickle stream opens with the PROTO opcode (0x80) for protocol 2+, OR a
# printable opcode for the protocol-0/1 ASCII pickles that SMPL ships: a pickled
# dict/tuple opens with MARK "(", an object with GLOBAL "c", a list/dict with
# "]"/"}". Accepting only 0x80 falsely rejected the real neutral model (SMPL's
# SMPL_NEUTRAL.pkl is a protocol-0 pickle starting with "("). HTML error pages
# are already rejected before this check, so a permissive pickle magic is safe.
_PICKLE_MAGIC = (b"\x80", b"(", b"c", b"]", b"}")
_MAGIC_BY_EXTENSION = {
    ".pkl": _PICKLE_MAGIC,
    ".npz": (b"PK\x03\x04",),
    ".zip": (b"PK\x03\x04",),
}


def download_failure_reason(asset: ModelAsset, head: bytes, size: int) -> str | None:
    """Explain why a downloaded payload is not the expected file (None = valid).

    Messages are user-facing: they name the expected file and the likely fix,
    never a traceback. An HTML payload is the MPI endpoint's login page — the
    established signal for wrong credentials in the fetch-script pattern.
    """
    file_name = asset.target_path[-1]
    if _looks_like_html(head):
        return (
            f"The download for {file_name} returned a web page instead of the file. "
            "This usually means the email or password did not match your account "
            "on the official site — please check them and try again."
        )
    if size < asset.min_bytes:
        return (
            f"The download for {file_name} is incomplete "
            f"({size:,} bytes; expected at least {asset.min_bytes:,}). "
            "Please try again."
        )
    if not _matches_magic(file_name, head):
        return (
            f"The downloaded file does not look like {file_name}. "
            "Please retry, or download it manually from the official site."
        )
    return None


def _looks_like_html(head: bytes) -> bool:
    stripped = head.lstrip()[:64].lower()
    return stripped.startswith((b"<!doctype", b"<html", b"<head", b"<body"))


def _matches_magic(file_name: str, head: bytes) -> bool:
    dot_index = file_name.rfind(".")
    extension = file_name[dot_index:].lower() if dot_index >= 0 else ""
    expected = _MAGIC_BY_EXTENSION.get(extension)
    if expected is None:
        return True
    return any(head.startswith(magic) for magic in expected)


_SMPL_SIGNUP_URL = "https://smpl.is.tue.mpg.de/register.php"
_SMPLX_SIGNUP_URL = "https://smpl-x.is.tue.mpg.de/register.php"
_FLAME_SIGNUP_URL = "https://flame.is.tue.mpg.de/register.php"


def archive_member_matches(member_name: str, tokens: tuple[str, ...]) -> bool:
    """True when the archive member's basename satisfies every token (case-insensitive).

    A token that starts with "." is an extension suffix the basename must end
    with (so ".pkl" never matches "model.pkl.bak"); any other token must appear
    as a substring.
    """
    basename = member_name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for token in tokens:
        lowered = token.lower()
        if lowered.startswith("."):
            if not basename.endswith(lowered):
                return False
        elif lowered not in basename:
            return False
    return True


_FLAME_2020_DOWNLOAD = MpiDownload(
    domain="flame",
    sfile="FLAME2020.zip",
    signup_url=_FLAME_SIGNUP_URL,
    archive_member_tokens=("generic_model", ".pkl"),
)

REQUIRED_MODEL_ASSETS: tuple[ModelAsset, ...] = (
    ModelAsset(
        target_path=("assets", "SMPL", "SMPL_NEUTRAL.pkl"),
        min_bytes=20_000_000,
        source=MpiDownload(
            domain="smpl",
            sfile="SMPL_python_v.1.1.0.zip",
            signup_url=_SMPL_SIGNUP_URL,
            archive_member_tokens=("neutral", ".pkl"),
        ),
    ),
    ModelAsset(
        target_path=("assets", "SMPLX", "SMPLX_NEUTRAL_2020.npz"),
        min_bytes=100_000_000,
        source=MpiDownload(
            domain="smplx",
            sfile="SMPLX_NEUTRAL_2020.npz",
            signup_url=_SMPLX_SIGNUP_URL,
        ),
    ),
    ModelAsset(
        target_path=("assets", "SMPLX", "flame_generic_model.pkl"),
        min_bytes=20_000_000,
        source=_FLAME_2020_DOWNLOAD,
    ),
    ModelAsset(
        target_path=("assets", "SMPLX", "smpl_mean_params.npz"),
        min_bytes=1_000,
        source=PublicDownload(
            url=(
                "https://huggingface.co/spaces/brjathu/HMR2.0/resolve/"
                "998dfa865dddc3cdd4f4bed22a7c78a61cf9b32a/data/smpl_mean_params.npz"
            ),
            sha256="6fd6dd687800da946d0a0492383f973b92ec20f166a0b829775882868c35fcdd",
        ),
    ),
    ModelAsset(
        target_path=("assets", "FLAME", "FLAME2020", "generic_model.pkl"),
        min_bytes=20_000_000,
        source=_FLAME_2020_DOWNLOAD,
    ),
)
