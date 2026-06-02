import json
from pathlib import Path

from code_agnostic.core.repository import CoreRepository
from code_agnostic.imports.models import ImportSection
from code_agnostic.imports.service import ImportService


def test_import_claude_mcp_from_home_config(tmp_path: Path) -> None:
    config_path = tmp_path / ".claude.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "demo": {
                        "type": "stdio",
                        "command": "uvx",
                        "args": ["demo"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    plan = ImportService(core).plan(
        "claude",
        include=[ImportSection.MCP],
        source_root=tmp_path / ".claude",
    )

    assert plan.errors == []
    result = ImportService(core).apply(plan)

    assert result.failed == 0
    payload = json.loads(core.mcp_base_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["demo"] == {
        "command": "uvx",
        "args": ["demo"],
    }


def test_import_claude_skills_and_agents(tmp_path: Path) -> None:
    skill_dir = tmp_path / ".claude" / "skills" / "review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("review skill\n", encoding="utf-8")
    agent_dir = tmp_path / ".claude" / "agents"
    agent_dir.mkdir(parents=True)
    (agent_dir / "planner.md").write_text("plan things\n", encoding="utf-8")

    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)
    plan = service.plan(
        "claude",
        include=[ImportSection.SKILLS, ImportSection.AGENTS],
        source_root=tmp_path / ".claude",
    )

    assert plan.errors == []
    result = service.apply(plan)

    assert result.failed == 0
    assert (core.skills_dir / "review" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "review skill\n"
    assert (core.agents_dir / "planner.md").read_text(encoding="utf-8") == (
        "plan things\n"
    )
