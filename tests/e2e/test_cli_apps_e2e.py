from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "app,target,expected_action_kind",
    [
        ("opencode", "opencode", "write_json"),
        ("cursor", "cursor", "write_json"),
        ("codex", "codex", "write_text"),
    ],
)
def test_plan_then_apply_syncs_each_app_end_to_end(
    app: str,
    target: str,
    expected_action_kind: str,
    minimal_shared_config: Path,
    cli_runner,
    enable_app,
    expected_app_config_path,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app(app)

    plan_result = cli_runner.invoke(cli, ["plan", target])

    assert plan_result.exit_code == 0
    assert "plan overview" in plan_result.output
    assert expected_action_kind in plan_result.output
    assert target in plan_result.output

    apply_result = cli_runner.invoke(cli, ["apply", target])

    assert apply_result.exit_code == 0
    assert "apply" in apply_result.output
    assert expected_app_config_path(app).exists()


def test_partial_apply_codex_writes_codex_config_only(
    minimal_shared_config: Path,
    cli_runner,
    enable_app,
    expected_app_config_path,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("codex")
    enable_app("cursor")

    plan_result = cli_runner.invoke(cli, ["plan", "codex"])
    assert plan_result.exit_code == 0
    assert "plan:codex" in plan_result.output
    assert "write_text" in plan_result.output

    apply_result = cli_runner.invoke(cli, ["apply", "codex"])
    assert apply_result.exit_code == 0

    assert expected_app_config_path("codex").exists()
    assert not expected_app_config_path("cursor").exists()
