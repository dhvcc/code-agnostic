from pathlib import Path

from code_agnostic.apps.common.compiled_planning import plan_compiled_text_action
from code_agnostic.models import ActionStatus


def test_plan_compiled_text_action_allows_nested_symlink_under_removable_parent(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    skill_dir = source_root / "my-skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("old\n", encoding="utf-8")

    target_root = tmp_path / "target"
    target_root.mkdir()
    removable_parent = target_root / "skills"
    removable_parent.symlink_to(source_root)

    target = removable_parent / "my-skill" / "SKILL.md"
    action = plan_compiled_text_action(
        target=target,
        payload="new\n",
        managed_paths=set(),
        removable_link_paths={removable_parent.resolve(strict=False)},
        scope="app:test:skills",
        app="test",
        create_detail="create compiled skill",
        noop_detail="compiled skill already up to date",
        update_detail="update compiled skill",
    )

    assert action.status == ActionStatus.UPDATE
