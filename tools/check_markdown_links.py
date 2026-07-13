"""Check that repository-relative Markdown links resolve to tracked paths."""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^)\s]+)")


def _tracked_markdown_files(root: Path) -> list[Path]:
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "*.md",
            ":(exclude).agents/**",
            ":(exclude).claude/**",
            ":(exclude)doc/reference/**",
            ":(exclude)WORKFLOW.md",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in completed.stdout.splitlines() if line]


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("files", nargs="*", type=Path)
    parsed = parser.parse_args(arguments)
    root = parsed.root.resolve()
    files = parsed.files or _tracked_markdown_files(root)

    errors: list[str] = []
    for relative_file in files:
        source = root / relative_file
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            for match in MARKDOWN_LINK.finditer(line):
                raw_target = match.group("target").strip("<>")
                parsed_target = urlparse(raw_target)
                if (
                    parsed_target.scheme
                    or parsed_target.netloc
                    or raw_target.startswith(("#", "/"))
                ):
                    continue
                link_path = unquote(parsed_target.path)
                if not link_path:
                    continue
                resolved = (source.parent / link_path).resolve()
                if not resolved.exists():
                    errors.append(
                        f"{relative_file.as_posix()}:{line_number}: "
                        f"missing relative link: {link_path}"
                    )

    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
