from pathlib import Path

from click.testing import CliRunner
import pytest

from code_agnostic.__main__ import cli
from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError
from code_agnostic.models import ActionKind, ActionStatus
from code_agnostic.planner import SyncPlanner
from code_agnostic.repositories.common import CommonRepository
from code_agnostic.repositories.opencode import OpenCodeRepository


def test_plan_config_create_when_missing(minimal_shared_config: Path, common_root: Path, opencode_root: Path) -> None:
    plan = SyncPlanner(common=CommonRepository(common_root), opencode=OpenCodeRepository(opencode_root)).build()

    config_actions = [a for a in plan.actions if a.kind == ActionKind.WRITE_JSON]
    assert len(config_actions) == 1
    assert config_actions[0].status == ActionStatus.CREATE


def test_plan_config_update_when_existing_but_different(
    minimal_shared_config: Path,
    common_root: Path,
    opencode_root: Path,
) -> None:
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}\n", encoding="utf-8")

    plan = SyncPlanner(common=CommonRepository(common_root), opencode=OpenCodeRepository(opencode_root)).build()

    config_actions = [a for a in plan.actions if a.kind == ActionKind.WRITE_JSON]
    assert len(config_actions) == 1
    assert config_actions[0].status == ActionStatus.UPDATE


def test_plan_config_noop_when_already_synced(
    minimal_shared_config: Path,
    common_root: Path,
    opencode_root: Path,
) -> None:
    common = CommonRepository(common_root)
    opencode = OpenCodeRepository(opencode_root)
    first_plan = SyncPlanner(common=common, opencode=opencode).build()
    payload = next(a.payload for a in first_plan.actions if a.kind == ActionKind.WRITE_JSON)

    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    second_plan = SyncPlanner(common=common, opencode=opencode).build()
    config_actions = [a for a in second_plan.actions if a.kind == ActionKind.WRITE_JSON]
    assert len(config_actions) == 1
    assert config_actions[0].status == ActionStatus.NOOP


def test_plan_collects_invalid_opencode_json_as_error(
    minimal_shared_config: Path,
    common_root: Path,
    opencode_root: Path,
) -> None:
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{not-json", encoding="utf-8")

    plan = SyncPlanner(common=CommonRepository(common_root), opencode=OpenCodeRepository(opencode_root)).build()

    assert len(plan.errors) == 1
    assert isinstance(plan.errors[0], InvalidJsonFormatError)
    assert str(config_path) in str(plan.errors[0])


def test_plan_treats_empty_opencode_config_as_update(
    minimal_shared_config: Path,
    common_root: Path,
    opencode_root: Path,
) -> None:
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("", encoding="utf-8")

    plan = SyncPlanner(common=CommonRepository(common_root), opencode=OpenCodeRepository(opencode_root)).build()

    config_actions = [a for a in plan.actions if a.kind == ActionKind.WRITE_JSON]
    assert len(config_actions) == 1
    assert config_actions[0].status == ActionStatus.UPDATE


def test_invalid_mcp_base_json_raises_custom_error(common_root: Path) -> None:
    config_dir = common_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "mcp.base.json").write_text("{bad", encoding="utf-8")
    (config_dir / "opencode.base.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(InvalidJsonFormatError):
        CommonRepository(common_root).load_mcp_base()


def test_invalid_mcp_base_schema_raises_custom_error(common_root: Path) -> None:
    config_dir = common_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "mcp.base.json").write_text("{}\n", encoding="utf-8")
    (config_dir / "opencode.base.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(InvalidConfigSchemaError):
        CommonRepository(common_root).load_mcp_base()


def test_cli_plan_shows_invalid_json_path(minimal_shared_config: Path, common_root: Path) -> None:
    runner = CliRunner()
    (common_root / "config" / "mcp.base.json").write_text("{bad", encoding="utf-8")

    result = runner.invoke(cli, ["plan"])

    assert result.exit_code != 0
    assert "Invalid JSON format" in result.output


def test_cli_apply_aborts_on_invalid_opencode_json(
    minimal_shared_config: Path,
    opencode_root: Path,
) -> None:
    runner = CliRunner()
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{oops", encoding="utf-8")

    result = runner.invoke(cli, ["apply"])

    assert result.exit_code != 0
    assert "Apply aborted" in result.output
    assert "Invalid JSON format" in result.output
    assert "opencode" in result.output


def test_cli_workspace_add_rejects_missing_path(minimal_shared_config: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    missing_path = tmp_path / "does-not-exist"

    result = runner.invoke(cli, ["workspaces", "add", "broken", str(missing_path)])

    assert result.exit_code != 0
    assert "does not exist or is not a directory" in result.output
