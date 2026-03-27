import functools
import json
from pathlib import Path
from urllib.request import Request, urlopen

from jsonschema import Draft7Validator

from code_agnostic.__main__ import cli

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@functools.lru_cache(maxsize=1)
def _load_codex_schema() -> dict:
    request = Request(
        "https://github.com/openai/codex/raw/refs/heads/main/codex-rs/core/config.schema.json",
        headers={"User-Agent": "Mozilla/5.0 code-agnostic-tests"},
    )
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _load_local_codex_schema() -> dict:
    schema_path = (
        Path(__file__).resolve().parent.parent
        / "code_agnostic"
        / "apps"
        / "codex"
        / "schema.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_local_codex_schema_matches_upstream_mcp_shape() -> None:
    upstream = _load_codex_schema()
    local = _load_local_codex_schema()

    upstream_raw = upstream["definitions"]["RawMcpServerConfig"]
    local_raw = local["definitions"]["RawMcpServerConfig"]

    assert (
        upstream["properties"]["mcp_servers"]["type"]
        == local["properties"]["mcp_servers"]["type"]
    )
    assert upstream_raw["additionalProperties"] is False
    assert local_raw["additionalProperties"] is False
    assert set(upstream_raw["properties"].keys()) == set(local_raw["properties"].keys())


def test_apply_codex_generates_schema_valid_config(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "local": {
                        "command": "uvx",
                        "args": ["tool"],
                        "timeout": 900000,
                        "env": {"TOKEN": "${TOKEN}"},
                    },
                    "remote": {
                        "url": "https://example.com/mcp",
                        "headers": {
                            "Authorization": "Bearer ${API_TOKEN}",
                            "X-Api-Version": "1",
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    codex_payload = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    validator = Draft7Validator(_load_local_codex_schema())
    assert list(validator.iter_errors(codex_payload)) == []
    assert codex_payload["mcp_servers"]["local"]["tool_timeout_sec"] == 900.0


def test_apply_codex_renders_agents_and_global_agents_config(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    (core_root / "config" / "codex.base.json").parent.mkdir(parents=True, exist_ok=True)
    (core_root / "config" / "codex.base.json").write_text(
        json.dumps({"agents": {"max_threads": 6, "max_depth": 1}}),
        encoding="utf-8",
    )
    (tmp_path / ".codex").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".codex" / "config.toml").write_text(
        "[agents.1]\n" 'description = "1"\n' 'config_file = "agents/1.toml"\n',
        encoding="utf-8",
    )
    (core_root / "agents").mkdir(parents=True, exist_ok=True)
    (core_root / "agents" / "planner.md").write_text(
        "---\n"
        "description: Planning specialist\n"
        "model: gpt-5.4\n"
        "model_reasoning_effort: high\n"
        "sandbox_mode: read-only\n"
        "nickname_candidates:\n"
        "  - Atlas\n"
        "codex:\n"
        "  mcp_servers:\n"
        "    openaiDeveloperDocs:\n"
        "      url: https://developers.openai.com/mcp\n"
        "  skills:\n"
        "    config:\n"
        "      - path: /tmp/docs/SKILL.md\n"
        "        enabled: false\n"
        "---\n"
        "\n"
        "Plan carefully.\n",
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    config_payload = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert config_payload["agents"]["max_threads"] == 6
    assert config_payload["agents"]["max_depth"] == 1
    assert config_payload["agents"]["1"] == {
        "description": "1",
        "config_file": "agents/1.toml",
    }
    assert config_payload["agents"]["planner"] == {
        "description": "Planning specialist",
        "nickname_candidates": ["Atlas"],
        "config_file": "agents/planner.toml",
    }

    agent_payload = tomllib.loads(
        (tmp_path / ".codex" / "agents" / "planner.toml").read_text(encoding="utf-8")
    )
    assert agent_payload["name"] == "planner"
    assert agent_payload["description"] == "Planning specialist"
    assert agent_payload["developer_instructions"] == "Plan carefully.\n"
    assert agent_payload["model"] == "gpt-5.4"
    assert agent_payload["mcp_servers"]["openaiDeveloperDocs"]["url"] == (
        "https://developers.openai.com/mcp"
    )
    assert agent_payload["skills"]["config"] == [
        {"path": "/tmp/docs/SKILL.md", "enabled": False}
    ]


def test_apply_codex_uses_local_schema_fallback_on_remote_failure(
    minimal_shared_config: Path,
    cli_runner,
    enable_app,
    monkeypatch,
) -> None:
    enable_app("codex")

    def _fail(*args, **kwargs):
        raise OSError("network unavailable")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
