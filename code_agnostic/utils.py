import json
import os
import stat
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

_replace_path = os.replace


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_json_safe(path: Path) -> tuple[Any | None, str | None]:
    if not path.exists():
        return None, None
    if path.stat().st_size == 0:
        return None, None
    try:
        return read_json(path), None
    except Exception as exc:
        return None, str(exc)


def write_json(path: Path, payload: Any) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    destination = path.resolve() if path.is_symlink() else path
    if not path.is_symlink():
        destination.parent.mkdir(parents=True, exist_ok=True)

    mode = _replacement_mode(destination)
    fd, raw_temp_path = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(mode)
        _replace_path(temp_path, destination)
        _fsync_directory(destination.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _replacement_mode(destination: Path) -> int:
    if destination.exists():
        return stat.S_IMODE(destination.stat().st_mode)
    current_umask = os.umask(0)
    os.umask(current_umask)
    return 0o666 & ~current_umask


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def merge_dict_overlay(
    existing: dict[str, Any], overlay: dict[str, Any]
) -> dict[str, Any]:
    merged = deepcopy(existing)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = merge_dict_overlay(current, value)
            continue
        merged[key] = deepcopy(value)
    return merged


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def compact_home_path(path: str | Path) -> str:
    text = str(path).replace("\\", "/")
    home = str(Path.home()).replace("\\", "/")
    if text == home:
        return "~"
    home_prefix = f"{home}/"
    if text.startswith(home_prefix):
        return f"~/{text[len(home_prefix) :]}"
    return text


def compact_home_paths_in_text(text: str) -> str:
    home = str(Path.home()).replace("\\", "/")
    normalized = text.replace("\\", "/")
    if normalized == home:
        return "~"
    return normalized.replace(f"{home}/", "~/")
