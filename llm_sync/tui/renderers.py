from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from llm_sync.models import PlanResult
from llm_sync.tui.enums import UIStyle
from llm_sync.tui.tables import ApplyTable, PlanTable, StatusTable, WorkspaceTable


class SyncConsoleUI:
    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    def render_plan(self, plan: PlanResult, mode: str) -> None:
        self.console.print(PlanTable.summary_panel(plan, mode=mode))
        self.console.print(PlanTable.actions_table(plan))

        if plan.errors:
            errors_text = "\n".join([f"- {item}" for item in plan.errors])
            self.console.print(Panel(errors_text, title="errors", border_style=UIStyle.RED.value))

        if plan.skipped:
            skipped_text = "\n".join([f"- {item}" for item in plan.skipped])
            self.console.print(Panel(skipped_text, title="skipped", border_style=UIStyle.YELLOW.value))

    def render_apply_result(self, applied: int, failed: int, failures: List[str], state_path: str) -> None:
        self.console.print(ApplyTable.stats_panel(applied=applied, failed=failed, state_path=state_path))
        if failures:
            failure_text = "\n".join([f"- {item}" for item in failures])
            self.console.print(Panel(failure_text, title="failures", border_style=UIStyle.RED.value))

    def render_workspace_saved(self, name: str, path: str, removed: bool = False) -> None:
        verb = "removed" if removed else "added"
        border_style = UIStyle.YELLOW.value if removed else UIStyle.GREEN.value
        self.console.print(Panel.fit(f"Workspace {verb}: [bold]{name}[/bold]\n{path}", border_style=border_style))

    def render_workspaces_overview(self, items: List[dict]) -> None:
        if not items:
            self.console.print(Panel.fit("No workspaces configured.", border_style=UIStyle.YELLOW.value, title="workspaces"))
            return

        self.console.print(Panel(WorkspaceTable.overview_table(items), title="workspaces", border_style=UIStyle.BLUE.value))

        for item in items:
            repos = item["repos"]
            repo_line = ", ".join(repos[:8])
            if len(repos) > 8:
                repo_line += ", ..."
            if not repo_line:
                repo_line = "(no git repos found)"
            self.console.print(f"[bold]{item['name']}[/bold]: {repo_line}")

    def render_status(self, editors: List[dict], workspaces: List[dict]) -> None:
        self.console.print(Panel(StatusTable.editor_table(editors), title="editor status", border_style=UIStyle.BLUE.value))

        root = Tree("[bold]workspace status[/bold]")
        if not workspaces:
            root.add(f"[{UIStyle.YELLOW.value}]no workspaces configured[/{UIStyle.YELLOW.value}]")
            self.console.print(root)
            return

        for workspace in workspaces:
            ws_style = UIStyle.GREEN.value if workspace["status"] == "synced" else UIStyle.RED.value if workspace["status"] == "error" else UIStyle.YELLOW.value
            ws_node = root.add(
                f"[{ws_style}]{workspace['name']}[/{ws_style}] - {workspace['detail']} ({workspace['path']})"
            )
            repos = workspace.get("repos", [])
            if not repos:
                ws_node.add(f"[{UIStyle.DIM.value}](no git repos found)[/{UIStyle.DIM.value}]")
                continue
            for repo in repos:
                repo_style = UIStyle.GREEN.value if repo["status"] == "synced" else UIStyle.YELLOW.value
                repo_label = "synced" if repo["status"] == "synced" else "needs sync"
                ws_node.add(f"[{repo_style}]{repo['repo']}[/{repo_style}] - {repo_label}")

        self.console.print(root)
