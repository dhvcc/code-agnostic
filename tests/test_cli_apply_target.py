from pathlib import Path
import functools
import json
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator
from llm_sync.__main__ import cli
from llm_sync.constants import AGENTS_FILENAME


@functools.lru_cache(maxsize=1)
def _load_opencode_schema() -> dict:
    request = Request(
        "https://opencode.ai/config.json",
        headers={"User-Agent": "Mozilla/5.0 llm-sync-tests"},
    )
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def test_apply_opencode_skips_workspace_repo_links(minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app) -> None:
    enable_app("opencode")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0

    apply_result = cli_runner.invoke(cli, ["apply", "opencode"])
    assert apply_result.exit_code == 0

    opencode_config = tmp_path / ".config" / "opencode" / "opencode.json"
    assert opencode_config.exists()

    workspace_link = workspace_root / "service-a" / AGENTS_FILENAME
    assert not workspace_link.exists()


def test_apply_default_syncs_everything(minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app) -> None:
    enable_app("opencode")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    workspace_link = workspace_root / "service-a" / AGENTS_FILENAME
    assert workspace_link.is_symlink()
    assert workspace_link.resolve() == (workspace_root / AGENTS_FILENAME).resolve()


def test_apply_generates_opencode_schema_valid_config(minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app) -> None:
    enable_app("opencode")
    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    opencode_config = tmp_path / ".config" / "opencode" / "opencode.json"
    payload = json.loads(opencode_config.read_text(encoding="utf-8"))
    schema = _load_opencode_schema()

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    assert errors == []


def test_apply_aborts_on_invalid_opencode_json(
    minimal_shared_config: Path,
    opencode_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("opencode")
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{oops", encoding="utf-8")

    result = cli_runner.invoke(cli, ["apply"])

    assert result.exit_code != 0
    assert "Apply aborted" in result.output
    assert "Invalid JSON format" in result.output
    assert "opencode" in result.output
