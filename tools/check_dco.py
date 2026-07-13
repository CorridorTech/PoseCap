"""Validate Developer Certificate of Origin trailers in a commit range."""

from __future__ import annotations

import re
import subprocess
import sys

SIGN_OFF = re.compile(
    r"^Signed-off-by:\s+(?P<name>.+)\s+<(?P<email>[^>]+)>\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def main(arguments: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 2:
        print("usage: check_dco.py <base> <head>", file=sys.stderr)
        return 2

    base, head = arguments
    try:
        commits = _git("rev-list", "--reverse", f"{base}..{head}").splitlines()
    except subprocess.CalledProcessError:
        print(f"invalid commit range: {base}..{head}", file=sys.stderr)
        return 2
    errors: list[str] = []
    for commit in commits:
        if len(_git("rev-list", "--parents", "-n", "1", commit).split()) > 2:
            continue
        message = _git("show", "-s", "--format=%B", commit)
        sign_offs = list(SIGN_OFF.finditer(message))
        if not sign_offs:
            errors.append(f"{commit}: missing Signed-off-by trailer")
            continue

        identity = _git("show", "-s", "--format=%an%x00%ae%x00%cn%x00%ce", commit)
        author_name, author_email, committer_name, committer_email = identity.rstrip().split("\0")
        valid_identities = {
            (author_name.casefold(), author_email.casefold()),
            (committer_name.casefold(), committer_email.casefold()),
        }
        if not any(
            (match.group("name").casefold(), match.group("email").casefold()) in valid_identities
            for match in sign_offs
        ):
            errors.append(f"{commit}: Signed-off-by must match {author_name} <{author_email}>")

    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
