from pathlib import Path

from llm_sync.__main__ import cli


def test_plan_shows_invalid_json_error_for_mcp_base(minimal_shared_config: Path, common_root: Path, cli_runner) -> None:
    (common_root / "config" / "mcp.base.json").write_text("{bad", encoding="utf-8")

    result = cli_runner.invoke(cli, ["plan"])

    assert result.exit_code != 0
    assert "Invalid JSON format" in result.output
