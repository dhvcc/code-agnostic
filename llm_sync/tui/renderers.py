from typing import List, Optional

from rich.console import Console

from llm_sync.models import PlanResult, WorkspaceSyncStatus
from llm_sync.tui.enums import UIStyle
from llm_sync.tui.sections import UISection
from llm_sync.tui.tables import AppsTable, ApplyTable, PlanTable, StatusTable, WorkspaceTable


class SyncConsoleUI:
    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    def render_plan(self, plan: PlanResult, mode: str) -> None:
        app_actions, workspace_actions = PlanTable.split_actions(plan)

        self.console.print(UISection.wrap("plan overview", PlanTable.summary_block(plan, mode=mode), style=UIStyle.BLUE.value))

        if app_actions:
            self.console.print(
                UISection.wrap("app config sync", PlanTable.actions_table(app_actions), style=UIStyle.CYAN.value)
            )
        if workspace_actions:
            self.console.print(
                UISection.wrap("workspace links", PlanTable.actions_table(workspace_actions), style=UIStyle.MAGENTA.value)
            )
        if not app_actions and not workspace_actions:
            self.console.print(UISection.note("actions", "No actions required.", style=UIStyle.DIM.value))

        if plan.errors:
            errors_text = "\n".join([f"- {item}" for item in plan.errors])
            self.console.print(UISection.note("errors", errors_text, style=UIStyle.RED.value))

        if plan.skipped:
            skipped_text = "\n".join([f"- {item}" for item in plan.skipped])
            self.console.print(UISection.note("skipped", skipped_text, style=UIStyle.YELLOW.value))

    def render_apply_result(self, applied: int, failed: int, failures: List[str], state_path: str) -> None:
        self.console.print(ApplyTable.stats_panel(applied=applied, failed=failed, state_path=state_path))
        if failures:
            failure_text = "\n".join([f"- {item}" for item in failures])
            self.console.print(UISection.note("failures", failure_text, style=UIStyle.RED.value))

    def render_workspace_saved(self, name: str, path: str, removed: bool = False) -> None:
        verb = "removed" if removed else "added"
        border_style = UIStyle.YELLOW.value if removed else UIStyle.GREEN.value
        self.console.print(UISection.note("workspace", f"Workspace {verb}: [bold]{name}[/bold]\n{path}", style=border_style))

    def render_workspaces_overview(self, items: List[dict]) -> None:
        if not items:
            self.console.print(UISection.note("workspaces", "No workspaces configured.", style=UIStyle.YELLOW.value))
            return

        self.console.print(UISection.wrap("workspaces", WorkspaceTable.overview_table(items), style=UIStyle.BLUE.value))
        self.console.print(UISection.wrap("workspace repositories", WorkspaceTable.repos_table(items), style=UIStyle.CYAN.value))

    def render_status(self, editors: List[dict], workspaces: List[dict]) -> None:
        self.console.print(UISection.wrap("app config sync", StatusTable.editor_table(editors), style=UIStyle.BLUE.value))

        if not workspaces:
            self.console.print(UISection.note("workspace sync", "No workspaces configured.", style=UIStyle.YELLOW.value))
            return

        workspace_style = UIStyle.GREEN.value
        if any(item.get("status") == WorkspaceSyncStatus.DRIFT.value for item in workspaces):
            workspace_style = UIStyle.YELLOW.value
        if any(item.get("status") == WorkspaceSyncStatus.ERROR.value for item in workspaces):
            workspace_style = UIStyle.RED.value

        self.console.print(
            UISection.wrap("workspace sync", StatusTable.workspace_overview(workspaces), style=workspace_style)
        )
        self.console.print(
            UISection.wrap("workspace repositories", StatusTable.workspace_repos_group(workspaces), style=UIStyle.CYAN.value)
        )

    def render_apps(self, items: List[dict]) -> None:
        self.console.print(UISection.wrap("apps", AppsTable.apps_table(items), style=UIStyle.BLUE.value))
