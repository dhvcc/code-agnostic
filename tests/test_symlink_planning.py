from pathlib import Path

from code_agnostic.apps.common.symlink_planning import plan_stale_group, plan_symlink
from code_agnostic.models import ActionKind, ActionStatus


# --- plan_symlink ---


def test_plan_symlink_target_does_not_exist(tmp_path: Path) -> None:
    source = tmp_path / "source_file"
    source.write_text("content", encoding="utf-8")
    target = tmp_path / "link"

    action = plan_symlink(target, source, scope="test")

    assert action.status == ActionStatus.CREATE
    assert action.kind == ActionKind.SYMLINK
    assert action.source == source
    assert action.path == target


def test_plan_symlink_target_is_correct_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source_file"
    source.write_text("content", encoding="utf-8")
    target = tmp_path / "link"
    target.symlink_to(source)

    action = plan_symlink(target, source, scope="test")

    assert action.status == ActionStatus.NOOP
    assert action.detail == "already linked"


def test_plan_symlink_target_points_elsewhere(tmp_path: Path) -> None:
    source = tmp_path / "source_file"
    source.write_text("content", encoding="utf-8")
    other = tmp_path / "other_file"
    other.write_text("other", encoding="utf-8")
    target = tmp_path / "link"
    target.symlink_to(other)

    action = plan_symlink(target, source, scope="test")

    assert action.status == ActionStatus.FIX
    assert action.detail == "symlink points elsewhere"


def test_plan_symlink_target_is_regular_file(tmp_path: Path) -> None:
    source = tmp_path / "source_file"
    source.write_text("content", encoding="utf-8")
    target = tmp_path / "link"
    target.write_text("i am a regular file", encoding="utf-8")

    action = plan_symlink(target, source, scope="test")

    assert action.status == ActionStatus.CONFLICT
    assert action.detail == "non-symlink path exists"


def test_plan_symlink_broken_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source_file"
    source.write_text("content", encoding="utf-8")
    deleted = tmp_path / "deleted_file"
    target = tmp_path / "link"
    target.symlink_to(deleted)
    assert not target.exists()
    assert target.is_symlink()

    action = plan_symlink(target, source, scope="test")

    assert action.status == ActionStatus.FIX


def test_plan_symlink_passes_app_and_scope(tmp_path: Path) -> None:
    source = tmp_path / "source_file"
    source.write_text("content", encoding="utf-8")
    target = tmp_path / "link"

    action = plan_symlink(target, source, scope="skills", app="opencode")

    assert action.app == "opencode"
    assert action.scope == "skills"


# --- plan_stale_group ---


def test_plan_stale_group_old_link_still_desired(tmp_path: Path) -> None:
    link = tmp_path / "still_wanted"
    link.symlink_to(tmp_path)

    actions = plan_stale_group(
        old_links=[link],
        desired_links=[link],
        remove_detail="removed",
        conflict_detail="conflict",
        noop_detail="noop",
        app="opencode",
        scope="test",
        skipped=[],
        skipped_message="skipped {path}",
    )

    assert actions == []


def test_plan_stale_group_old_symlink_not_desired(tmp_path: Path) -> None:
    target_file = tmp_path / "target"
    target_file.write_text("x", encoding="utf-8")
    link = tmp_path / "old_link"
    link.symlink_to(target_file)
    skipped: list[str] = []

    actions = plan_stale_group(
        old_links=[link],
        desired_links=[],
        remove_detail="stale symlink removed",
        conflict_detail="conflict",
        noop_detail="noop",
        app="opencode",
        scope="test",
        skipped=skipped,
        skipped_message="skipped {path}",
    )

    assert len(actions) == 1
    assert actions[0].status == ActionStatus.REMOVE
    assert actions[0].kind == ActionKind.REMOVE_SYMLINK
    assert skipped == []


def test_plan_stale_group_old_regular_file_not_desired(tmp_path: Path) -> None:
    regular = tmp_path / "regular_file"
    regular.write_text("content", encoding="utf-8")
    skipped: list[str] = []

    actions = plan_stale_group(
        old_links=[regular],
        desired_links=[],
        remove_detail="removed",
        conflict_detail="not a symlink",
        noop_detail="noop",
        app="opencode",
        scope="test",
        skipped=skipped,
        skipped_message="skipped {path}",
    )

    assert len(actions) == 1
    assert actions[0].status == ActionStatus.CONFLICT
    assert len(skipped) == 1
    assert str(regular) in skipped[0]


def test_plan_stale_group_old_link_does_not_exist(tmp_path: Path) -> None:
    missing = tmp_path / "gone"
    skipped: list[str] = []

    actions = plan_stale_group(
        old_links=[missing],
        desired_links=[],
        remove_detail="removed",
        conflict_detail="conflict",
        noop_detail="already gone",
        app="opencode",
        scope="test",
        skipped=skipped,
        skipped_message="skipped {path}",
    )

    assert len(actions) == 1
    assert actions[0].status == ActionStatus.NOOP
    assert skipped == []


def test_plan_stale_group_empty_old_links() -> None:
    actions = plan_stale_group(
        old_links=[],
        desired_links=[],
        remove_detail="removed",
        conflict_detail="conflict",
        noop_detail="noop",
        app="opencode",
        scope="test",
        skipped=[],
        skipped_message="skipped {path}",
    )

    assert actions == []


def test_plan_stale_group_empty_desired_all_become_actions(tmp_path: Path) -> None:
    target_file = tmp_path / "target"
    target_file.write_text("x", encoding="utf-8")
    link1 = tmp_path / "link1"
    link1.symlink_to(target_file)
    link2 = tmp_path / "link2"
    link2.symlink_to(target_file)

    actions = plan_stale_group(
        old_links=[link1, link2],
        desired_links=[],
        remove_detail="removed",
        conflict_detail="conflict",
        noop_detail="noop",
        app="opencode",
        scope="test",
        skipped=[],
        skipped_message="skipped {path}",
    )

    assert len(actions) == 2
    assert all(a.status == ActionStatus.REMOVE for a in actions)
