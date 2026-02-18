"""Tests for the interactive import selector TUI."""

from __future__ import annotations

import pytest

from code_agnostic.imports.models import (
    ImportAction,
    ImportActionKind,
    ImportActionStatus,
    ImportPlan,
    ImportSection,
)
from code_agnostic.tui.import_selector import (
    ImportSelectorApp,
    filter_plan_by_selection,
)


def _make_plan(actions: list[ImportAction] | None = None) -> ImportPlan:
    if actions is None:
        actions = [
            ImportAction(
                section=ImportSection.MCP,
                kind=ImportActionKind.WRITE_MCP_BASE,
                status=ImportActionStatus.CREATE,
                detail="add server 'demo'",
            ),
            ImportAction(
                section=ImportSection.SKILLS,
                kind=ImportActionKind.COPY_PATH,
                status=ImportActionStatus.CREATE,
                detail="copy skill 'my-skill'",
            ),
            ImportAction(
                section=ImportSection.MCP,
                kind=ImportActionKind.NOTE,
                status=ImportActionStatus.NOOP,
                detail="server 'existing' already present",
            ),
            ImportAction(
                section=ImportSection.MCP,
                kind=ImportActionKind.NOTE,
                status=ImportActionStatus.SKIP,
                detail="server 'skipped' conflict",
            ),
        ]
    return ImportPlan(
        source_app="codex",
        sections=[ImportSection.MCP, ImportSection.SKILLS],
        actions=actions,
        errors=[],
        skipped=[],
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_all_actionable_items_shown() -> None:
    """NOOP and SKIP actions should be excluded from the selection list."""
    plan = _make_plan()
    app = ImportSelectorApp(plan)
    async with app.run_test():
        sel = app.query_one("SelectionList")
        # Only index 0 (CREATE mcp) and 1 (CREATE skills) are actionable
        assert len(sel._options) == 2


@pytest.mark.asyncio(loop_scope="function")
async def test_select_all_action() -> None:
    plan = _make_plan()
    app = ImportSelectorApp(plan)
    async with app.run_test() as pilot:
        await pilot.press("a")
        sel = app.query_one("SelectionList")
        assert len(sel.selected) == 2


@pytest.mark.asyncio(loop_scope="function")
async def test_select_none_action() -> None:
    plan = _make_plan()
    app = ImportSelectorApp(plan)
    async with app.run_test() as pilot:
        await pilot.press("n")
        sel = app.query_one("SelectionList")
        assert len(sel.selected) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_confirm_returns_selected_indices() -> None:
    plan = _make_plan()
    app = ImportSelectorApp(plan)
    async with app.run_test():
        # Call action_confirm directly since enter key may be consumed
        # by the focused SelectionList widget
        app.action_confirm()
    assert app.return_value is not None
    assert set(app.return_value) == {0, 1}


@pytest.mark.asyncio(loop_scope="function")
async def test_quit_returns_empty() -> None:
    plan = _make_plan()
    app = ImportSelectorApp(plan)
    async with app.run_test() as pilot:
        await pilot.press("q")
    assert app.return_value == []


def test_filter_plan_by_selection() -> None:
    plan = _make_plan()
    filtered = filter_plan_by_selection(plan, [1])
    assert len(filtered.actions) == 1
    assert filtered.actions[0].detail == "copy skill 'my-skill'"
    assert filtered.source_app == plan.source_app
    assert filtered.sections == plan.sections
    assert filtered.errors == plan.errors


def test_filter_plan_empty_selection() -> None:
    plan = _make_plan()
    filtered = filter_plan_by_selection(plan, [])
    assert len(filtered.actions) == 0


def test_get_selected_actions() -> None:
    plan = _make_plan()
    app_instance = ImportSelectorApp(plan)
    selected = app_instance.get_selected_actions([0, 1])
    assert len(selected) == 2
    assert selected[0].detail == "add server 'demo'"
    assert selected[1].detail == "copy skill 'my-skill'"
