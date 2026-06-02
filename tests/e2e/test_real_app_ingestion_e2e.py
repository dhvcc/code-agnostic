import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ENABLE_ENV = "CODE_AGNOSTIC_REAL_APP_E2E"
TARGETS_ENV = "CODE_AGNOSTIC_REAL_APP_TARGETS"
ALL_TARGETS = ("codex", "cursor", "opencode", "claude")
SMOKE_SERVER = """\
import json
import sys


def send(payload):
    sys.stdout.write(json.dumps(payload) + "\\n")
    sys.stdout.flush()


for line in sys.stdin:
    if not line.strip():
        continue
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        send(
            {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "ca-smoke", "version": "1.0.0"},
                },
            }
        )
    elif method == "tools/list":
        send(
            {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "ca_smoke_ping",
                            "description": "Smoke ping",
                            "inputSchema": {"type": "object", "properties": {}},
                        }
                    ]
                },
            }
        )
    elif method == "tools/call":
        send(
            {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"content": [{"type": "text", "text": "pong"}]},
            }
        )
"""

pytestmark = pytest.mark.skipif(
    os.environ.get(ENABLE_ENV) != "1",
    reason=f"set {ENABLE_ENV}=1 to run real app-ingestion E2E",
)


def _selected_targets() -> set[str]:
    raw = os.environ.get(TARGETS_ENV)
    if not raw:
        return set(ALL_TARGETS)
    selected = {item.strip() for item in raw.split(",") if item.strip()}
    unknown = selected - set(ALL_TARGETS)
    if unknown:
        pytest.fail(f"{TARGETS_ENV} contains unsupported target(s): {sorted(unknown)}")
    return selected


def _required_cli(target: str) -> str:
    if target == "codex":
        return "codex"
    if target == "cursor":
        return "cursor-agent"
    if target == "opencode":
        return "opencode"
    if target == "claude":
        return "claude"
    raise AssertionError(f"unexpected target: {target}")


def _isolated_env(home: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "USERPROFILE": str(home),
        "APPDATA": str(home / ".config"),
        "LOCALAPPDATA": str(home / ".local" / "share"),
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "TERM": "xterm-256color",
    }


def _sanitize(text: str, home: Path, tmp_path: Path) -> str:
    return (
        text.replace(str(home), "<HOME>")
        .replace(str(tmp_path), "<TMP>")
        .replace("smoke-value", "<redacted>")
    )


def _write_artifact(path: Path, text: str, home: Path, tmp_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_sanitize(text, home, tmp_path), encoding="utf-8")


def _run(
    label: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    artifact_dir: Path,
    home: Path,
    tmp_path: Path,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _write_artifact(
            artifact_dir / f"{label}.timeout.txt",
            f"command: {shlex.join(command)}\ntimeout: {timeout}\n"
            f"stdout:\n{exc.stdout or ''}\nstderr:\n{exc.stderr or ''}\n",
            home,
            tmp_path,
        )
        pytest.fail(f"{label} timed out after {timeout}s: {shlex.join(command)}")
    _write_artifact(
        artifact_dir / f"{label}.cmd.txt",
        f"command: {shlex.join(command)}\nreturncode: {result.returncode}\n",
        home,
        tmp_path,
    )
    _write_artifact(artifact_dir / f"{label}.stdout.txt", result.stdout, home, tmp_path)
    _write_artifact(artifact_dir / f"{label}.stderr.txt", result.stderr, home, tmp_path)
    return result


def _assert_success(label: str, result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"{label} failed with exit {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _run_code_agnostic(
    label: str,
    args: list[str],
    *,
    env: dict[str, str],
    artifact_dir: Path,
    home: Path,
    tmp_path: Path,
) -> subprocess.CompletedProcess[str]:
    return _run(
        label,
        [sys.executable, "-m", "code_agnostic", *args],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
    )


def _load_json_output(output: str, marker: str) -> object:
    start = output.find(marker)
    if start == -1:
        raise AssertionError(f"no JSON marker {marker!r} found in output:\n{output}")
    return json.loads(output[start:])


def _write_source_fixtures(home: Path, tmp_path: Path) -> tuple[Path, Path]:
    workspace_root = tmp_path / "workspace"
    repo_root = workspace_root / "repo-a"
    (repo_root / ".git" / "info").mkdir(parents=True)

    core_root = home / ".config" / "code-agnostic"
    skill_dir = core_root / "skills" / "ca-smoke"
    skill_dir.mkdir(parents=True)
    (skill_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: skill\n"
        "name: ca-smoke\n"
        "description: Real app smoke skill\n",
        encoding="utf-8",
    )
    (skill_dir / "prompt.md").write_text(
        "Real app smoke skill body.\n",
        encoding="utf-8",
    )

    agent_dir = core_root / "agents" / "ca-smoke-agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: agent\n"
        "name: ca-smoke-agent\n"
        "description: Real app smoke agent\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text(
        "Real app smoke agent body.\n",
        encoding="utf-8",
    )

    server_path = tmp_path / "mcp_smoke_server.py"
    server_path.write_text(SMOKE_SERVER, encoding="utf-8")
    return repo_root, server_path


def _prepare_candidate(
    target: str,
    *,
    env: dict[str, str],
    artifact_dir: Path,
    home: Path,
    tmp_path: Path,
) -> Path:
    repo_root, server_path = _write_source_fixtures(home, tmp_path)
    workspace_root = repo_root.parent

    commands = [
        (
            "enable_app",
            ["apps", "enable", "-a", target],
        ),
        (
            "add_mcp",
            [
                "mcp",
                "add",
                "ca-smoke",
                "--command",
                sys.executable,
                "--args",
                str(server_path),
                "--env",
                "CA_SMOKE_TOKEN=smoke-value",
                "--timeout-ms",
                "3000",
            ],
        ),
        (
            "add_workspace",
            ["workspaces", "add", "--name", "realws", "--path", str(workspace_root)],
        ),
    ]
    for label, args in commands:
        _assert_success(
            label,
            _run_code_agnostic(
                label,
                args,
                env=env,
                artifact_dir=artifact_dir,
                home=home,
                tmp_path=tmp_path,
            ),
        )

    rules_dir = home / ".config" / "code-agnostic" / "workspaces" / "realws" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "smoke.md").write_text(
        "Workspace smoke instructions.\n",
        encoding="utf-8",
    )

    _assert_success(
        "apply",
        _run_code_agnostic(
            "apply",
            ["apply", "-a", target],
            env=env,
            artifact_dir=artifact_dir,
            home=home,
            tmp_path=tmp_path,
        ),
    )
    return repo_root


def _assert_codex_ingestion(
    *,
    env: dict[str, str],
    artifact_dir: Path,
    home: Path,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    mcp_result = _run(
        "codex_mcp_list",
        ["codex", "mcp", "list", "--json"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
    )
    _assert_success("codex mcp list", mcp_result)
    servers = json.loads(mcp_result.stdout)
    smoke = next(server for server in servers if server["name"] == "ca-smoke")
    assert smoke["enabled"] is True
    assert smoke["transport"]["command"] == sys.executable
    assert smoke["transport"]["args"][-1].endswith("mcp_smoke_server.py")
    assert smoke["transport"]["env"]["CA_SMOKE_TOKEN"] == "smoke-value"

    prompt_result = _run(
        "codex_prompt_input",
        ["codex", "-C", str(repo_root), "debug", "prompt-input", "smoke"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
    )
    _assert_success("codex debug prompt-input", prompt_result)
    prompt_payload = json.loads(prompt_result.stdout)
    prompt_text = json.dumps(prompt_payload)
    assert "ca-smoke: Real app smoke skill" in prompt_text
    assert "Workspace smoke instructions." in prompt_text


def _assert_cursor_ingestion(
    *,
    env: dict[str, str],
    artifact_dir: Path,
    home: Path,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    list_result = _run(
        "cursor_mcp_list",
        ["cursor-agent", "mcp", "list"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
        timeout=45,
    )
    _assert_success("cursor-agent mcp list", list_result)
    list_output = list_result.stdout + list_result.stderr
    assert "ca-smoke" in list_output

    tools_result = _run(
        "cursor_mcp_list_tools",
        ["cursor-agent", "mcp", "list-tools", "ca-smoke"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
        timeout=45,
    )
    _assert_success("cursor-agent mcp list-tools", tools_result)
    tools_output = tools_result.stdout + tools_result.stderr
    assert "ca_smoke_ping" in tools_output


def _assert_opencode_ingestion(
    *,
    env: dict[str, str],
    artifact_dir: Path,
    home: Path,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    config_result = _run(
        "opencode_debug_config",
        ["opencode", "debug", "config"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
    )
    _assert_success("opencode debug config", config_result)
    config = _load_json_output(config_result.stdout, "{")
    assert config["mcp"]["ca-smoke"]["command"] == [
        sys.executable,
        str(tmp_path / "mcp_smoke_server.py"),
    ]
    assert config["mcp"]["ca-smoke"]["environment"]["CA_SMOKE_TOKEN"] == "smoke-value"
    assert config["agent"]["ca-smoke-agent"]["prompt"] == "Real app smoke agent body."
    assert any("AGENTS.md" in instruction for instruction in config["instructions"])

    skill_result = _run(
        "opencode_debug_skill",
        ["opencode", "debug", "skill"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
    )
    _assert_success("opencode debug skill", skill_result)
    skills = _load_json_output(skill_result.stdout, "[")
    smoke_skill = next(skill for skill in skills if skill["name"] == "ca-smoke")
    assert smoke_skill["description"] == "Real app smoke skill"
    assert "Real app smoke skill body." in smoke_skill["content"]

    mcp_result = _run(
        "opencode_mcp_list",
        ["opencode", "mcp", "list"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
    )
    _assert_success("opencode mcp list", mcp_result)
    output = mcp_result.stdout + mcp_result.stderr
    assert "ca-smoke" in output
    assert "connected" in output


def _assert_claude_ingestion(
    *,
    env: dict[str, str],
    artifact_dir: Path,
    home: Path,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    list_result = _run(
        "claude_mcp_list",
        ["claude", "mcp", "list"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
        timeout=45,
    )
    _assert_success("claude mcp list", list_result)
    list_output = list_result.stdout + list_result.stderr
    assert "ca-smoke" in list_output

    get_result = _run(
        "claude_mcp_get",
        ["claude", "mcp", "get", "ca-smoke"],
        cwd=repo_root,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
        timeout=45,
    )
    _assert_success("claude mcp get", get_result)
    get_output = get_result.stdout + get_result.stderr
    assert "ca-smoke" in get_output
    assert "mcp_smoke_server.py" in get_output

    assert (repo_root / "CLAUDE.local.md").read_text(encoding="utf-8") == (
        "Workspace smoke instructions.\n"
    )
    assert (repo_root / ".claude" / "skills" / "ca-smoke" / "SKILL.md").is_file()
    assert (repo_root / ".claude" / "agents" / "ca-smoke-agent.md").is_file()


@pytest.mark.parametrize("target", ALL_TARGETS)
def test_real_app_ingestion_uses_tool_introspection(
    target: str, tmp_path: Path
) -> None:
    selected = _selected_targets()
    if target not in selected:
        pytest.skip(f"{target} not selected by {TARGETS_ENV}")

    cli = _required_cli(target)
    if shutil.which(cli) is None:
        pytest.fail(f"{cli} is required for {target} real app-ingestion E2E")

    home = tmp_path / "home"
    home.mkdir()
    env = _isolated_env(home)
    artifact_dir = tmp_path / "artifacts" / target
    repo_root = _prepare_candidate(
        target,
        env=env,
        artifact_dir=artifact_dir,
        home=home,
        tmp_path=tmp_path,
    )

    if target == "codex":
        _assert_codex_ingestion(
            env=env,
            artifact_dir=artifact_dir,
            home=home,
            repo_root=repo_root,
            tmp_path=tmp_path,
        )
    elif target == "cursor":
        _assert_cursor_ingestion(
            env=env,
            artifact_dir=artifact_dir,
            home=home,
            repo_root=repo_root,
            tmp_path=tmp_path,
        )
    elif target == "opencode":
        _assert_opencode_ingestion(
            env=env,
            artifact_dir=artifact_dir,
            home=home,
            repo_root=repo_root,
            tmp_path=tmp_path,
        )
    elif target == "claude":
        _assert_claude_ingestion(
            env=env,
            artifact_dir=artifact_dir,
            home=home,
            repo_root=repo_root,
            tmp_path=tmp_path,
        )
    else:
        raise AssertionError(f"unexpected target: {target}")
