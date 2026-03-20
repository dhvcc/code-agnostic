"""CLI entrypoint - thin wrapper that wires command modules."""

import click

from code_agnostic.cli import AliasedGroup
from code_agnostic.cli.commands.agents import agents_group
from code_agnostic.cli.commands.apps import apps
from code_agnostic.cli.commands.apply import apply
from code_agnostic.cli.commands.explain_lossiness import explain_lossiness
from code_agnostic.cli.commands.import_ import import_group
from code_agnostic.cli.commands.mcp import mcp
from code_agnostic.cli.commands.plan import plan
from code_agnostic.cli.commands.restore import restore
from code_agnostic.cli.commands.rules import rules
from code_agnostic.cli.commands.skills import skills
from code_agnostic.cli.commands.status import status
from code_agnostic.cli.commands.validate import validate
from code_agnostic.cli.commands.workspaces import workspaces


@click.group(
    cls=AliasedGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """App-based config sync."""
    ctx.obj = {}


# Register individual commands
cli.add_command(plan)
cli.add_command(apply)
cli.add_command(restore)
cli.add_command(status)
cli.add_command(validate)
cli.add_command(explain_lossiness)

# Register command groups
cli.add_command(apps)
cli.add_command(workspaces)
cli.add_command(rules)
cli.add_command(skills)
cli.add_command(agents_group)
cli.add_command(mcp)
cli.add_command(import_group)


def main() -> int:
    try:
        cli(standalone_mode=False)
    except click.exceptions.Exit as exc:
        code = exc.exit_code
        return code if isinstance(code, int) else 1
    except click.ClickException as exc:
        exc.show()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
