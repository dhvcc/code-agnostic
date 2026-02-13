import sys
import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner
import pytest


def _ensure_repo_on_path() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_on_path()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


@pytest.fixture
def write_json():
    def _write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    return _write


@pytest.fixture
def common_root(tmp_path: Path) -> Path:
    return tmp_path / ".config" / "code-agnostic"


@pytest.fixture
def opencode_root(tmp_path: Path) -> Path:
    return tmp_path / ".config" / "opencode"


@pytest.fixture
def minimal_shared_config(common_root: Path, write_json) -> Path:
    write_json(common_root / "config" / "mcp.base.json", {"mcpServers": {}})
    write_json(
        common_root / "config" / "opencode.base.json",
        {"$schema": "https://opencode.ai/config.json"},
    )
    return common_root


@pytest.fixture
def cli_runner(tmp_path: Path) -> CliRunner:
    class HomeCliRunner(CliRunner):
        def invoke(self, cli: Any, args: Any = None, **kwargs: Any):  # type: ignore[override]
            env = dict(kwargs.pop("env", {}) or {})
            env.setdefault("HOME", str(tmp_path))
            env.setdefault("XDG_CONFIG_HOME", str(tmp_path / ".config"))
            kwargs["env"] = env
            return super().invoke(cli, args=args, **kwargs)

    return HomeCliRunner()


@pytest.fixture
def enable_app(cli_runner):
    from code_agnostic.__main__ import cli

    def _enable(app: str) -> None:
        result = cli_runner.invoke(cli, ["apps", "enable", app])
        assert result.exit_code == 0

    return _enable
