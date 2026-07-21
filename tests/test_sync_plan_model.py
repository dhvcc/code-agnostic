from pathlib import Path

from code_agnostic.models import (
    Action,
    ActionKind,
    ActionStatus,
    SyncPlan,
    SyncState,
)


def _action(
    status: ActionStatus = ActionStatus.CREATE,
    app: str | None = None,
    scope: str | None = None,
    path: str = "/tmp/test",
) -> Action:
    return Action(
        kind=ActionKind.WRITE_JSON,
        path=Path(path),
        status=status,
        detail="test",
        app=app,
        scope=scope,
    )


# --- filter_for_target ---


def test_filter_for_target_all_returns_self() -> None:
    plan = SyncPlan(
        actions=[_action(app="cursor"), _action(app="opencode")],
        errors=[],
        skipped=[],
    )

    result = plan.filter_for_target("all")

    assert result is plan


def test_filter_for_target_cursor_keeps_cursor_and_workspace() -> None:
    plan = SyncPlan(
        actions=[
            _action(app="cursor"),
            _action(app="opencode"),
            _action(app="codex"),
            _action(app="workspace"),
        ],
        errors=[],
        skipped=[],
    )

    result = plan.filter_for_target("cursor")

    apps = [a.app for a in result.actions]
    assert "cursor" in apps
    assert "workspace" in apps
    assert "opencode" not in apps
    assert "codex" not in apps


def test_filter_for_target_codex_keeps_codex_and_workspace() -> None:
    plan = SyncPlan(
        actions=[
            _action(app="cursor"),
            _action(app="opencode"),
            _action(app="codex"),
            _action(app="workspace"),
        ],
        errors=[],
        skipped=[],
    )

    result = plan.filter_for_target("codex")

    apps = [a.app for a in result.actions]
    assert "codex" in apps
    assert "workspace" in apps
    assert "cursor" not in apps
    assert "opencode" not in apps


def test_filter_for_target_claude_keeps_claude_and_workspace() -> None:
    plan = SyncPlan(
        actions=[
            _action(app="cursor"),
            _action(app="opencode"),
            _action(app="codex"),
            _action(app="claude"),
            _action(app="workspace"),
        ],
        errors=[],
        skipped=[],
    )

    result = plan.filter_for_target("claude")

    apps = [a.app for a in result.actions]
    assert "claude" in apps
    assert "workspace" in apps
    assert "cursor" not in apps
    assert "opencode" not in apps
    assert "codex" not in apps


def test_filter_for_target_opencode_keeps_opencode_workspace_and_none() -> None:
    plan = SyncPlan(
        actions=[
            _action(app="cursor"),
            _action(app="opencode"),
            _action(app="codex"),
            _action(app="workspace"),
            _action(app=None),
        ],
        errors=[],
        skipped=[],
    )

    result = plan.filter_for_target("opencode")

    apps = [a.app for a in result.actions]
    assert "opencode" in apps
    assert "workspace" in apps
    assert None in apps
    assert "cursor" not in apps
    assert "codex" not in apps


def test_filter_for_target_opencode_app_none_kept() -> None:
    plan = SyncPlan(
        actions=[_action(app=None, path="/tmp/skill_link")],
        errors=[],
        skipped=[],
    )

    result = plan.filter_for_target("opencode")

    assert len(result.actions) == 1
    assert result.actions[0].app is None


def test_filter_for_target_preserves_errors_and_skipped() -> None:
    plan = SyncPlan(
        actions=[_action(app="cursor")],
        errors=[ValueError("test error")],
        skipped=["skipped item"],
    )

    result = plan.filter_for_target("cursor")

    assert len(result.errors) == 1
    assert len(result.skipped) == 1


# --- summary ---


def test_summary_counts_statuses() -> None:
    plan = SyncPlan(
        actions=[
            _action(status=ActionStatus.CREATE),
            _action(status=ActionStatus.CREATE),
            _action(status=ActionStatus.NOOP),
            _action(status=ActionStatus.UPDATE),
            _action(status=ActionStatus.CONFLICT),
        ],
        errors=[ValueError("err")],
        skipped=["skip1", "skip2"],
    )

    summary = plan.summary()

    assert summary["create"] == 2
    assert summary["noop"] == 1
    assert summary["update"] == 1
    assert summary["conflict"] == 1
    assert summary["fix"] == 0
    assert summary["remove"] == 0
    assert summary["actions"] == 5
    assert summary["errors"] == 1
    assert summary["skipped"] == 2


def test_summary_empty_plan() -> None:
    plan = SyncPlan(actions=[], errors=[], skipped=[])

    summary = plan.summary()

    assert summary["actions"] == 0
    assert summary["errors"] == 0
    assert summary["skipped"] == 0


# --- is_valid ---


def test_is_valid_no_errors() -> None:
    plan = SyncPlan(actions=[], errors=[], skipped=[])

    assert plan.is_valid() is True


def test_is_valid_with_errors() -> None:
    plan = SyncPlan(actions=[], errors=[ValueError("err")], skipped=[])

    assert plan.is_valid() is False


def test_sync_state_from_non_dict_payload_is_empty() -> None:
    assert SyncState.from_payload(None) == SyncState()
    assert SyncState.from_payload("garbage") == SyncState()
    assert SyncState.from_payload([1, 2, 3]) == SyncState()


def test_sync_state_from_payload_normalizes_all_fields() -> None:
    state = SyncState.from_payload(
        {
            "managed_links": {"app:cursor:skills": ["/a", 5, "/b"]},
            "managed_paths": {"scope": ["/p"], 7: ["ignored"]},
            "managed_mcp": {"app:claude:projects": ["/repo"]},
            "managed_skill_links": ["x", 1, "y"],
            "skipped": ["s1"],
            "updated_at": "2026-07-21T00:00:00",
        }
    )

    # non-str entries and non-str scope keys are dropped
    assert state.managed_links == {"app:cursor:skills": ["/a", "/b"]}
    assert state.managed_paths == {"scope": ["/p"]}
    assert state.managed_mcp == {"app:claude:projects": ["/repo"]}
    assert state.managed_skill_links == ["x", "y"]
    assert state.skipped == ["s1"]
    assert state.updated_at == "2026-07-21T00:00:00"


def test_sync_state_from_payload_coerces_wrong_types() -> None:
    state = SyncState.from_payload(
        {
            "managed_links": "not-a-dict",
            "managed_paths": {"scope": "not-a-list"},
            "managed_skill_links": "not-a-list",
            "updated_at": 12345,
        }
    )

    assert state.managed_links == {}
    assert state.managed_paths == {}  # non-list value drops the scope
    assert state.managed_skill_links == []
    assert state.updated_at is None
