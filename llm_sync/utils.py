import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_json_safe(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    if not path.exists():
        return None, None
    if path.stat().st_size == 0:
        return None, None
    try:
        return read_json(path), None
    except Exception as exc:
        return None, str(exc)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def backup_file(path: Path) -> Path:
    backup_path = Path(f"{path}.bak-{now_stamp()}")
    shutil.copy2(path, backup_path)
    return backup_path


def same_json(path: Path, payload: Any) -> bool:
    existing, error = read_json_safe(path)
    if error is not None:
        return False
    return existing == payload


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False
