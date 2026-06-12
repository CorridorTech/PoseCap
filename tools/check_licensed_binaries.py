"""Pre-commit gate: licensed model binaries never enter the repo (AGENTS.md Security)."""

import sys

FORBIDDEN_EXTENSIONS = {".npz", ".pkl", ".pt", ".ckpt", ".onnx", ".engine"}


def main() -> int:
    flagged = [
        path
        for path in sys.argv[1:]
        if any(path.lower().endswith(extension) for extension in FORBIDDEN_EXTENSIONS)
    ]
    if not flagged:
        return 0
    print("Licensed/model binary extensions are never committed (AGENTS.md Security & Privacy):")
    for path in flagged:
        print(f"  {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
