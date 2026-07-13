from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_DCO = REPO_ROOT / "tools" / "check_dco.py"


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _repository_with_base(tmp_path: Path) -> tuple[Path, Path, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Example Contributor")
    _git(repository, "config", "user.email", "contributor@example.com")

    tracked_file = repository / "tracked.txt"
    tracked_file.write_text("base\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-s", "-m", "test: establish base")
    base = _git(repository, "rev-parse", "HEAD")
    return repository, tracked_file, base


def test_unsigned_commit_is_rejected(tmp_path: Path) -> None:
    repository, tracked_file, base = _repository_with_base(tmp_path)

    tracked_file.write_text("unsigned\n", encoding="utf-8")
    _git(repository, "commit", "-am", "docs: omit sign-off")
    unsigned_commit = _git(repository, "rev-parse", "HEAD")

    completed = subprocess.run(
        [sys.executable, str(CHECK_DCO), base, "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert f"{unsigned_commit}: missing Signed-off-by trailer" in completed.stderr


def test_sign_off_must_match_commit_author(tmp_path: Path) -> None:
    repository, tracked_file, base = _repository_with_base(tmp_path)

    tracked_file.write_text("mismatch\n", encoding="utf-8")
    _git(
        repository,
        "commit",
        "-am",
        "docs: use another identity",
        "-m",
        "Signed-off-by: Someone Else <else@example.com>",
    )
    mismatched_commit = _git(repository, "rev-parse", "HEAD")

    completed = subprocess.run(
        [sys.executable, str(CHECK_DCO), base, "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert (
        f"{mismatched_commit}: Signed-off-by must match "
        "Example Contributor <contributor@example.com>"
    ) in completed.stderr


def test_sign_off_name_and_email_must_belong_to_same_identity(tmp_path: Path) -> None:
    repository, tracked_file, base = _repository_with_base(tmp_path)

    tracked_file.write_text("crossed identity\n", encoding="utf-8")
    _git(
        repository,
        "-c",
        "user.name=Example Committer",
        "-c",
        "user.email=committer@example.com",
        "commit",
        "-am",
        "docs: reject crossed identity",
        "--author",
        "Example Author <author@example.com>",
        "-m",
        "Signed-off-by: Example Author <committer@example.com>",
    )

    completed = subprocess.run(
        [sys.executable, str(CHECK_DCO), base, "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1


def test_invalid_commit_range_has_actionable_error(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")

    completed = subprocess.run(
        [sys.executable, str(CHECK_DCO), "missing-base", "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "invalid commit range: missing-base..HEAD" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_merge_commit_does_not_require_a_second_sign_off(tmp_path: Path) -> None:
    repository, _, base = _repository_with_base(tmp_path)

    _git(repository, "switch", "-c", "feature")
    (repository / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(repository, "add", "feature.txt")
    _git(repository, "commit", "-s", "-m", "docs: add feature reference")

    _git(repository, "switch", "master")
    (repository / "main.txt").write_text("main\n", encoding="utf-8")
    _git(repository, "add", "main.txt")
    _git(repository, "commit", "-s", "-m", "docs: update main reference")

    _git(repository, "switch", "feature")
    _git(repository, "merge", "--no-ff", "master", "-m", "Merge main")

    completed = subprocess.run(
        [sys.executable, str(CHECK_DCO), base, "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
