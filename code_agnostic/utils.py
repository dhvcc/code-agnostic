import json
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

from code_agnostic.constants import SYNC_LOCK_FILENAME


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Advisory inter-process lock on `path` for a read-modify-write section.

    Serializes concurrent `apply` runs so they can't race on shared state
    (`sync_state.json`). Uses `fcntl.flock` on POSIX; on platforms without it
    (e.g. Windows) it degrades to a no-op rather than failing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
    except ImportError:  # pragma: no cover - non-POSIX fallback
        yield
        return

    with path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def sync_target_lock() -> Iterator[None]:
    """Lock native client targets shared by independent source roots."""
    target_lock = Path.home() / ".cache" / "code-agnostic" / SYNC_LOCK_FILENAME
    with file_lock(target_lock):
        yield


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(rendered)


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
