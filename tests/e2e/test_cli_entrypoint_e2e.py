import json
import os
import subprocess
import sys
from pathlib import Path


def _run_cli(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["USERPROFILE"] = str(home)
    env["APPDATA"] = str(home / ".config")
    env["LOCALAPPDATA"] = str(home / ".local" / "share")
    return subprocess.run(
        [sys.executable, "-m", "code_agnostic", *args],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_codex_workspace_skill_apply_without_global_mcp_entrypoint(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    workspace_root = tmp_path / "workspace"
    repo = workspace_root / "repo-a"
    (repo / ".git" / "info").mkdir(parents=True)

    enable = _run_cli(home, "apps", "enable", "-a", "codex")
    assert enable.returncode == 0, enable.stderr

    add_workspace = _run_cli(
        home,
        "workspaces",
        "add",
        "--name",
        "myws",
        "--path",
        str(workspace_root),
    )
    assert add_workspace.returncode == 0, add_workspace.stderr

    skill_dir = home / ".config" / "code-agnostic" / "workspaces" / "myws" / "skills"
    (skill_dir / "reviewer").mkdir(parents=True)
    (skill_dir / "reviewer" / "SKILL.md").write_text(
        "---\n"
        "name: reviewer\n"
        "description: Review workspace code\n"
        "---\n"
        "\n"
        "Review carefully.\n",
        encoding="utf-8",
    )

    apply = _run_cli(home, "apply", "-a", "codex")
    assert apply.returncode == 0, apply.stderr + apply.stdout
    assert (workspace_root / ".agents" / "skills" / "reviewer" / "SKILL.md").is_file()
    assert (repo / ".agents" / "skills" / "reviewer" / "SKILL.md").is_file()

    status = _run_cli(home, "status", "-a", "codex")
    assert status.returncode == 0, status.stderr + status.stdout
    assert "synced" in status.stdout
    assert "needs sync" not in status.stdout


def test_entrypoint_plan_and_status_fail_on_invalid_mcp_source(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    enable = _run_cli(home, "apps", "enable", "-a", "codex")
    assert enable.returncode == 0, enable.stderr

    source = home / ".config" / "code-agnostic" / "config" / "mcp.base.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{}", encoding="utf-8")

    plan = _run_cli(home, "plan", "-a", "codex")
    assert plan.returncode != 0
    assert "Invalid config schema" in plan.stdout
    assert "mcp.base.json" in plan.stdout

    status = _run_cli(home, "status", "-a", "codex")
    assert status.returncode != 0
    assert "codex" in status.stdout
    assert "error" in status.stdout
    assert "Invalid config schema" in status.stdout
    assert "synced" not in status.stdout


def test_entrypoint_workspaces_remove_preserves_invalid_registry(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    registry = home / ".config" / "code-agnostic" / "config" / "workspaces.json"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry.parent.mkdir(parents=True)
    registry_text = json.dumps(
        [
            {"name": "demo", "path": str(workspace)},
            {"name": "bad/name", "path": str(tmp_path / "bad")},
        ]
    )
    registry.write_text(registry_text, encoding="utf-8")

    result = _run_cli(home, "workspaces", "remove", "--name", "demo")

    assert result.returncode != 0
    assert "invalid workspace name" in result.stdout + result.stderr
    assert registry.read_text(encoding="utf-8") == registry_text


def test_entrypoint_status_fails_on_invalid_project_registry(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    registry = home / ".config" / "code-agnostic" / "config" / "projects.json"
    registry.parent.mkdir(parents=True)
    registry.write_text("{bad", encoding="utf-8")

    result = _run_cli(home, "status")

    assert result.returncode != 0
    assert "projects" in result.stdout
    assert "error" in result.stdout
    assert "Invalid JSON" in result.stdout
    assert "format" in result.stdout
    assert registry.read_text(encoding="utf-8") == "{bad"


def test_entrypoint_skills_remove_refuses_symlinked_source_dir(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    source_root = home / ".config" / "code-agnostic"
    outside = tmp_path / "outside-skills"
    outside_skill = outside / "keep"
    outside_skill.mkdir(parents=True)
    (outside_skill / "SKILL.md").write_text("external data\n", encoding="utf-8")
    source_root.mkdir(parents=True)
    (source_root / "skills").symlink_to(outside)

    result = _run_cli(home, "skills", "remove", "--name", "keep")

    assert result.returncode != 0
    assert "Refusing to modify symlinked skills source directory" in (
        result.stdout + result.stderr
    )
    assert outside_skill.exists()
    assert (outside_skill / "SKILL.md").read_text(encoding="utf-8") == (
        "external data\n"
    )


def test_entrypoint_skills_install_rejects_invalid_bundle_before_writing(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    source = tmp_path / "bad-skill"
    source.mkdir()
    (source / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: skill\n"
        "name: bad-skill\n"
        "description: Bad skill\n"
        "surprise: nope\n",
        encoding="utf-8",
    )
    (source / "prompt.md").write_text("Bad skill\n", encoding="utf-8")

    result = _run_cli(home, "skills", "install", "--global", str(source))

    assert result.returncode != 0
    assert "Invalid config schema" in result.stderr
    assert "surprise" in result.stderr
    assert not (home / ".config" / "code-agnostic" / "skills" / "bad-skill").exists()


def test_entrypoint_copilot_apply_keeps_outputs_scoped_and_preserves_user_files(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    workspace_root = tmp_path / "workspace"
    repo = workspace_root / "service-api"
    (repo / ".git" / "info").mkdir(parents=True)

    enable = _run_cli(home, "apps", "enable", "-a", "copilot")
    assert enable.returncode == 0, enable.stderr

    add_workspace = _run_cli(
        home,
        "workspaces",
        "add",
        "--name",
        "myws",
        "--path",
        str(workspace_root),
    )
    assert add_workspace.returncode == 0, add_workspace.stderr

    core_root = home / ".config" / "code-agnostic"
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {"mcpServers": {"global": {"command": "uvx", "args": ["global-server"]}}}
        ),
        encoding="utf-8",
    )
    ws_config = core_root / "workspaces" / "myws"
    (ws_config / "mcp.base.json").write_text(
        json.dumps({"mcpServers": {"workspace": {"url": "https://example.test/mcp"}}}),
        encoding="utf-8",
    )
    (ws_config / "skills" / "review").mkdir(parents=True)
    (ws_config / "skills" / "review" / "SKILL.md").write_text(
        "---\nname: review\ndescription: Review code\n---\n\nReview.\n",
        encoding="utf-8",
    )
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.agent.md").write_text(
        "---\nname: planner\ndescription: Plan work\n---\n\nPlan.\n",
        encoding="utf-8",
    )

    user_global_file = home / ".copilot" / "user-settings.json"
    user_global_file.parent.mkdir(parents=True)
    user_global_file.write_text('{"theme": "dark"}\n', encoding="utf-8")
    workspace_user_file = workspace_root / ".github" / "workflows" / "ci.yml"
    workspace_user_file.parent.mkdir(parents=True)
    workspace_user_file.write_text("name: ci\n", encoding="utf-8")
    repo_user_file = repo / ".github" / "dependabot.yml"
    repo_user_file.parent.mkdir(parents=True)
    repo_user_file.write_text("version: 2\n", encoding="utf-8")
    repo_mcp = repo / ".github" / "mcp.json"
    repo_mcp.write_text(
        json.dumps(
            {
                "note": "repo-owned",
                "mcpServers": {
                    "personal": {
                        "tools": ["*"],
                        "type": "local",
                        "command": "uvx",
                        "args": ["personal"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    plan = _run_cli(home, "plan", "-a", "copilot")
    assert plan.returncode == 0, plan.stderr + plan.stdout
    assert "copilot" in plan.stdout

    apply = _run_cli(home, "apply", "-a", "copilot")
    assert apply.returncode == 0, apply.stderr + apply.stdout

    assert (home / ".copilot" / "mcp-config.json").is_file()
    assert not (home / ".mcp.json").exists()
    assert user_global_file.read_text(encoding="utf-8") == '{"theme": "dark"}\n'

    assert (workspace_root / ".github" / "mcp.json").is_file()
    repo_mcp_payload = json.loads(repo_mcp.read_text(encoding="utf-8"))
    assert repo_mcp_payload["note"] == "repo-owned"
    assert repo_mcp_payload["mcpServers"]["personal"]["args"] == ["personal"]
    assert repo_mcp_payload["mcpServers"]["workspace"]["url"] == (
        "https://example.test/mcp"
    )
    assert (repo / ".github" / "skills" / "review" / "SKILL.md").is_file()
    assert (repo / ".github" / "agents" / "planner.agent.md").is_file()
    assert not (workspace_root / ".mcp.json").exists()
    assert not (repo / ".mcp.json").exists()
    assert workspace_user_file.read_text(encoding="utf-8") == "name: ci\n"
    assert repo_user_file.read_text(encoding="utf-8") == "version: 2\n"


def test_entrypoint_apply_fails_on_generated_skill_conflict(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    enable = _run_cli(home, "apps", "enable", "-a", "codex")
    assert enable.returncode == 0, enable.stderr

    source_skill = home / ".config" / "code-agnostic" / "skills" / "reviewer"
    source_skill.mkdir(parents=True)
    (source_skill / "SKILL.md").write_text(
        "---\n" "name: reviewer\n" "---\n" "\n" "Review carefully.\n",
        encoding="utf-8",
    )

    target_skill_file = home / ".agents" / "skills" / "reviewer" / "SKILL.md"
    target_skill_file.mkdir(parents=True)

    apply = _run_cli(home, "apply", "-a", "codex")
    assert apply.returncode != 0
    assert "conflict" in apply.stdout
    assert "failed" in apply.stdout
    assert target_skill_file.is_dir()


def test_entrypoint_import_apply_preflights_before_writing(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    codex_config = home / ".codex" / "config.toml"
    codex_config.parent.mkdir(parents=True)
    codex_config.write_text(
        '[mcp_servers.demo]\ncommand = "uvx"\n',
        encoding="utf-8",
    )

    source_skill = home / ".agents" / "skills" / "reviewer"
    source_skill.mkdir(parents=True)
    (source_skill / "SKILL.md").write_text(
        "---\n" "name: reviewer\n" "---\n" "\n" "Review carefully.\n",
        encoding="utf-8",
    )

    hub_root = home / ".config" / "code-agnostic"
    (hub_root / "config").mkdir(parents=True)
    (hub_root / "skills").write_text("not a directory\n", encoding="utf-8")

    apply = _run_cli(
        home,
        "import",
        "apply",
        "-a",
        "codex",
        "--include",
        "mcp",
        "--include",
        "skills",
    )

    assert apply.returncode != 0
    assert "failed" in apply.stdout
    assert not (hub_root / "config" / "mcp.base.json").exists()
    assert (hub_root / "skills").read_text(encoding="utf-8") == "not a directory\n"


def test_entrypoint_import_apply_preflights_broken_symlink_before_writing(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    codex_config = home / ".codex" / "config.toml"
    codex_config.parent.mkdir(parents=True)
    codex_config.write_text(
        '[mcp_servers.demo]\ncommand = "uvx"\n',
        encoding="utf-8",
    )

    source_skills = home / ".agents" / "skills"
    source_skills.mkdir(parents=True)
    broken_skill = source_skills / "reviewer"
    broken_skill.symlink_to(home / "missing-skill")

    apply = _run_cli(
        home,
        "import",
        "apply",
        "-a",
        "codex",
        "--include",
        "mcp",
        "--include",
        "skills",
        "--follow-symlinks",
    )

    hub_mcp = home / ".config" / "code-agnostic" / "config" / "mcp.base.json"
    assert apply.returncode != 0
    assert "failed" in apply.stdout
    assert "Source path missing" in apply.stdout
    assert broken_skill.name in apply.stdout
    assert not hub_mcp.exists()


def test_entrypoint_status_scopes_app_config_errors(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    enable_codex = _run_cli(home, "apps", "enable", "-a", "codex")
    assert enable_codex.returncode == 0, enable_codex.stderr
    enable_opencode = _run_cli(home, "apps", "enable", "-a", "opencode")
    assert enable_opencode.returncode == 0, enable_opencode.stderr

    opencode_config = home / ".config" / "opencode" / "opencode.json"
    opencode_config.parent.mkdir(parents=True, exist_ok=True)
    opencode_config.write_text("[]", encoding="utf-8")

    status = _run_cli(home, "status", "-a", "codex")
    assert status.returncode == 0, status.stderr + status.stdout
    assert "codex" in status.stdout
    assert "opencode" not in status.stdout
    assert "opencode.json" not in status.stdout
    assert "cannot evaluate" not in status.stdout


def test_entrypoint_status_fails_on_missing_workspace_path(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    add_workspace = _run_cli(
        home,
        "workspaces",
        "add",
        "--name",
        "missingws",
        "--path",
        str(workspace_root),
    )
    assert add_workspace.returncode == 0, add_workspace.stderr

    workspace_root.rmdir()

    status = _run_cli(home, "status")
    assert status.returncode != 0
    assert "missingws" in status.stdout
    assert "error" in status.stdout
    assert "workspace path" in status.stdout


def test_entrypoint_skills_remove_rejects_path_like_name(tmp_path: Path) -> None:
    home = tmp_path / "home"
    source_root = home / ".config" / "code-agnostic"
    (source_root / "skills").mkdir(parents=True)
    victim = source_root / "victim" / "keep.txt"
    victim.parent.mkdir(parents=True)
    victim.write_text("keep\n", encoding="utf-8")

    result = _run_cli(home, "skills", "remove", "--name", "../victim")

    assert result.returncode != 0
    assert "Invalid skill name" in result.stderr
    assert victim.read_text(encoding="utf-8") == "keep\n"


def test_entrypoint_restore_project_repairs_generated_skill(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    project_root = tmp_path / "service-api"
    project_root.mkdir()

    enable = _run_cli(home, "apps", "enable", "-a", "codex")
    assert enable.returncode == 0, enable.stderr

    add_project = _run_cli(
        home,
        "projects",
        "add",
        "--name",
        "service-api",
        "--path",
        str(project_root),
    )
    assert add_project.returncode == 0, add_project.stderr

    skill = (
        home
        / ".config"
        / "code-agnostic"
        / "projects"
        / "service-api"
        / "skills"
        / "project-tool"
        / "SKILL.md"
    )
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\n"
        "name: project-tool\n"
        "description: Project tool\n"
        "---\n"
        "\n"
        "Use project context.\n",
        encoding="utf-8",
    )

    apply = _run_cli(home, "apply", "-a", "codex")
    assert apply.returncode == 0, apply.stderr + apply.stdout

    generated_skill = project_root / ".agents" / "skills" / "project-tool" / "SKILL.md"
    generated_skill.write_text("local damage\n", encoding="utf-8")

    restore = _run_cli(home, "restore", "--project", "service-api")

    assert restore.returncode == 0, restore.stderr + restore.stdout
    assert "Restored revision" in restore.stdout
    assert generated_skill.read_text(encoding="utf-8") == skill.read_text(
        encoding="utf-8"
    )


def test_entrypoint_apply_reports_pending_repair_failure_without_writes(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    enable = _run_cli(home, "apps", "enable", "-a", "opencode")
    assert enable.returncode == 0, enable.stderr

    source_root = home / ".config" / "code-agnostic" / "skills"
    reviewer = source_root / "reviewer"
    reviewer.mkdir(parents=True)
    (reviewer / "SKILL.md").write_text(
        "---\n"
        "name: reviewer\n"
        "description: Review code\n"
        "---\n"
        "\n"
        "Review carefully.\n",
        encoding="utf-8",
    )

    first_apply = _run_cli(home, "apply", "-a", "opencode")
    assert first_apply.returncode == 0, first_apply.stderr + first_apply.stdout

    revisions_root = home / ".config" / "code-agnostic" / ".sync-revisions"
    active_revision = json.loads(
        (revisions_root / "active.json").read_text(encoding="utf-8")
    )
    manifest_path = Path(active_revision["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generated_skill = home / ".config" / "opencode" / "skills" / "reviewer" / "SKILL.md"
    skill_entry = next(
        entry for entry in manifest["targets"] if entry["path"] == str(generated_skill)
    )
    Path(skill_entry["artifact_path"]).unlink()
    pending_path = revisions_root / "pending.json"
    pending_path.write_text('{"revision_id": "pending"}\n', encoding="utf-8")
    generated_skill.write_text("local edits\n", encoding="utf-8")

    triage = source_root / "triage"
    triage.mkdir()
    (triage / "SKILL.md").write_text(
        "---\n"
        "name: triage\n"
        "description: Triage code\n"
        "---\n"
        "\n"
        "Triage carefully.\n",
        encoding="utf-8",
    )

    second_apply = _run_cli(home, "apply", "-a", "opencode")

    assert second_apply.returncode != 0
    assert "pending revision repair failed" in second_apply.stdout
    assert "Missing revision artifact" in second_apply.stdout
    assert "Traceback" not in second_apply.stderr
    assert generated_skill.read_text(encoding="utf-8") == "local edits\n"
    assert not (
        home / ".config" / "opencode" / "skills" / "triage" / "SKILL.md"
    ).exists()
    assert pending_path.exists()
