from collections import Counter
from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from llm_sync.models import PlanResult


def _status_style(status: str) -> str:
    mapping = {
        "create": "green",
        "update": "cyan",
        "fix": "yellow",
        "remove": "magenta",
        "noop": "dim",
        "conflict": "red",
    }
    return mapping.get(status, "white")


def render_plan(console: Console, plan: PlanResult, mode: str) -> None:
    counts = Counter(action.status for action in plan.actions)
    counts_line = " ".join([f"{key}:{value}" for key, value in sorted(counts.items())])
    console.print(
        Panel.fit(
            f"[bold]Mode:[/bold] {mode}   [bold]Actions:[/bold] {len(plan.actions)}   [bold]Status:[/bold] {counts_line or 'none'}",
            title="llm-sync",
            border_style="blue",
        )
    )

    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Action", width=10)
    table.add_column("Status", width=10)
    table.add_column("Path", overflow="ellipsis", max_width=56)
    table.add_column("Source", overflow="ellipsis", max_width=56)
    table.add_column("Detail", overflow="ellipsis")

    for action in plan.actions:
        source = str(action.source) if action.source is not None else ""
        status_text = f"[{_status_style(action.status)}]{action.status}[/{_status_style(action.status)}]"
        table.add_row(action.kind, status_text, str(action.path), source, action.detail)

    console.print(table)

    if plan.errors:
        errors_text = "\n".join([f"- {item}" for item in plan.errors])
        console.print(Panel(errors_text, title="errors", border_style="red"))

    if plan.skipped:
        skipped_text = "\n".join([f"- {item}" for item in plan.skipped])
        console.print(Panel(skipped_text, title="skipped", border_style="yellow"))


def render_apply_result(console: Console, applied: int, failed: int, failures: List[str], state_path: str) -> None:
    stats: Dict[str, str] = {
        "applied": str(applied),
        "failed": str(failed),
        "state": state_path,
    }

    stats_table = Table(show_header=False, box=None)
    for key, value in stats.items():
        stats_table.add_row(f"[bold]{key}[/bold]", value)
    console.print(Panel(stats_table, title="apply", border_style="green" if failed == 0 else "red"))

    if failures:
        failure_text = "\n".join([f"- {item}" for item in failures])
        console.print(Panel(failure_text, title="failures", border_style="red"))


def render_workspace_saved(console: Console, name: str, path: str, removed: bool = False) -> None:
    verb = "removed" if removed else "added"
    style = "yellow" if removed else "green"
    console.print(Panel.fit(f"Workspace {verb}: [bold]{name}[/bold]\n{path}", border_style=style))


def render_workspaces_overview(console: Console, items: List[dict]) -> None:
    if not items:
        console.print(Panel.fit("No workspaces configured.", border_style="yellow", title="workspaces"))
        return

    summary = Table(show_header=True, header_style="bold", expand=True)
    summary.add_column("Workspace", width=24)
    summary.add_column("Path", overflow="ellipsis")
    summary.add_column("Repos", width=8, justify="right")

    for item in items:
        summary.add_row(item["name"], item["path"], str(len(item["repos"])))

    console.print(Panel(summary, title="workspaces", border_style="blue"))

    for item in items:
        repos = item["repos"]
        repo_line = ", ".join(repos[:8])
        if len(repos) > 8:
            repo_line += ", ..."
        if not repo_line:
            repo_line = "(no git repos found)"
        console.print(f"[bold]{item['name']}[/bold]: {repo_line}")


def render_status(console: Console, editors: List[dict], workspaces: List[dict]) -> None:
    editor_table = Table(show_header=True, header_style="bold", expand=True)
    editor_table.add_column("Editor", width=16)
    editor_table.add_column("Status", width=12)
    editor_table.add_column("Detail")

    for item in editors:
        status = item["status"]
        style = "green" if status == "synced" else "yellow" if status == "disabled" else "red"
        editor_table.add_row(item["name"], f"[{style}]{status}[/{style}]", item["detail"])

    console.print(Panel(editor_table, title="editor status", border_style="blue"))

    root = Tree("[bold]workspace status[/bold]")
    if not workspaces:
        root.add("[yellow]no workspaces configured[/yellow]")
        console.print(root)
        return

    for workspace in workspaces:
        ws_style = "green" if workspace["status"] == "synced" else "red" if workspace["status"] == "error" else "yellow"
        ws_node = root.add(
            f"[{ws_style}]{workspace['name']}[/{ws_style}] - {workspace['detail']} ({workspace['path']})"
        )
        repos = workspace.get("repos", [])
        if not repos:
            ws_node.add("[dim](no git repos found)[/dim]")
            continue
        for repo in repos:
            repo_style = "green" if repo["status"] == "synced" else "yellow"
            repo_label = "synced" if repo["status"] == "synced" else "needs sync"
            ws_node.add(f"[{repo_style}]{repo['repo']}[/{repo_style}] - {repo_label}")

    console.print(root)
