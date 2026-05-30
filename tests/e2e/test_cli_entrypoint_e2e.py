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
