from llm_sync.__main__ import cli


def test_apps_list_shows_all_disabled_by_default(minimal_shared_config, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["apps", "list"])

    assert result.exit_code == 0
    assert "opencode" in result.output
    assert "cursor" in result.output
    assert "disabled" in result.output


def test_apps_enable_and_disable_updates_state(minimal_shared_config, cli_runner) -> None:
    enable_result = cli_runner.invoke(cli, ["apps", "enable", "opencode"])
    assert enable_result.exit_code == 0

    list_after_enable = cli_runner.invoke(cli, ["apps", "list"])
    assert list_after_enable.exit_code == 0
    assert "opencode" in list_after_enable.output
    assert "enabled" in list_after_enable.output

    disable_result = cli_runner.invoke(cli, ["apps", "disable", "opencode"])
    assert disable_result.exit_code == 0

    list_after_disable = cli_runner.invoke(cli, ["apps", "list"])
    assert list_after_disable.exit_code == 0
    assert "opencode" in list_after_disable.output
    assert "disabled" in list_after_disable.output


def test_apply_skips_when_no_apps_enabled(minimal_shared_config, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["apply"])

    assert result.exit_code == 0
    assert "No apps enabled" in result.output


def test_apply_reports_enabled_but_not_implemented_apps(minimal_shared_config, cli_runner) -> None:
    enable_cursor = cli_runner.invoke(cli, ["apps", "enable", "cursor"])
    assert enable_cursor.exit_code == 0

    result = cli_runner.invoke(cli, ["apply"])

    assert result.exit_code == 0
    assert "not implemented" in result.output
    assert "cursor" in result.output


def test_status_reports_cursor_enabled_but_not_implemented(minimal_shared_config, cli_runner) -> None:
    enable_cursor = cli_runner.invoke(cli, ["apps", "enable", "cursor"])
    assert enable_cursor.exit_code == 0

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "cursor" in result.output
    assert "enabled but sync is not implemented yet" in result.output
