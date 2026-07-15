from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def test_pull_request_template_collects_review_and_provenance_evidence() -> None:
    template = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")

    assert "## Why" in template
    assert "## Summary" in template
    assert "## Test plan" in template
    assert "## Links" in template
    assert "Signed-off-by" in template
    assert "licensed model assets" in template
    assert "agent-assisted" in template
    assert "human author" in template


def test_issue_forms_route_bug_feature_support_and_security_reports() -> None:
    issue_templates = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
    bug = _yaml(issue_templates / "bug.yml")
    feature = _yaml(issue_templates / "feature.yml")
    config = _yaml(issue_templates / "config.yml")

    assert bug["name"] == "Bug report"
    bug_ids = {field.get("id") for field in bug["body"] if isinstance(field, dict)}
    assert {
        "build",
        "windows",
        "blender",
        "gpu",
        "reproduction",
        "expected",
        "diagnostics",
    } <= bug_ids

    assert feature["name"] == "Feature request"
    feature_ids = {field.get("id") for field in feature["body"] if isinstance(field, dict)}
    assert {"outcome", "workflow", "value", "alternatives"} <= feature_ids

    assert config["blank_issues_enabled"] is False
    contact_urls = {contact["url"] for contact in config["contact_links"]}
    assert "https://github.com/CorridorTech/PoseCap/security/advisories/new" in contact_urls
    assert "https://github.com/CorridorTech/PoseCap/blob/main/SUPPORT.md" in contact_urls


def test_repository_policies_define_security_support_conduct_and_ownership() -> None:
    security = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    support = (REPO_ROOT / "SUPPORT.md").read_text(encoding="utf-8")
    conduct = (REPO_ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    codeowners = (REPO_ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "security/advisories/new" in security
    assert "Do not open a public issue" in security
    assert "Support Bundle" in support
    assert "private security report" in support
    assert "Contributor Covenant" in conduct
    assert "alexandre.alvaro@hotmail.com" in conduct
    assert "* @alexandremendoncaalvaro" in codeowners
    assert "@s-deanhughes" not in codeowners
    assert "sole code reviewer" in contributing
    assert "git clone https://github.com/CorridorTech/PoseCap.git" in contributing
    assert "git clone https://github.com/alexandremendoncaalvaro/PoseCap.git" not in contributing


def test_dependabot_updates_python_and_github_actions_with_bounded_noise() -> None:
    config = _yaml(REPO_ROOT / ".github" / "dependabot.yml")
    updates = config["updates"]
    assert isinstance(updates, list)
    by_ecosystem = {update["package-ecosystem"]: update for update in updates}

    assert set(by_ecosystem) == {"pip", "github-actions"}
    for update in by_ecosystem.values():
        assert update["directory"] == "/"
        assert update["schedule"]["interval"] == "weekly"
        assert update["cooldown"]["default-days"] == 7
        assert update["open-pull-requests-limit"] <= 5
        assert update["groups"]


def test_scorecard_publishes_signed_results_to_code_scanning() -> None:
    workflow = _yaml(REPO_ROOT / ".github" / "workflows" / "scorecard.yml")
    analysis = workflow["jobs"]["analysis"]

    assert workflow["permissions"] == "read-all"
    assert analysis["permissions"] == {
        "contents": "read",
        "security-events": "write",
        "id-token": "write",
    }
    references = {
        str(step["uses"]) for step in analysis["steps"] if isinstance(step, dict) and "uses" in step
    }
    assert any(reference.startswith("ossf/scorecard-action@") for reference in references)
    assert any(
        reference.startswith("github/codeql-action/upload-sarif@") for reference in references
    )
    assert all(
        reference.rsplit("@", 1)[-1].isalnum() and len(reference.rsplit("@", 1)[-1]) == 40
        for reference in references
    )


def test_release_workflow_uses_protected_runner_signing_and_attestation() -> None:
    path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    workflow = _yaml(path)
    workflow_text = path.read_text(encoding="utf-8")
    release = workflow["jobs"]["release"]
    actionlint = _yaml(REPO_ROOT / ".github" / "actionlint.yaml")

    assert 'tags: ["v*-win.*"]' in workflow_text
    assert "posecap-release" in actionlint["self-hosted-runner"]["labels"]
    assert release["runs-on"] == ["self-hosted", "Windows", "X64", "posecap-release"]
    assert release["environment"] == "release"
    assert release["permissions"] == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }
    commands = "\n".join(
        str(step["run"]) for step in release["steps"] if isinstance(step, dict) and "run" in step
    )
    assert "verification.verified" in commands
    assert 'expectedTag = "v$baseVersion-win.$buildNumber"' in commands
    assert "GITHUB_REF_NAME -cne $expectedTag" in commands
    assert "Set-AuthenticodeSignature" in commands
    assert "Get-AuthenticodeSignature" in commands
    assert "Get-FileHash -Algorithm SHA256" in commands
    assert "gh release create" in commands
    assert "https://github.com/$env:GITHUB_REPOSITORY/releases/download/$artifactTag" in commands
    assert "packaging\\build_pear_payload.ps1" in commands
    assert "packaging\\build_mediapipe_payload.ps1" in commands
    assert "-Pytorch3dSitePackages .venv-pear\\Lib\\site-packages" in commands
    assert "-PearPayloadManifest $pearPayloadManifest" in commands
    assert "-MediaPipePayloadManifest $mediaPipePayloadManifest" in commands
    assert (
        "gh release create $env:GITHUB_REF_NAME @assets --verify-tag --generate-notes --draft"
        in commands
    )
    assert "gh release view $env:GITHUB_REF_NAME --json assets" in commands
    assert "gh release edit $env:GITHUB_REF_NAME --draft=false" in commands
    assert "packaging/dist/*.json" in workflow_text
    references = {
        str(step["uses"]) for step in release["steps"] if isinstance(step, dict) and "uses" in step
    }
    assert any(reference.startswith("actions/attest@") for reference in references)
    assert all(len(reference.rsplit("@", 1)[-1]) == 40 for reference in references)


def test_release_workflow_manual_qualification_cannot_publish() -> None:
    path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    workflow = _yaml(path)
    workflow_text = path.read_text(encoding="utf-8")
    release = workflow["jobs"]["release"]

    assert "workflow_dispatch:" in workflow_text
    assert "build_number:" in workflow_text
    assert 'GITHUB_EVENT_NAME -eq "workflow_dispatch"' in workflow_text

    release_steps = [
        step
        for step in release["steps"]
        if isinstance(step, dict) and "gh release" in str(step.get("run", ""))
    ]
    assert release_steps
    assert all(step.get("if") == "github.event_name == 'push'" for step in release_steps)

    signed_tag_step = next(
        step for step in release["steps"] if step.get("name") == "Verify signed tag belongs to main"
    )
    assert signed_tag_step["if"] == "github.event_name == 'push'"


def test_release_workflow_isolates_pear_setup_exit_code() -> None:
    workflow = _yaml(REPO_ROOT / ".github" / "workflows" / "release.yml")
    release = workflow["jobs"]["release"]
    prepare = next(
        step for step in release["steps"] if step.get("name") == "Prepare pinned PEAR runtime"
    )

    assert "pwsh -NoProfile -File tools\\install\\setup_pear_runtime.ps1" in prepare["run"]
