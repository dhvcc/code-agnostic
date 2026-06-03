import json
import stat
from pathlib import Path

from code_agnostic.utils import (
    compact_home_path,
    compact_home_paths_in_text,
    is_under,
    read_json_safe,
    write_json,
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


def test_write_json_does_not_touch_existing_file_when_payload_is_invalid(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"existing": true}\n', encoding="utf-8")

    try:
        write_json(path, {"bad": {1, 2, 3}})
    except TypeError:
        pass
    else:  # pragma: no cover - json.dump must reject sets
        raise AssertionError("write_json unexpectedly accepted an invalid payload")

    assert path.read_text(encoding="utf-8") == '{"existing": true}\n'


def test_write_json_preserves_symlinked_destination(tmp_path: Path) -> None:
    real_target = tmp_path / "real-config.json"
    real_target.write_text('{"existing": true}\n', encoding="utf-8")
    link = tmp_path / "config.json"
    link.symlink_to(real_target)

    write_json(link, {"updated": True})

    assert link.is_symlink()
    assert link.resolve() == real_target.resolve()
    assert json.loads(real_target.read_text(encoding="utf-8")) == {"updated": True}


def test_write_json_preserves_existing_file_mode(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"existing": true}\n', encoding="utf-8")
    path.chmod(0o644)

    write_json(path, {"updated": True})

    assert stat.S_IMODE(path.stat().st_mode) == 0o644


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
