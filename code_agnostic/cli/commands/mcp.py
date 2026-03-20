"""MCP group commands."""

import click
from rich.console import Console

from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.imports.models import ConflictPolicy
from code_agnostic.mcp_service import MCPManagementService
from code_agnostic.tui import SyncConsoleUI


def _parse_env_pair(raw: str) -> tuple[str, str]:
    if "=" in raw:
        key, _, value = raw.partition("=")
        return key, value
    return raw, f"${{{raw}}}"


@click.group(help="Manage MCP server definitions in the hub config.")
def mcp() -> None:
    pass


@mcp.command("list", help="List configured MCP servers.")
@workspace_option()
@click.pass_obj
def mcp_list(obj: dict[str, str], workspace: str | None) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = MCPManagementService(core)
    try:
        servers = service.list_servers(workspace=workspace)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    rows = [
        [name, dto.command or dto.url or ""] for name, dto in sorted(servers.items())
    ]
    ui.render_list(
        "mcp servers", ["Server", "Command / URL"], rows, "No MCP servers configured."
    )


@mcp.command("add", help="Add an MCP server definition.")
@click.argument("name")
@click.option("--command", default=None, help="Command for stdio server.")
@click.option(
    "--args", "args_str", default=None, help="Comma-separated args for stdio server."
)
@click.option("--url", default=None, help="URL for HTTP/SSE server.")
@click.option(
    "--timeout-ms",
    type=int,
    default=None,
    help="Request timeout in milliseconds.",
)
@click.option(
    "--env",
    "env_pairs",
    multiple=True,
    help="Env var as KEY or KEY=VALUE (repeatable).",
)
@click.option(
    "--headers", "header_pairs", multiple=True, help="Header as KEY=VALUE (repeatable)."
)
@click.option(
    "--on-conflict",
    type=click.Choice([item.value for item in ConflictPolicy]),
    default=ConflictPolicy.FAIL.value,
    show_default=True,
)
@workspace_option()
@click.pass_obj
def mcp_add(
    obj: dict[str, str],
    name: str,
    command: str | None,
    args_str: str | None,
    url: str | None,
    timeout_ms: int | None,
    env_pairs: tuple[str, ...],
    header_pairs: tuple[str, ...],
    on_conflict: str,
    workspace: str | None,
) -> None:
    args = [a.strip() for a in args_str.split(",")] if args_str else []
    env = dict(_parse_env_pair(p) for p in env_pairs) if env_pairs else {}
    headers = dict(_parse_env_pair(p) for p in header_pairs) if header_pairs else {}

    core = CoreRepository()
    service = MCPManagementService(core)
    try:
        msg = service.add_server(
            name=name,
            command=command,
            args=args or None,
            url=url,
            timeout_ms=timeout_ms,
            env=env or None,
            headers=headers or None,
            workspace=workspace,
            on_conflict=ConflictPolicy(on_conflict),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(msg)


@mcp.command("remove", help="Remove an MCP server definition.")
@click.argument("name")
@workspace_option()
@click.pass_obj
def mcp_remove(obj: dict[str, str], name: str, workspace: str | None) -> None:
    core = CoreRepository()
    service = MCPManagementService(core)
    try:
        removed = service.remove_server(name, workspace=workspace)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if not removed:
        raise click.ClickException(f"Server not found: {name}")
    click.echo(f"Removed: {name}")
