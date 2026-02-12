from collections import Counter
from typing import Dict, List

from rich.panel import Panel
from rich.table import Column, Table

from llm_sync.models import PlanResult
from llm_sync.tui.enums import ACTION_STATUS_STYLE, UIStyle


class PlanTable:
    @staticmethod
    def summary_panel(plan: PlanResult, mode: str) -> Panel:
        counts = Counter(action.status.value for action in plan.actions)
        counts_line = " ".join([f"{key}:{value}" for key, value in sorted(counts.items())])
        return Panel.fit(
            f"[bold]Mode:[/bold] {mode}   [bold]Actions:[/bold] {len(plan.actions)}   [bold]Status:[/bold] {counts_line or 'none'}",
            title="llm-sync",
            border_style=UIStyle.BLUE.value,
        )

    @staticmethod
    def actions_table(plan: PlanResult) -> Table:
        table = Table(
            Column(header="Action", width=10),
            Column(header="Status", width=10),
            Column(header="Path", overflow="ellipsis", max_width=56),
            Column(header="Source", overflow="ellipsis", max_width=56),
            Column(header="Detail", overflow="ellipsis"),
            expand=True,
            header_style="bold",
        )

        for action in plan.actions:
            source = str(action.source) if action.source is not None else ""
            status_value = action.status.value
            status_style = ACTION_STATUS_STYLE.get(action.status, UIStyle.WHITE.value)
            status_text = f"[{status_style}]{status_value}[/{status_style}]"
            table.add_row(action.kind.value, status_text, str(action.path), source, action.detail)
        return table


class ApplyTable:
    @staticmethod
    def stats_panel(applied: int, failed: int, state_path: str) -> Panel:
        stats: Dict[str, str] = {
            "applied": str(applied),
            "failed": str(failed),
            "state": state_path,
        }
        table = Table(show_header=False, box=None)
        for key, value in stats.items():
            table.add_row(f"[bold]{key}[/bold]", value)
        return Panel(table, title="apply", border_style=UIStyle.GREEN.value if failed == 0 else UIStyle.RED.value)


class WorkspaceTable:
    @staticmethod
    def overview_table(items: List[dict]) -> Table:
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


class StatusTable:
    @staticmethod
    def editor_table(items: List[dict]) -> Table:
        table = Table(
            "Editor",
            "Status",
            "Detail",
            expand=True,
            header_style="bold",
        )
        for item in items:
            status = item["status"]
            style = UIStyle.GREEN.value if status == "synced" else UIStyle.YELLOW.value if status == "disabled" else UIStyle.RED.value
            table.add_row(item["name"], f"[{style}]{status}[/{style}]", item["detail"])
        return table
