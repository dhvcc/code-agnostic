import json
from pathlib import Path

from code_agnostic.utils import (
    backup_file,
    compact_home_path,
    compact_home_paths_in_text,
    is_under,
    read_json_safe,
)


# --- read_json_safe ---


def test_read_json_safe_file_missing(tmp_path: Path) -> None:
    result, error = read_json_safe(tmp_path / "missing.json")

    assert result is None
    assert error is None


def test_read_json_safe_file_empty(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")

    result, error = read_json_safe(path)

    assert result is None
    assert error is None


def test_read_json_safe_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "valid.json"
    path.write_text(json.dumps({"key": "value"}), encoding="utf-8")

    result, error = read_json_safe(path)

    assert result == {"key": "value"}
    assert error is None


def test_read_json_safe_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{bad json", encoding="utf-8")

    result, error = read_json_safe(path)

    assert result is None
    assert error is not None
    assert isinstance(error, str)


# --- is_under ---


def test_is_under_path_under_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    child = root / "child" / "file.txt"

    assert is_under(child, root) is True


def test_is_under_path_not_under_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside" / "file.txt"

    assert is_under(outside, root) is False


def test_is_under_with_dotdot_resolving_under_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    tricky = root / "sub" / ".." / "other"

    assert is_under(tricky, root) is True


def test_is_under_symlink_resolving_outside(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    link.symlink_to(outside)

    assert is_under(link, root) is False


# --- backup_file ---


def test_backup_file_creates_bak_copy(tmp_path: Path) -> None:
    original = tmp_path / "config.json"
    original.write_text('{"key": "value"}', encoding="utf-8")

    backup_path = backup_file(original)

    assert backup_path.exists()
    assert ".bak-" in backup_path.name
    assert backup_path.read_text(encoding="utf-8") == '{"key": "value"}'
    assert original.exists()


def test_compact_home_path_for_absolute_home_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert compact_home_path(tmp_path / ".cursor" / "mcp.json") == "~/.cursor/mcp.json"


def test_compact_home_paths_in_text_rewrites_embedded_paths(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    message = (
        f"Skipped conflict at {tmp_path / '.cursor' / 'mcp.json'} "
        f"from {tmp_path / '.config' / 'code-agnostic' / 'config' / 'mcp.base.json'}"
    )

    result = compact_home_paths_in_text(message)

    assert "~/.cursor/mcp.json" in result
    assert "~/.config/code-agnostic/config/mcp.base.json" in result
