"""CLI group aliases for singular/plural command groups."""

import click


class AliasedGroup(click.Group):
    """Click group that resolves singular aliases to plural command names."""

    ALIASES: dict[str, str] = {
        "app": "apps",
        "workspace": "workspaces",
    }

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        return super().get_command(ctx, self.ALIASES.get(cmd_name, cmd_name))

    def resolve_command(self, ctx: click.Context, args: list[str]):
        if args and args[0] in self.ALIASES:
            args[0] = self.ALIASES[args[0]]
        return super().resolve_command(ctx, args)
