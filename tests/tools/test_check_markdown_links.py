import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_LINKS = REPO_ROOT / "tools" / "check_markdown_links.py"


def test_missing_relative_markdown_link_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Read the [missing guide](doc/missing.md).\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(CHECK_LINKS), "--root", str(tmp_path), "README.md"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "README.md:1: missing relative link: doc/missing.md" in completed.stderr
