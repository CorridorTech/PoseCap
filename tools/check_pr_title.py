"""Validate that a pull request title is a Conventional Commit subject."""

import re
import sys

TITLE = re.compile(
    r"^(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?!?: [a-z0-9].+$"
)


def main(arguments: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1:
        print("usage: check_pr_title.py <title>", file=sys.stderr)
        return 2

    title = arguments[0]
    if len(title) > 72 or TITLE.fullmatch(title) is None:
        print(
            "expected Conventional Commit title, for example: docs(readme): add license reference",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
