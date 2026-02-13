from pathlib import Path

from code_agnostic.core.repository import CoreRepository
from code_agnostic.imports.models import ConflictPolicy, ImportSection
from code_agnostic.imports.service import ImportService


def test_skills_import_copies_skill_directories(tmp_path: Path) -> None:
    source = tmp_path / ".codex"
    skill_dir = source / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("skill", encoding="utf-8")
    (source / "config.toml").write_text("", encoding="utf-8")

    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan("codex", include=[ImportSection.SKILLS])
    result = service.apply(plan)

    assert result.failed == 0
    assert (core.skills_dir / "demo" / "SKILL.md").exists()


def test_agents_import_copies_supported_app_assets(tmp_path: Path) -> None:
    source = tmp_path / ".cursor"
    source.mkdir(parents=True, exist_ok=True)
    (source / "mcp.json").write_text("{}", encoding="utf-8")
    agent_file = source / "agents" / "planner.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("agent", encoding="utf-8")

    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan("cursor", include=[ImportSection.AGENTS])
    result = service.apply(plan)

    assert result.failed == 0
    assert (core.agents_dir / "planner.md").exists()


def test_assets_import_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / ".codex"
    skill_dir = source / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("skill", encoding="utf-8")
    (source / "config.toml").write_text("", encoding="utf-8")

    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    service.apply(service.plan("codex", include=[ImportSection.SKILLS]))
    second_plan = service.plan("codex", include=[ImportSection.SKILLS])

    assert all(action.status.value == "noop" for action in second_plan.actions)


def test_assets_import_skips_symlink_entries_by_default(tmp_path: Path) -> None:
    source = tmp_path / ".codex"
    source.mkdir(parents=True)
    (source / "config.toml").write_text("", encoding="utf-8")
    real_skill = tmp_path / "shared-skill"
    real_skill.mkdir()
    (real_skill / "SKILL.md").write_text("skill", encoding="utf-8")

    skills_root = source / "skills"
    skills_root.mkdir()
    (skills_root / "linked-skill").symlink_to(real_skill)

    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan("codex", include=[ImportSection.SKILLS])
    service.apply(plan)

    assert not (core.skills_dir / "linked-skill").exists()
    assert any("symlink" in item.lower() for item in plan.skipped)


def test_assets_import_overwrite_replaces_target_content(tmp_path: Path) -> None:
    source = tmp_path / ".codex"
    source.mkdir(parents=True)
    (source / "config.toml").write_text("", encoding="utf-8")
    skill_dir = source / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("new", encoding="utf-8")

    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    target_skill = core.skills_dir / "demo"
    target_skill.mkdir(parents=True)
    (target_skill / "SKILL.md").write_text("old", encoding="utf-8")

    service = ImportService(core)
    plan = service.plan(
        "codex",
        include=[ImportSection.SKILLS],
        conflict_policy=ConflictPolicy.OVERWRITE,
    )
    service.apply(plan)

    assert (target_skill / "SKILL.md").read_text(encoding="utf-8") == "new"
