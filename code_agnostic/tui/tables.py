from collections import Counter

from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

from code_agnostic.constants import AGENTS_FILENAME
from code_agnostic.imports.models import ImportAction, ImportActionStatus, ImportPlan
from code_agnostic.models import (
    Action,
    AppStatusRow,
    AppSyncStatus,
    EditorStatusRow,
    EditorSyncStatus,
    RepoSyncStatus,
    SyncPlan,
    WorkspaceStatusRow,
    WorkspaceSyncStatus,
)
from code_agnostic.tui.enums import ACTION_STATUS_STYLE, UIStyle


IMPORT_STATUS_STYLE = {
    ImportActionStatus.CREATE: UIStyle.GREEN.value,
    ImportActionStatus.UPDATE: UIStyle.CYAN.value,
    ImportActionStatus.NOOP: UIStyle.DIM.value,
    ImportActionStatus.SKIP: UIStyle.YELLOW.value,
    ImportActionStatus.CONFLICT: UIStyle.RED.value,
}


class PlanTable:
    @staticmethod
    def summary_block(plan: SyncPlan, mode: str):
        counts = Counter(action.status.value for action in plan.actions)
        chips = [f"{key}={value}" for key, value in sorted(counts.items()) if value > 0]
        if not chips:
            chips = ["none"]

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold")
        table.add_column()
        table.add_row("Mode", mode)
        table.add_row("Actions", str(len(plan.actions)))
        table.add_row("Statuses", "  ".join(chips))
        return table

    @staticmethod
    def split_actions(plan: SyncPlan) -> tuple[list[Action], list[Action]]:
        app_actions: list[Action] = []
        workspace_actions: list[Action] = []
        for action in plan.actions:
            is_workspace_link = action.path.name == AGENTS_FILENAME
            if is_workspace_link:
                workspace_actions.append(action)
            else:
                app_actions.append(action)
        return app_actions, workspace_actions

    @staticmethod
    def actions_table(actions: list[Action]) -> Table:
        table = Table(
            Column(header="Type", width=12),
            Column(header="Status", width=10),
            Column(header="Target", overflow="ellipsis", max_width=58),
            Column(header="Source", overflow="ellipsis", max_width=42),
            Column(header="Reason", overflow="ellipsis"),
            expand=True,
            header_style="bold",
        )

        for action in actions:
            source = str(action.source) if action.source is not None else ""
            status_value = action.status.value
            status_style = ACTION_STATUS_STYLE.get(action.status, UIStyle.WHITE.value)
            status_text = f"[{status_style}]{status_value}[/{status_style}]"
            table.add_row(
                action.kind.value, status_text, str(action.path), source, action.detail
            )
        return table


class ApplyTable:
    @staticmethod
    def stats_panel(applied: int, failed: int) -> Panel:
        stats: dict[str, str] = {
            "applied": str(applied),
            "failed": str(failed),
        }
        table = Table(show_header=False, box=None)
        for key, value in stats.items():
            table.add_row(f"[bold]{key}[/bold]", value)
        return Panel(
            table,
            title="apply",
            border_style=UIStyle.GREEN.value if failed == 0 else UIStyle.RED.value,
        )


class WorkspaceTable:
    @staticmethod
    def overview_table(items: list[dict]) -> Table:
        table = Table(
            Column(header="Workspace", width=24),
            Column(header="Path", overflow="ellipsis"),
            Column(header="Repos", width=8, justify="right"),
            expand=True,
            header_style="bold",
        )
        for item in items:
            table.add_row(item["name"], item["path"], str(len(item["repos"])))
        return table

    @staticmethod
    def repos_table(items: list[dict]) -> Table:
        table = Table(
            Column(header="Workspace", width=24),
            Column(header="Repositories", overflow="fold"),
            expand=True,
            header_style="bold",
        )
        for item in items:
            repos = item.get("repos", [])
            if not repos:
                repo_line = "(no git repos found)"
            else:
                repo_line = ", ".join(repos)
            table.add_row(item["name"], repo_line)
        return table


class StatusTable:
    @staticmethod
    def editor_table(items: list[EditorStatusRow]) -> Table:
        table = Table(
            "Editor",
            "Status",
            "Detail",
            expand=True,
            header_style="bold",
        )
        for item in items:
            status = item.status
            style = (
                UIStyle.GREEN.value
                if status == EditorSyncStatus.SYNCED
                else UIStyle.YELLOW.value
                if status == EditorSyncStatus.DISABLED
                else UIStyle.RED.value
            )
            table.add_row(item.name, f"[{style}]{status.value}[/{style}]", item.detail)
        return table

    @staticmethod
    def workspace_overview(items: list[WorkspaceStatusRow]) -> Table:
        table = Table(
            Column(header="Workspace", width=24),
            Column(header="Status", width=12),
            Column(header="Repos", width=8, justify="right"),
            Column(header="Detail", overflow="ellipsis"),
            expand=True,
            header_style="bold",
        )
        for item in items:
            status = item.status
            style = (
                UIStyle.GREEN.value
                if status == WorkspaceSyncStatus.SYNCED
                else UIStyle.RED.value
                if status == WorkspaceSyncStatus.ERROR
                else UIStyle.YELLOW.value
            )
            table.add_row(
                item.name,
                f"[{style}]{status.value}[/{style}]",
                str(len(item.repos)),
                item.detail,
            )
        return table

    @staticmethod
    def workspace_repos_group(items: list[WorkspaceStatusRow]):
        blocks = []
        for item in items:
            repos = item.repos
            heading = Text(item.name, style="bold")
            if not repos:
                blocks.append(
                    Group(
                        heading, Text("  (no git repos found)", style=UIStyle.DIM.value)
                    )
                )
                continue

            repo_table = Table(
                Column(header="Repo", width=28),
                Column(header="Status", width=12),
                Column(header="Detail", overflow="ellipsis"),
                expand=True,
                header_style="bold",
            )
            for repo in repos:
                status = repo.status
                style = (
                    UIStyle.GREEN.value
                    if status == RepoSyncStatus.SYNCED
                    else UIStyle.YELLOW.value
                )
                label = (
                    RepoSyncStatus.SYNCED.value
                    if status == RepoSyncStatus.SYNCED
                    else "needs sync"
                )
                repo_table.add_row(
                    repo.repo, f"[{style}]{label}[/{style}]", repo.detail
                )
            blocks.append(Group(heading, Padding(repo_table, (0, 0, 0, 2))))

        if not blocks:
            return Text("No workspace details.", style=UIStyle.DIM.value)
        return Group(*blocks)


class AppsTable:
    @staticmethod
    def apps_table(items: list[AppStatusRow]) -> Table:
        table = Table(
            Column(header="App", width=14),
            Column(header="Status", width=12),
            Column(header="Detail", overflow="ellipsis"),
            expand=True,
            header_style="bold",
        )
        for item in items:
            status = item.status
            style = (
                UIStyle.GREEN.value
                if status == AppSyncStatus.ENABLED
                else UIStyle.YELLOW.value
            )
            table.add_row(item.name, f"[{style}]{status.value}[/{style}]", item.detail)
        return table


class ImportTable:
    @staticmethod
    def summary_block(plan: ImportPlan, mode: str):
        counts = Counter(action.status.value for action in plan.actions)
        chips = [f"{key}={value}" for key, value in sorted(counts.items()) if value > 0]
        if not chips:
            chips = ["none"]

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold")
        table.add_column()
        table.add_row("Mode", mode)
        table.add_row("Source", plan.source_app)
        table.add_row("Sections", ", ".join(section.value for section in plan.sections))
        table.add_row("Actions", str(len(plan.actions)))
        table.add_row("Statuses", "  ".join(chips))
        return table

    @staticmethod
    def actions_table(actions: list[ImportAction]) -> Table:
        table = Table(
            Column(header="Section", width=10),
            Column(header="Status", width=10),
            Column(header="Source", overflow="ellipsis", max_width=50),
            Column(header="Target", overflow="ellipsis", max_width=50),
            Column(header="Detail", overflow="ellipsis"),
            expand=True,
            header_style="bold",
        )

        for action in actions:
            style = IMPORT_STATUS_STYLE.get(action.status, UIStyle.WHITE.value)
            status_text = f"[{style}]{action.status.value}[/{style}]"
            table.add_row(
                action.section.value,
                status_text,
                str(action.source) if action.source is not None else "",
                str(action.target) if action.target is not None else "",
                action.detail,
            )
        return table

    @staticmethod
    def split_actions(
        plan: ImportPlan,
    ) -> tuple[list[ImportAction], list[ImportAction], list[ImportAction]]:
        mcp: list[ImportAction] = []
        skills: list[ImportAction] = []
        agents: list[ImportAction] = []
        for action in plan.actions:
            if action.section.value == "mcp":
                mcp.append(action)
            elif action.section.value == "skills":
                skills.append(action)
            elif action.section.value == "agents":
                agents.append(action)
        return mcp, skills, agents
