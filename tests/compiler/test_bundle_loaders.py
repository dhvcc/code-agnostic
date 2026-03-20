from pathlib import Path

import pytest

from code_agnostic.apps.common.models import MCPServerType
from code_agnostic.errors import InvalidConfigSchemaError, MissingConfigFileError
from code_agnostic.spec.loaders import (
    load_agent_bundle,
    load_mcp_base,
    load_rule_bundle,
    load_skill_bundle,
)


def test_load_rule_bundle(tmp_path: Path) -> None:
    rule_dir = tmp_path / "rules" / "python-style"
    rule_dir.mkdir(parents=True)
    (rule_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: rule\n"
        "description: Python style\n"
        "globs:\n"
        '  - "*.py"\n'
        "always_apply: true\n",
        encoding="utf-8",
    )
    (rule_dir / "prompt.md").write_text("Always use type hints.\n", encoding="utf-8")

    rule = load_rule_bundle(rule_dir)

    assert rule.name == "python-style"
    assert rule.metadata.description == "Python style"
    assert rule.metadata.globs == ["*.py"]
    assert rule.metadata.always_apply is True
    assert rule.content == "Always use type hints.\n"


def test_load_skill_bundle(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "code-reviewer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: skill\n"
        "name: code-reviewer\n"
        "description: Reviews code\n"
        "tools:\n"
        "  read: true\n"
        "  write: false\n"
        "  mcp:\n"
        "    - server: github\n"
        "      tool: create_pull_request_review\n",
        encoding="utf-8",
    )
    (skill_dir / "prompt.md").write_text("Review the diff.\n", encoding="utf-8")

    skill = load_skill_bundle(skill_dir)

    assert skill.name == "code-reviewer"
    assert skill.metadata.name == "code-reviewer"
    assert skill.metadata.description == "Reviews code"
    assert skill.metadata.tools.read is True
    assert skill.metadata.tools.write is False
    assert skill.metadata.tools.mcp == [
        {"server": "github", "tool": "create_pull_request_review"}
    ]
    assert skill.content == "Review the diff.\n"


def test_load_agent_bundle(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agents" / "architect"
    agent_dir.mkdir(parents=True)
    (agent_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: agent\n"
        "name: architect\n"
        "description: Architecture specialist\n"
        "model: gpt-5.4\n"
        "reasoning_effort: high\n"
        "sandbox_mode: workspace-write\n"
        "nickname_candidates:\n"
        "  - Atlas\n"
        "tools:\n"
        "  read: true\n"
        "  write: true\n"
        "codex:\n"
        "  mcp_servers:\n"
        "    openaiDeveloperDocs:\n"
        "      url: https://developers.openai.com/mcp\n"
        "  skills:\n"
        "    config:\n"
        "      - path: /tmp/docs/SKILL.md\n"
        "        enabled: false\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("Design the system.\n", encoding="utf-8")

    agent = load_agent_bundle(agent_dir)

    assert agent.name == "architect"
    assert agent.metadata.model == "gpt-5.4"
    assert agent.metadata.model_reasoning_effort == "high"
    assert agent.metadata.sandbox_mode == "workspace-write"
    assert agent.metadata.nickname_candidates == ["Atlas"]
    assert agent.metadata.codex.mcp_servers == {
        "openaiDeveloperDocs": {"url": "https://developers.openai.com/mcp"}
    }
    assert agent.metadata.codex.skills_config[0].path == "/tmp/docs/SKILL.md"
    assert agent.metadata.codex.skills_config[0].enabled is False
    assert agent.content == "Design the system.\n"


def test_load_agent_bundle_with_app_overrides(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agents" / "architect"
    agent_dir.mkdir(parents=True)
    (agent_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: agent\n"
        "name: architect\n"
        "model: gpt-5.4-mini\n"
        "x-opencode:\n"
        "  model: opencode/big-pickle\n"
        "  temperature: 0.2\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("Design the system.\n", encoding="utf-8")

    agent = load_agent_bundle(agent_dir)

    assert agent.metadata.model == "gpt-5.4-mini"
    assert agent.metadata.app_overrides == {
        "opencode": {"model": "opencode/big-pickle", "temperature": 0.2}
    }


@pytest.mark.parametrize(
    ("relative_path", "meta_text", "loader"),
    [
        (
            "rules/example/meta.yaml",
            "$schema: https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/rule.v1.schema.json\n"
            "spec_version: v1\n"
            "kind: rule\n"
            "description: Example rule\n",
            load_rule_bundle,
        ),
        (
            "skills/example/meta.yaml",
            "$schema: https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/skill.v1.schema.json\n"
            "spec_version: v1\n"
            "kind: skill\n"
            "name: example\n",
            load_skill_bundle,
        ),
        (
            "agents/example/meta.yaml",
            "$schema: https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/agent.v1.schema.json\n"
            "spec_version: v1\n"
            "kind: agent\n"
            "name: example\n",
            load_agent_bundle,
        ),
    ],
)
def test_bundle_loader_accepts_schema_property(
    tmp_path: Path, relative_path: str, meta_text: str, loader
) -> None:
    bundle_dir = tmp_path / Path(relative_path).parent
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "meta.yaml").write_text(meta_text, encoding="utf-8")
    (bundle_dir / "prompt.md").write_text("Content.\n", encoding="utf-8")

    resource = loader(bundle_dir)

    assert resource.content == "Content.\n"


def test_load_mcp_base(tmp_path: Path) -> None:
    path = tmp_path / "config" / "mcp.base.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "spec_version: v1\n"
        "mcp_servers:\n"
        "  github:\n"
        "    type: stdio\n"
        "    command: npx\n"
        "    args:\n"
        "      - -y\n"
        "      - '@modelcontextprotocol/server-github'\n"
        "    timeout: 900000\n"
        "    env:\n"
        "      GITHUB_TOKEN: ${GITHUB_TOKEN}\n",
        encoding="utf-8",
    )

    servers = load_mcp_base(path)

    github = servers["github"]
    assert github.type == MCPServerType.STDIO
    assert github.command == "npx"
    assert github.args == ["-y", "@modelcontextprotocol/server-github"]
    assert github.timeout_ms == 900000
    assert github.env == {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}


def test_load_mcp_base_accepts_schema_property(tmp_path: Path) -> None:
    path = tmp_path / "config" / "mcp.base.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "$schema: https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/mcp.v1.schema.json\n"
        "spec_version: v1\n"
        "mcp_servers:\n"
        "  github:\n"
        "    type: stdio\n"
        "    command: npx\n",
        encoding="utf-8",
    )

    servers = load_mcp_base(path)

    assert servers["github"].command == "npx"


@pytest.mark.parametrize("loader_name", ["rule", "skill", "agent"])
def test_bundle_loader_requires_prompt_markdown(
    tmp_path: Path, loader_name: str
) -> None:
    bundle_dir = tmp_path / f"{loader_name}s" / "example"
    bundle_dir.mkdir(parents=True)

    if loader_name == "rule":
        (bundle_dir / "meta.yaml").write_text(
            "spec_version: v1\nkind: rule\ndescription: Example\n", encoding="utf-8"
        )
        loader = load_rule_bundle
    elif loader_name == "skill":
        (bundle_dir / "meta.yaml").write_text(
            "spec_version: v1\nkind: skill\nname: example\n", encoding="utf-8"
        )
        loader = load_skill_bundle
    else:
        (bundle_dir / "meta.yaml").write_text(
            "spec_version: v1\nkind: agent\nname: example\n", encoding="utf-8"
        )
        loader = load_agent_bundle

    with pytest.raises(MissingConfigFileError):
        loader(bundle_dir)


@pytest.mark.parametrize(
    ("loader", "meta_text"),
    [
        (
            load_rule_bundle,
            "spec_version: v1\nkind: rule\ndescription: Example\nunsupported: true\n",
        ),
        (
            load_skill_bundle,
            "spec_version: v1\nkind: skill\nname: example\nunsupported: true\n",
        ),
        (
            load_agent_bundle,
            "spec_version: v1\nkind: agent\nname: example\nunsupported: true\n",
        ),
    ],
)
def test_bundle_loader_rejects_unknown_keys(
    tmp_path: Path, loader, meta_text: str
) -> None:
    bundle_dir = tmp_path / "resource"
    bundle_dir.mkdir()
    (bundle_dir / "meta.yaml").write_text(meta_text, encoding="utf-8")
    (bundle_dir / "prompt.md").write_text("Content.\n", encoding="utf-8")

    with pytest.raises(InvalidConfigSchemaError):
        loader(bundle_dir)


def test_load_mcp_base_rejects_invalid_server_shape(tmp_path: Path) -> None:
    path = tmp_path / "config" / "mcp.base.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "spec_version: v1\nmcp_servers:\n  github:\n    type: stdio\n",
        encoding="utf-8",
    )

    with pytest.raises(InvalidConfigSchemaError):
        load_mcp_base(path)
