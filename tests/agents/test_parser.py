"""Tests for agent parser."""

from pathlib import Path

from code_agnostic.agents.models import (
    Agent,
    AgentCodexConfig,
    AgentMetadata,
    AgentSkillConfig,
    AgentToolPermissions,
)
from code_agnostic.agents.parser import parse_agent, serialize_agent


def test_parse_full_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "architect.md").write_text(
        "---\n"
        "name: architect\n"
        "description: System architecture specialist\n"
        "model: claude-sonnet-4-20250514\n"
        "model_reasoning_effort: high\n"
        "sandbox_mode: read-only\n"
        "nickname_candidates:\n"
        "  - Atlas\n"
        "  - Echo\n"
        "tools:\n"
        "  read: true\n"
        "  write: true\n"
        "  mcp:\n"
        "    - server: filesystem\n"
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
        "# Architect Agent\n\n"
        "You are a system architect.\n",
        encoding="utf-8",
    )
    agent = parse_agent(tmp_path / "architect.md")
    assert agent.name == "architect"
    assert agent.metadata.description == "System architecture specialist"
    assert agent.metadata.model == "claude-sonnet-4-20250514"
    assert agent.metadata.model_reasoning_effort == "high"
    assert agent.metadata.sandbox_mode == "read-only"
    assert agent.metadata.nickname_candidates == ["Atlas", "Echo"]
    assert agent.metadata.tools.read is True
    assert agent.metadata.tools.write is True
    assert len(agent.metadata.tools.mcp) == 1
    assert agent.metadata.codex.mcp_servers["openaiDeveloperDocs"]["url"] == (
        "https://developers.openai.com/mcp"
    )
    assert agent.metadata.codex.skills_config == [
        AgentSkillConfig(path="/tmp/docs/SKILL.md", enabled=False)
    ]
    assert "# Architect Agent" in agent.content


def test_parse_no_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "simple.md").write_text(
        "# Simple Agent\n\nJust content.\n",
        encoding="utf-8",
    )
    agent = parse_agent(tmp_path / "simple.md")
    assert agent.name == "simple"
    assert agent.metadata.description == ""
    assert agent.metadata.model == ""
    assert "# Simple Agent" in agent.content


def test_parse_opencode_reasoning_effort_alias(tmp_path: Path) -> None:
    (tmp_path / "reviewer.md").write_text(
        "---\n"
        "name: reviewer\n"
        "model: openai/gpt-5\n"
        "reasoningEffort: high\n"
        "---\n"
        "\n"
        "Review carefully.\n",
        encoding="utf-8",
    )

    agent = parse_agent(tmp_path / "reviewer.md")
    assert agent.metadata.model == "openai/gpt-5"
    assert agent.metadata.model_reasoning_effort == "high"


def test_parse_app_prefixed_agent_overrides(tmp_path: Path) -> None:
    (tmp_path / "reviewer.md").write_text(
        "---\n"
        "name: reviewer\n"
        "model: gpt-5.4-mini\n"
        "opencode-model: opencode/big-pickle\n"
        "opencode-temperature: 0.2\n"
        "---\n"
        "\n"
        "Review carefully.\n",
        encoding="utf-8",
    )

    agent = parse_agent(tmp_path / "reviewer.md")

    assert agent.metadata.model == "gpt-5.4-mini"
    assert agent.metadata.app_overrides == {
        "opencode": {"model": "opencode/big-pickle", "temperature": 0.2}
    }


def test_serialize_roundtrip(tmp_path: Path) -> None:
    agent = Agent(
        name="test-agent",
        source_path=tmp_path / "test-agent.md",
        metadata=AgentMetadata(
            name="test-agent",
            description="A test agent",
            model="claude-opus-4-20250514",
            model_reasoning_effort="medium",
            sandbox_mode="workspace-write",
            nickname_candidates=["Atlas", "Delta"],
            tools=AgentToolPermissions(read=True, write=True),
            app_overrides={
                "opencode": {"model": "opencode/big-pickle", "temperature": 0.2}
            },
            codex=AgentCodexConfig(
                mcp_servers={
                    "openaiDeveloperDocs": {"url": "https://developers.openai.com/mcp"}
                },
                skills_config=[
                    AgentSkillConfig(path="/tmp/docs/SKILL.md", enabled=False)
                ],
            ),
        ),
        content="Agent body.\n",
    )
    text = serialize_agent(agent)
    (tmp_path / "test-agent.md").write_text(text, encoding="utf-8")

    parsed = parse_agent(tmp_path / "test-agent.md")
    assert parsed.metadata.name == "test-agent"
    assert parsed.metadata.description == "A test agent"
    assert parsed.metadata.model == "claude-opus-4-20250514"
    assert parsed.metadata.model_reasoning_effort == "medium"
    assert parsed.metadata.sandbox_mode == "workspace-write"
    assert parsed.metadata.nickname_candidates == ["Atlas", "Delta"]
    assert parsed.metadata.app_overrides == {
        "opencode": {"model": "opencode/big-pickle", "temperature": 0.2}
    }
    assert parsed.metadata.codex.mcp_servers["openaiDeveloperDocs"]["url"] == (
        "https://developers.openai.com/mcp"
    )
    assert parsed.metadata.codex.skills_config == [
        AgentSkillConfig(path="/tmp/docs/SKILL.md", enabled=False)
    ]
    assert "Agent body." in parsed.content
