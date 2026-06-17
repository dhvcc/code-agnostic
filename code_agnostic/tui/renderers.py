from rich.console import Console

from code_agnostic.apps.app_id import app_label
from code_agnostic.imports.models import (
    ImportActionStatus,
    ImportApplyResult,
    ImportPlan,
)
from code_agnostic.models import (
    AppStatusRow,
    EditorStatusRow,
    EditorSyncStatus,
    ProjectStatusRow,
    ProjectSyncStatus,
    SyncPlan,
    WorkspaceStatusRow,
    WorkspaceSyncStatus,
)
from code_agnostic.tui.enums import UIStyle
from code_agnostic.tui.sections import UISection
from code_agnostic.tui.tables import (
    AppsTable,
    ApplyTable,
    ConfigListTable,
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
        app_actions, workspace_actions, project_actions = PlanTable.split_actions(plan)

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
        if project_actions:
            self.console.print(
                UISection.wrap(
                    "project config sync",
                    PlanTable.actions_table(project_actions, verbose=verbose),
                    style=UIStyle.GREEN.value,
                )
            )
        if not app_actions and not workspace_actions and not project_actions:
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

        next_steps = self._next_steps(plan, mode)
        if next_steps:
            self.console.print(
                UISection.note("next", next_steps, style=UIStyle.DIM.value)
            )

    @staticmethod
    def _next_steps(plan: SyncPlan, mode: str) -> str | None:
        command, _, target = mode.partition(":")
        target = target or "all"
        is_scoped = target != "all"
        target_flag = f" -a {target}" if is_scoped else ""

        if command == "apply":
            return None

        if plan.errors:
            return (
                "Fix the errors above, then rerun the plan.\n"
                f"- code-agnostic plan{target_flag}"
            )

        if plan.actions:
            return (
                "Review the planned changes. If they match what you expect, apply them.\n"
                f"- code-agnostic apply{target_flag}"
            )

        if is_scoped and f"{target} is disabled for sync." in plan.skipped:
            return (
                f"Enable {target}, then preview and apply it.\n"
                f"- code-agnostic apps enable -a {target}\n"
                f"- code-agnostic plan -a {target}\n"
                f"- code-agnostic apply -a {target}"
            )

        if "No apps enabled for sync." in plan.skipped:
            if is_scoped:
                return (
                    f"Enable {target}, then preview and apply it.\n"
                    f"- code-agnostic apps enable -a {target}\n"
                    f"- code-agnostic plan -a {target}\n"
                    f"- code-agnostic apply -a {target}"
                )
            return (
                "Enable a target app, then preview and apply it.\n"
                "- code-agnostic apps enable -a <app>\n"
                "- code-agnostic plan -a <app>\n"
                "- code-agnostic apply -a <app>"
            )

        if is_scoped:
            return (
                f"No changes needed for {target}.\n- code-agnostic status -a {target}"
            )
        return "No changes needed.\n- code-agnostic status"

    def render_apply_result(
        self,
        applied: int,
        failed: int,
        failures: list[str],
        next_steps: str | None = None,
    ) -> None:
        self.console.print(ApplyTable.stats_panel(applied=applied, failed=failed))
        if failures:
            failure_text = "\n".join(
                [f"- {compact_home_paths_in_text(item)}" for item in failures]
            )
            self.console.print(
                UISection.note("failures", failure_text, style=UIStyle.RED.value)
            )
        if next_steps:
            self.console.print(
                UISection.note("next", next_steps, style=UIStyle.DIM.value)
            )

    def render_workspace_saved(
        self, name: str, path: str, removed: bool = False
    ) -> None:
        verb = "unregistered" if removed else "added"
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
                    "No workspaces configured.\n"
                    "- code-agnostic workspaces add --name <name> --path <path>",
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
        self,
        editors: list[EditorStatusRow],
        workspaces: list[WorkspaceStatusRow],
        projects: list[ProjectStatusRow] | None = None,
    ) -> None:
        self.console.print(
            UISection.wrap(
                "app config sync",
                StatusTable.editor_table(editors),
                style=UIStyle.BLUE.value,
            )
        )
        next_steps = self._status_next_steps(editors)
        if next_steps:
            self.console.print(
                UISection.note("next", next_steps, style=UIStyle.DIM.value)
            )

        if not workspaces:
            self.console.print(
                UISection.note(
                    "workspace sync",
                    "No workspaces configured.\n"
                    "- code-agnostic workspaces add --name <name> --path <path>",
                    style=UIStyle.YELLOW.value,
                )
            )
        else:
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
            workspace_errors = [
                item for item in workspaces if item.status == WorkspaceSyncStatus.ERROR
            ]
            if workspace_errors:
                errors_text = "\n".join(
                    [
                        f"- {item.name}: {compact_home_paths_in_text(item.detail)}"
                        for item in workspace_errors
                    ]
                )
                self.console.print(
                    UISection.note(
                        "workspace errors", errors_text, style=UIStyle.RED.value
                    )
                )
            self.console.print(
                UISection.wrap(
                    "workspace repositories",
                    StatusTable.workspace_repos_group(workspaces),
                    style=UIStyle.CYAN.value,
                )
            )

        project_rows = projects or []
        if not project_rows:
            return

        project_style = UIStyle.GREEN.value
        if any(item.status == ProjectSyncStatus.DRIFT for item in project_rows):
            project_style = UIStyle.YELLOW.value
        if any(item.status == ProjectSyncStatus.ERROR for item in project_rows):
            project_style = UIStyle.RED.value

        self.console.print(
            UISection.wrap(
                "project sync",
                StatusTable.project_overview(project_rows),
                style=project_style,
            )
        )

    @staticmethod
    def _status_next_steps(editors: list[EditorStatusRow]) -> str | None:
        if not editors or any(
            row.status != EditorSyncStatus.DISABLED for row in editors
        ):
            return None

        if len(editors) == 1:
            app = editors[0].name
            return (
                f"Enable {app}, then preview and apply it.\n"
                f"- code-agnostic apps enable -a {app}\n"
                f"- code-agnostic plan -a {app}\n"
                f"- code-agnostic apply -a {app}"
            )

        return (
            "Enable a target app, then preview and apply it.\n"
            "- code-agnostic apps enable -a <app>\n"
            "- code-agnostic plan -a <app>\n"
            "- code-agnostic apply -a <app>"
        )

    def render_apps(self, items: list[AppStatusRow]) -> None:
        self.console.print(
            UISection.wrap(
                "apps", AppsTable.apps_table(items), style=UIStyle.BLUE.value
            )
        )

    def render_app_enabled_next_steps(self, app: str) -> None:
        self.console.print(
            UISection.note(
                "next",
                f"Preview and apply {app}.\n"
                f"- code-agnostic plan -a {app}\n"
                f"- code-agnostic apply -a {app}",
                style=UIStyle.DIM.value,
            )
        )

    def render_list(
        self,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        empty_msg: str = "None configured.",
    ) -> None:
        if not rows:
            self.console.print(
                UISection.note(title, empty_msg, style=UIStyle.YELLOW.value)
            )
            return
        self.console.print(
            UISection.wrap(
                title,
                ConfigListTable.build(headers, rows),
                style=UIStyle.BLUE.value,
            )
        )

    def render_exclude_config(
        self, workspace: str, include_defaults: bool, extra_patterns: list[str]
    ) -> None:
        lines = [f"include_defaults: {include_defaults}"]
        if extra_patterns:
            lines.append("extra_patterns:")
            for p in extra_patterns:
                lines.append(f"  - {p}")
        else:
            lines.append("extra_patterns: (none)")
        self.console.print(
            UISection.note(
                f"git-exclude ({workspace})",
                "\n".join(lines),
                style=UIStyle.BLUE.value,
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

        next_steps = self._import_next_steps(plan, mode)
        if next_steps:
            self.console.print(
                UISection.note("next", next_steps, style=UIStyle.DIM.value)
            )

    @staticmethod
    def _import_next_steps(plan: ImportPlan, mode: str) -> str | None:
        parts = mode.split(":", 2)
        if len(parts) != 3:
            return None

        _, command, target = parts
        target_flag = f" -a {target}" if target else ""
        conflict_items = [*plan.errors, *plan.skipped]
        has_conflict = any("conflict" in item.lower() for item in conflict_items)

        if command == "apply":
            return None

        if plan.errors:
            lines = [
                "Fix the errors above, then rerun the import preview.",
                f"- code-agnostic import plan{target_flag}",
            ]
            if has_conflict:
                lines.append(
                    "For conflicts, choose --on-conflict overwrite or --on-conflict fail."
                )
            return "\n".join(lines)

        has_writes = any(
            action.status in {ImportActionStatus.CREATE, ImportActionStatus.UPDATE}
            for action in plan.actions
        )
        if has_writes:
            lines = [
                "Review the imported items. If they match what you expect, write them to the hub.",
                f"- code-agnostic import apply{target_flag}",
            ]
            if has_conflict:
                lines.append(
                    "Skipped conflicts will stay unchanged unless you rerun with --on-conflict overwrite."
                )
            return "\n".join(lines)

        if has_conflict:
            return (
                "Skipped conflicts were left unchanged.\n"
                f"- code-agnostic import plan{target_flag} --on-conflict overwrite"
            )

        if plan.skipped and all(
            item.lower().startswith("source ") and " missing:" in item.lower()
            for item in plan.skipped
        ):
            return (
                f"No importable {app_label(plan.source_app)} config found for the selected sections.\n"
                "Check --source-root, or choose a different source app."
            )

        return "No import changes needed.\n- code-agnostic validate"

    def render_import_apply_result(self, result: ImportApplyResult) -> None:
        self.render_apply_result(
            applied=result.applied,
            failed=result.failed,
            failures=result.failures,
        )
