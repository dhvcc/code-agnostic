import json
from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.constants import AGENTS_FILENAME
from code_agnostic.core.repository import CoreRepository


def test_projects_add_list_remove_commands(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    project_root = tmp_path / "example-project"
    project_root.mkdir()
    (project_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")

    add_result = cli_runner.invoke(
        cli,
        [
            "projects",
            "add",
            "--name",
            "project-example",
            "--path",
            str(project_root),
        ],
    )
    assert add_result.exit_code == 0
    assert "Project added: project-example" in add_result.output

    registry = minimal_shared_config / "config" / "projects.json"
    assert json.loads(registry.read_text(encoding="utf-8")) == [
        {"name": "project-example", "path": str(project_root.resolve())}
    ]
    assert (minimal_shared_config / "projects" / "project-example").is_dir()

    list_result = cli_runner.invoke(cli, ["projects", "list"])
    assert list_result.exit_code == 0
    assert "project-example" in list_result.output
    assert str(project_root.resolve()) in list_result.output

    remove_result = cli_runner.invoke(
        cli, ["projects", "remove", "--name", "project-example"]
    )
    assert remove_result.exit_code == 0
    assert "Project unregistered: project-example" in remove_result.output

    list_after_remove = cli_runner.invoke(cli, ["projects", "list"])
    assert list_after_remove.exit_code == 0
    assert "No projects configured" in list_after_remove.output
    assert "code-agnostic projects add --name <name> --path <path>" in (
        list_after_remove.output
    )
    assert (minimal_shared_config / "projects" / "project-example").is_dir()


def test_project_config_dir_uses_project_source_root(core_root: Path) -> None:
    assert CoreRepository(core_root).project_config_dir("demo") == (
        core_root / "projects" / "demo"
    )


def test_projects_add_rejects_missing_path(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    missing_path = tmp_path / "does-not-exist"

    result = cli_runner.invoke(
        cli, ["projects", "add", "--name", "broken", "--path", str(missing_path)]
    )

    assert result.exit_code != 0
    assert "does not exist or is not a directory" in result.output


def test_projects_add_empty_name(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()

    result = cli_runner.invoke(
        cli, ["projects", "add", "--name", "", "--path", str(project_root)]
    )

    assert result.exit_code != 0
    assert "empty" in result.output.lower()


def test_projects_add_rejects_path_like_name_before_writes(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    registry = minimal_shared_config / "config" / "projects.json"
    victim = minimal_shared_config.parent / "victim"

    result = cli_runner.invoke(
        cli,
        [
            "projects",
            "add",
            "--name",
            "../../victim",
            "--path",
            str(project_root),
        ],
    )

    assert result.exit_code != 0
    assert "Invalid project name: ../../victim" in result.output
    assert not registry.exists()
    assert not victim.exists()


def test_projects_add_duplicate_name(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    project_one = tmp_path / "project-one"
    project_one.mkdir()
    project_two = tmp_path / "project-two"
    project_two.mkdir()

    add_result = cli_runner.invoke(
        cli, ["projects", "add", "--name", "demo", "--path", str(project_one)]
    )
    assert add_result.exit_code == 0

    dup_result = cli_runner.invoke(
        cli, ["projects", "add", "--name", "demo", "--path", str(project_two)]
    )
    assert dup_result.exit_code != 0
    assert "already exists" in dup_result.output


def test_projects_add_duplicate_path(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()

    add_result = cli_runner.invoke(
        cli, ["projects", "add", "--name", "first", "--path", str(project_root)]
    )
    assert add_result.exit_code == 0

    dup_result = cli_runner.invoke(
        cli, ["projects", "add", "--name", "second", "--path", str(project_root)]
    )
    assert dup_result.exit_code != 0
    assert "already exists" in dup_result.output


def test_projects_add_preserves_corrupted_registry(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    registry = minimal_shared_config / "config" / "projects.json"
    registry.write_text("{bad", encoding="utf-8")

    result = cli_runner.invoke(
        cli, ["projects", "add", "--name", "new", "--path", str(project_root)]
    )

    assert result.exit_code != 0
    assert "Invalid JSON format" in result.output
    assert registry.read_text(encoding="utf-8") == "{bad"


def test_projects_list_reports_corrupted_registry(
    minimal_shared_config: Path, cli_runner
) -> None:
    registry = minimal_shared_config / "config" / "projects.json"
    registry.write_text("{bad", encoding="utf-8")

    result = cli_runner.invoke(cli, ["projects", "list"])

    assert result.exit_code != 0
    assert "Invalid JSON format" in result.output
    assert registry.read_text(encoding="utf-8") == "{bad"


def test_projects_remove_reports_corrupted_registry(
    minimal_shared_config: Path, cli_runner
) -> None:
    registry = minimal_shared_config / "config" / "projects.json"
    registry.write_text("{bad", encoding="utf-8")

    result = cli_runner.invoke(cli, ["projects", "remove", "--name", "old"])

    assert result.exit_code != 0
    assert "Invalid JSON format" in result.output
    assert registry.read_text(encoding="utf-8") == "{bad"


def test_projects_list_rejects_invalid_registry_without_rewrite(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    registry = minimal_shared_config / "config" / "projects.json"
    payload = [
        {"name": "demo", "path": str(project_root)},
        {"name": "demo", "path": str(project_root)},
    ]
    registry_text = json.dumps(payload)
    registry.write_text(registry_text, encoding="utf-8")

    result = cli_runner.invoke(cli, ["projects", "list"])

    assert result.exit_code != 0
    assert "duplicate project name" in result.output
    assert registry.read_text(encoding="utf-8") == registry_text


def test_projects_list_allows_registry_with_missing_path(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    registry = minimal_shared_config / "config" / "projects.json"
    missing_path = tmp_path / "missing"
    registry_text = json.dumps([{"name": "missing", "path": str(missing_path)}])
    registry.write_text(registry_text, encoding="utf-8")

    result = cli_runner.invoke(cli, ["projects", "list"])

    assert result.exit_code == 0
    assert "missing" in result.output
    assert str(missing_path.resolve()) in result.output
    assert registry.read_text(encoding="utf-8") == registry_text


def test_projects_remove_allows_registry_with_missing_path(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    registry = minimal_shared_config / "config" / "projects.json"
    missing_path = tmp_path / "missing"
    registry.write_text(
        json.dumps([{"name": "missing", "path": str(missing_path)}]),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["projects", "remove", "--name", "missing"])

    assert result.exit_code == 0
    assert "Project unregistered: missing" in result.output
    assert json.loads(registry.read_text(encoding="utf-8")) == []


def test_projects_remove_nonexistent(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["projects", "remove", "--name", "ghost"])

    assert result.exit_code != 0
    assert "Project not found" in result.output
