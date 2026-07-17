"""Validate a commit subject with the same rule CI applies to PR titles.

CI's ``tools/check_pr_title.py`` enforces a Conventional Commit subject of at
most 72 characters, but a PR title only exists at ``gh pr create`` time, so no
pre-push hook can catch a bad one -- it has broken ``CI required`` more than
once (PR 77, PR 96). This commit-msg hook closes that gap at the earliest
point: it validates the commit *subject* against the exact same checker, so an
invalid subject is blocked at commit time and any PR title derived from it is
already valid. It shells out to ``check_pr_title.py`` rather than duplicating
the regex, so the two can never drift.

Auto-generated subjects that are not authored Conventional Commits (merge,
revert, and autosquash markers) are skipped, matching how pre-commit itself
leaves them alone.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SKIP_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ", "amend! ")


def _subject(commit_msg: str) -> str:
    """First non-comment, non-blank line of the commit message."""
    for line in commit_msg.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        return line
    return ""


def main(arguments: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1:
        print("usage: check_commit_subject.py <commit-msg-file>", file=sys.stderr)
        return 2

    subject = _subject(Path(arguments[0]).read_text(encoding="utf-8"))
    if not subject or subject.startswith(_SKIP_PREFIXES):
        return 0

    checker = Path(__file__).with_name("check_pr_title.py")
    return subprocess.run([sys.executable, str(checker), subject], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
