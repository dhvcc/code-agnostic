import pytest

from code_agnostic.__main__ import cli


@pytest.mark.parametrize(
    ("args", "expected_name"),
    [
        (["restore", "--workspace", "missing"], "missing"),
        (["validate", "--workspace", "missing"], "missing"),
        (["explain-lossiness", "--workspace", "missing"], "missing"),
        (["rules", "list", "--workspace", "missing"], "missing"),
        (
            ["rules", "remove", "--name", "rule", "--workspace", "missing"],
            "missing",
        ),
        (["skills", "list", "--workspace", "missing"], "missing"),
        (
            ["skills", "remove", "--name", "skill", "--workspace", "missing"],
            "missing",
        ),
        (["agents", "list", "--workspace", "missing"], "missing"),
        (
            ["agents", "remove", "--name", "agent", "--workspace", "missing"],
            "missing",
        ),
    ],
)
def test_workspace_scoped_commands_reject_unknown_workspaces(
    minimal_shared_config, cli_runner, args: list[str], expected_name: str
) -> None:
    result = cli_runner.invoke(cli, args)

    assert result.exit_code != 0
    assert f"Workspace not found: {expected_name}" in result.output
