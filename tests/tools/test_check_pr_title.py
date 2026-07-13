import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_PR_TITLE = REPO_ROOT / "tools" / "check_pr_title.py"


def test_non_conventional_pull_request_title_is_rejected() -> None:
    completed = subprocess.run(
        [sys.executable, str(CHECK_PR_TITLE), "Couple of reference links I wanted when read"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "expected Conventional Commit title" in completed.stderr


def test_scoped_conventional_pull_request_title_is_accepted() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(CHECK_PR_TITLE),
            "ci(governance): enforce contribution gates",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
