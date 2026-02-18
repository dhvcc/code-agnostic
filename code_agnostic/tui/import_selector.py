"""Interactive Textual-based selector for import operations."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, SelectionList, Static
from textual.widgets.selection_list import Selection

from code_agnostic.imports.models import ImportAction, ImportActionStatus, ImportPlan


class ImportSelectorApp(App[list[int]]):
    """Interactive selector for choosing which items to import."""

    TITLE = "Import Selector"
    CSS_DEFAULT = """
    Screen {
        layout: vertical;
    }
    #info {
        height: 3;
        content-align: center middle;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }
    SelectionList {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("a", "select_all", "Select All"),
        Binding("n", "select_none", "Select None"),
        Binding("enter", "confirm", "Confirm"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, plan: ImportPlan) -> None:
        super().__init__()
        self._plan = plan
        self._actionable_indices: list[int] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            f"Source: {self._plan.source_app} | "
            f"Actions: {len(self._plan.actions)} | "
            f"Use [a] select all, [n] select none, [enter] confirm",
            id="info",
        )

        selections: list[Selection[int]] = []
        for i, action in enumerate(self._plan.actions):
            if action.status in (
                ImportActionStatus.NOOP,
                ImportActionStatus.SKIP,
            ):
                continue
            self._actionable_indices.append(i)
            label = f"[{action.section.value}] {action.status.value}: {action.detail}"
            selections.append(Selection(label, i, True))

        yield SelectionList[int](*selections)
        yield Footer()

    def action_select_all(self) -> None:
        sel = self.query_one(SelectionList)
        sel.select_all()

    def action_select_none(self) -> None:
        sel = self.query_one(SelectionList)
        sel.deselect_all()

    def action_confirm(self) -> None:
        sel = self.query_one(SelectionList)
        self.exit(list(sel.selected))

    def action_quit_app(self) -> None:
        self.exit([])

    def get_selected_actions(self, selected_indices: list[int]) -> list[ImportAction]:
        return [self._plan.actions[i] for i in selected_indices]


def filter_plan_by_selection(
    plan: ImportPlan, selected_indices: list[int]
) -> ImportPlan:
    """Create a new plan containing only the selected actions."""
    selected_set = set(selected_indices)
    filtered = [action for i, action in enumerate(plan.actions) if i in selected_set]
    return ImportPlan(
        source_app=plan.source_app,
        sections=plan.sections,
        actions=filtered,
        errors=plan.errors,
        skipped=plan.skipped,
    )
