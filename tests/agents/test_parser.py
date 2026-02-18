"""Tests for agent parser."""

from pathlib import Path

from code_agnostic.agents.models import Agent, AgentMetadata, AgentToolPermissions
from code_agnostic.agents.parser import parse_agent, serialize_agent


def test_parse_full_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "architect.md").write_text(
        "---\n"
        "name: architect\n"
        "description: System architecture specialist\n"
        "model: claude-sonnet-4-20250514\n"
        "tools:\n"
        "  read: true\n"
        "  write: true\n"
        "  mcp:\n"
        "    - server: filesystem\n"
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
    assert agent.metadata.tools.read is True
    assert agent.metadata.tools.write is True
    assert len(agent.metadata.tools.mcp) == 1
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


def test_serialize_roundtrip(tmp_path: Path) -> None:
    agent = Agent(
        name="test-agent",
        source_path=tmp_path / "test-agent.md",
        metadata=AgentMetadata(
            name="test-agent",
            description="A test agent",
            model="claude-opus-4-20250514",
            tools=AgentToolPermissions(read=True, write=True),
        ),
        content="Agent body.\n",
    )
    text = serialize_agent(agent)
    (tmp_path / "test-agent.md").write_text(text, encoding="utf-8")

    parsed = parse_agent(tmp_path / "test-agent.md")
    assert parsed.metadata.name == "test-agent"
    assert parsed.metadata.description == "A test agent"
    assert parsed.metadata.model == "claude-opus-4-20250514"
    assert "Agent body." in parsed.content
