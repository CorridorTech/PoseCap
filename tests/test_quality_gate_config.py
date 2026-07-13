import re
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _local_hooks() -> list[dict[str, Any]]:
    config = _load_yaml(REPO_ROOT / ".pre-commit-config.yaml")
    hooks: list[dict[str, Any]] = []
    for repo in config["repos"]:
        assert isinstance(repo, dict)
        for hook in repo.get("hooks", []):
            assert isinstance(hook, dict)
            hooks.append(cast(dict[str, Any], hook))
    return hooks


def test_pre_push_pyright_checks_windows_and_linux_platforms() -> None:
    pyright_entries = {
        str(hook["entry"])
        for hook in _local_hooks()
        if str(hook.get("id", "")).startswith("pyright") and hook.get("stages") == ["pre-push"]
    }

    assert "uv run pyright --pythonplatform Windows" in pyright_entries
    assert "uv run pyright --pythonplatform Linux" in pyright_entries


def test_pre_commit_install_defaults_include_pre_push() -> None:
    config = _load_yaml(REPO_ROOT / ".pre-commit-config.yaml")

    assert set(config["default_install_hook_types"]) == {"pre-commit", "pre-push"}


def test_pre_push_rejects_unsigned_commits() -> None:
    dco_hooks = [hook for hook in _local_hooks() if hook.get("id") == "dco-signoff"]

    assert dco_hooks == [
        {
            "id": "dco-signoff",
            "name": "DCO sign-off",
            "entry": "uv run python tools/check_dco.py origin/main HEAD",
            "language": "system",
            "pass_filenames": False,
            "stages": ["pre-push"],
        }
    ]


def test_pre_push_lints_github_workflows() -> None:
    workflow_hooks = {
        str(hook["id"]): hook
        for hook in _local_hooks()
        if hook.get("id") in {"actionlint", "zizmor"}
    }

    assert set(workflow_hooks) == {"actionlint", "zizmor"}
    assert workflow_hooks["actionlint"]["stages"] == ["pre-push"]
    assert workflow_hooks["zizmor"] == {
        "id": "zizmor",
        "name": "GitHub Actions security",
        "entry": "uv run zizmor .",
        "language": "system",
        "pass_filenames": False,
        "stages": ["pre-push"],
    }


def test_ci_type_gate_checks_windows_and_linux_platforms() -> None:
    workflow = _load_yaml(REPO_ROOT / ".github" / "workflows" / "ci.yml")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    quality = jobs["quality"]
    assert isinstance(quality, dict)
    steps = quality["steps"]
    assert isinstance(steps, list)

    commands = {
        str(step["run"])
        for step in steps
        if isinstance(step, dict) and step.get("name", "").startswith("Types")
    }

    assert "uv run pyright --pythonplatform Windows" in commands
    assert "uv run pyright --pythonplatform Linux" in commands


def test_ci_uses_least_privilege_and_immutable_actions() -> None:
    workflow = _load_yaml(REPO_ROOT / ".github" / "workflows" / "ci.yml")

    assert workflow["permissions"] == {"contents": "read"}
    workflow_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    action_references = re.findall(r"^\s*- uses:\s+([^\s#]+)", workflow_text, re.MULTILINE)
    assert action_references
    for reference in action_references:
        if reference.startswith("./"):
            continue
        assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference), reference


def test_ci_cancels_stale_runs_and_pins_python_311() -> None:
    workflow = _load_yaml(REPO_ROOT / ".github" / "workflows" / "ci.yml")

    assert workflow["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}",
        "cancel-in-progress": True,
    }
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    for job in jobs.values():
        assert isinstance(job, dict)
        assert 1 <= int(job["timeout-minutes"]) <= 30

    quality = jobs["quality"]
    setup_python = [
        step
        for step in quality["steps"]
        if isinstance(step, dict) and str(step.get("uses", "")).startswith("actions/setup-python@")
    ]
    assert setup_python == [
        {
            "uses": "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
            "with": {"python-version": "3.11"},
        }
    ]


def test_ci_enforces_dco_workflow_security_and_stable_required_gate() -> None:
    workflow = _load_yaml(REPO_ROOT / ".github" / "workflows" / "ci.yml")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    dco = jobs["dco"]
    assert dco["name"] == "DCO sign-off"
    assert dco["if"] == "github.event_name == 'pull_request'"
    dco_command = (
        "uv run python tools/check_dco.py "
        "${{ github.event.pull_request.base.sha }} "
        "${{ github.event.pull_request.head.sha }}"
    )
    assert any(step.get("run") == dco_command for step in dco["steps"] if isinstance(step, dict))
    title_steps = [
        step
        for step in dco["steps"]
        if isinstance(step, dict)
        and step.get("run") == 'uv run python tools/check_pr_title.py "$PR_TITLE"'
    ]
    assert title_steps == [
        {
            "name": "Validate pull request title",
            "env": {"PR_TITLE": "${{ github.event.pull_request.title }}"},
            "run": 'uv run python tools/check_pr_title.py "$PR_TITLE"',
        }
    ]

    workflow_security = jobs["workflow-security"]
    security_commands = {
        str(step["run"])
        for step in workflow_security["steps"]
        if isinstance(step, dict) and "run" in step
    }
    assert security_commands == {
        "uv run pre-commit run --hook-stage pre-push actionlint --all-files",
        "uv run zizmor .",
    }

    audit_commands = {
        str(step["run"])
        for step in jobs["audit"]["steps"]
        if isinstance(step, dict) and "run" in step
    }
    assert (
        "uv export --locked --format requirements.txt --no-emit-workspace -o requirements-audit.txt"
        in audit_commands
    )
    assert "uv run pip-audit -r requirements-audit.txt" in audit_commands
    assert not any("uvx pip-audit" in command for command in audit_commands)

    required = jobs["required"]
    assert required["name"] == "CI required"
    assert required["if"] == "always()"
    assert set(required["needs"]) == {
        "quality",
        "licensed-binaries",
        "audit",
        "dco",
        "workflow-security",
        "package",
    }


def test_ci_builds_and_smoke_installs_distributable_packages() -> None:
    workflow = _load_yaml(REPO_ROOT / ".github" / "workflows" / "ci.yml")
    package = workflow["jobs"]["package"]
    commands = [
        str(step["run"]) for step in package["steps"] if isinstance(step, dict) and "run" in step
    ]

    expected_commands = [
        "uv sync --locked",
        "uv build --all-packages --out-dir build/wheels",
        (
            "uv run python tools/build_extension.py --output-dir build/extension "
            "--staging-dir build/extension-stage --release"
        ),
        "uv venv build/smoke-venv --python 3.11",
        (
            "uv pip install --python build/smoke-venv --find-links build/wheels "
            "posecap-contracts posecap-core posecap-engine"
        ),
        (
            'uv run --python build/smoke-venv --no-project python -c "import '
            'posecap_contracts, posecap_core, posecap_engine"'
        ),
    ]
    assert commands == expected_commands


def test_ci_rejects_broken_repository_documentation_links() -> None:
    workflow = _load_yaml(REPO_ROOT / ".github" / "workflows" / "ci.yml")
    commands = {
        str(step["run"])
        for step in workflow["jobs"]["quality"]["steps"]
        if isinstance(step, dict) and "run" in step
    }

    assert "uv run python tools/check_markdown_links.py" in commands
    link_hooks = [hook for hook in _local_hooks() if hook.get("id") == "markdown-links"]
    assert link_hooks == [
        {
            "id": "markdown-links",
            "name": "repository Markdown links",
            "entry": "uv run python tools/check_markdown_links.py",
            "language": "system",
            "pass_filenames": False,
            "stages": ["pre-push"],
        }
    ]
