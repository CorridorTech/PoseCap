"""Deterministic import-boundary gates for the layers import-linter cannot see.

import-linter enforces the contracts/core/engine boundaries (pyproject
`[tool.importlinter]`), but the addon package is not installed in the workspace
venv, and a forbidden-list cannot prove `contracts/` stays stdlib-only. These
AST scans close both gaps per GUIDELINES section 1 so the dependency rule is
enforced in CI for every layer, not by review memory.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

_ADDON_FORBIDDEN = {"posecap_engine", "torch"}


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_addon_never_imports_engine_or_torch() -> None:
    offenders = {
        f"{path.relative_to(REPO_ROOT)}: {found}"
        for path in (REPO_ROOT / "addon").rglob("*.py")
        if (found := sorted(_top_level_imports(path) & _ADDON_FORBIDDEN))
    }
    assert not offenders, (
        f"addon must launch the engine via subprocess, never import it: {offenders}"
    )


def test_contracts_imports_stdlib_only() -> None:
    allowed = set(sys.stdlib_module_names) | {"posecap_contracts"}
    offenders = {
        f"{path.relative_to(REPO_ROOT)}: {found}"
        for path in (REPO_ROOT / "contracts" / "src").rglob("*.py")
        if (found := sorted(_top_level_imports(path) - allowed))
    }
    assert not offenders, f"contracts is the innermost layer, stdlib only: {offenders}"
