"""Tests for CLI module organization.

These tests protect the CLI import structure and module organization.
They ensure the refactor maintains backward compatibility.
"""

from code_agnostic.__main__ import cli


def test_cli_importable_from_main(cli_runner) -> None:
    """CLI should be importable from code_agnostic.__main__."""
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "App-based config sync" in result.output


def test_cli_group_importable_from_cli_package() -> None:
    """AliasedGroup should be importable from code_agnostic.cli."""
    from code_agnostic.cli import AliasedGroup

    assert AliasedGroup is not None


def test_cli_has_all_expected_commands(cli_runner) -> None:
    """All expected commands should be registered."""
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0

    # Root commands
    assert "plan" in result.output
    assert "apply" in result.output
    assert "status" in result.output
    assert "restore" in result.output
    assert "validate" in result.output
    assert "explain-lossiness" in result.output

    # Groups
    assert "apps" in result.output
    assert "workspaces" in result.output
    assert "rules" in result.output
    assert "skills" in result.output
    assert "agents" in result.output
    assert "mcp" in result.output
    assert "import" in result.output


def test_cli_aliases_work(cli_runner) -> None:
    """Singular aliases should resolve to plural groups."""
    # 'app' should resolve to 'apps'
    app_result = cli_runner.invoke(cli, ["app", "--help"])
    assert app_result.exit_code == 0

    # 'workspace' should resolve to 'workspaces'
    ws_result = cli_runner.invoke(cli, ["workspace", "--help"])
    assert ws_result.exit_code == 0
