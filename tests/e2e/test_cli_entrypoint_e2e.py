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
