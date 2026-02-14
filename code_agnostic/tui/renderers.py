from rich.console import Console

from code_agnostic.imports.models import ImportApplyResult, ImportPlan
from code_agnostic.models import (
    AppStatusRow,
    EditorStatusRow,
    SyncPlan,
    WorkspaceStatusRow,
    WorkspaceSyncStatus,
)
from code_agnostic.tui.enums import UIStyle
from code_agnostic.tui.sections import UISection
from code_agnostic.tui.tables import (
    AppsTable,
    ApplyTable,
    ImportTable,
    PlanTable,
    StatusTable,
    WorkspaceTable,
)
from code_agnostic.utils import compact_home_path, compact_home_paths_in_text


class SyncConsoleUI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render_plan(self, plan: SyncPlan, mode: str, verbose: bool = False) -> None:
        app_actions, workspace_actions = PlanTable.split_actions(plan)

        self.console.print(
            UISection.wrap(
                "plan overview",
                PlanTable.summary_block(plan, mode=mode),
                style=UIStyle.BLUE.value,
            )
        )

        if app_actions:
            self.console.print(
                UISection.wrap(
                    "app config sync",
                    PlanTable.actions_table(app_actions, verbose=verbose),
                    style=UIStyle.CYAN.value,
                )
            )
        if workspace_actions:
            self.console.print(
                UISection.wrap(
                    "workspace config sync",
                    PlanTable.actions_table(workspace_actions, verbose=verbose),
                    style=UIStyle.MAGENTA.value,
                )
            )
        if not app_actions and not workspace_actions:
            self.console.print(
                UISection.note(
                    "actions", "No actions required.", style=UIStyle.DIM.value
                )
            )

        if plan.errors:
            errors_text = "\n".join(
                [f"- {compact_home_paths_in_text(str(item))}" for item in plan.errors]
            )
            self.console.print(
                UISection.note("errors", errors_text, style=UIStyle.RED.value)
            )

        if plan.skipped:
            skipped_text = "\n".join(
                [f"- {compact_home_paths_in_text(item)}" for item in plan.skipped]
            )
            self.console.print(
                UISection.note("skipped", skipped_text, style=UIStyle.YELLOW.value)
            )

        self.console.print(
            UISection.note(
                "next",
                "Enable target app sync, then run apply.\n"
                "- code-agnostic apps enable <app>\n"
                "- code-agnostic apply <app>",
                style=UIStyle.DIM.value,
            )
        )

    def render_apply_result(
        self, applied: int, failed: int, failures: list[str]
    ) -> None:
        self.console.print(ApplyTable.stats_panel(applied=applied, failed=failed))
        if failures:
            failure_text = "\n".join(
                [f"- {compact_home_paths_in_text(item)}" for item in failures]
            )
            self.console.print(
                UISection.note("failures", failure_text, style=UIStyle.RED.value)
            )

    def render_workspace_saved(
        self, name: str, path: str, removed: bool = False
    ) -> None:
        verb = "removed" if removed else "added"
        border_style = UIStyle.YELLOW.value if removed else UIStyle.GREEN.value
        self.console.print(
            UISection.note(
                "workspace",
                f"Workspace {verb}: [bold]{name}[/bold]\n{compact_home_path(path)}",
                style=border_style,
            )
        )

    def render_workspaces_overview(self, items: list[dict]) -> None:
        if not items:
            self.console.print(
                UISection.note(
                    "workspaces",
                    "No workspaces configured.",
                    style=UIStyle.YELLOW.value,
                )
            )
            return

        self.console.print(
            UISection.wrap(
                "workspaces",
                WorkspaceTable.overview_table(items),
                style=UIStyle.BLUE.value,
            )
        )
        self.console.print(
            UISection.wrap(
                "workspace repositories",
                WorkspaceTable.repos_table(items),
                style=UIStyle.CYAN.value,
            )
        )

    def render_status(
        self, editors: list[EditorStatusRow], workspaces: list[WorkspaceStatusRow]
    ) -> None:
        self.console.print(
            UISection.wrap(
                "app config sync",
                StatusTable.editor_table(editors),
                style=UIStyle.BLUE.value,
            )
        )

        if not workspaces:
            self.console.print(
                UISection.note(
                    "workspace sync",
                    "No workspaces configured.",
                    style=UIStyle.YELLOW.value,
                )
            )
            return

        workspace_style = UIStyle.GREEN.value
        if any(item.status == WorkspaceSyncStatus.DRIFT for item in workspaces):
            workspace_style = UIStyle.YELLOW.value
        if any(item.status == WorkspaceSyncStatus.ERROR for item in workspaces):
            workspace_style = UIStyle.RED.value

        self.console.print(
            UISection.wrap(
                "workspace sync",
                StatusTable.workspace_overview(workspaces),
                style=workspace_style,
            )
        )
        self.console.print(
            UISection.wrap(
                "workspace repositories",
                StatusTable.workspace_repos_group(workspaces),
                style=UIStyle.CYAN.value,
            )
        )

    def render_apps(self, items: list[AppStatusRow]) -> None:
        self.console.print(
            UISection.wrap(
                "apps", AppsTable.apps_table(items), style=UIStyle.BLUE.value
            )
        )

    def render_import_plan(
        self, plan: ImportPlan, mode: str, verbose: bool = False
    ) -> None:
        mcp_actions, skill_actions, agent_actions = ImportTable.split_actions(plan)

        self.console.print(
            UISection.wrap(
                "import overview",
                ImportTable.summary_block(plan, mode=mode),
                style=UIStyle.BLUE.value,
            )
        )

        if mcp_actions:
            self.console.print(
                UISection.wrap(
                    "mcp import",
                    ImportTable.actions_table(
                        mcp_actions, source_app=plan.source_app, verbose=verbose
                    ),
                    style=UIStyle.CYAN.value,
                )
            )
        if skill_actions:
            self.console.print(
                UISection.wrap(
                    "skills import",
                    ImportTable.actions_table(
                        skill_actions, source_app=plan.source_app, verbose=verbose
                    ),
                    style=UIStyle.MAGENTA.value,
                )
            )
        if agent_actions:
            self.console.print(
                UISection.wrap(
                    "agents import",
                    ImportTable.actions_table(
                        agent_actions, source_app=plan.source_app, verbose=verbose
                    ),
                    style=UIStyle.GREEN.value,
                )
            )

        if plan.errors:
            errors_text = "\n".join(
                [f"- {compact_home_paths_in_text(item)}" for item in plan.errors]
            )
            self.console.print(
                UISection.note("errors", errors_text, style=UIStyle.RED.value)
            )
        if plan.skipped:
            skipped_text = "\n".join(
                [f"- {compact_home_paths_in_text(item)}" for item in plan.skipped]
            )
            self.console.print(
                UISection.note("skipped", skipped_text, style=UIStyle.YELLOW.value)
            )

    def render_import_apply_result(self, result: ImportApplyResult) -> None:
        self.render_apply_result(
            applied=result.applied,
            failed=result.failed,
            failures=result.failures,
        )
