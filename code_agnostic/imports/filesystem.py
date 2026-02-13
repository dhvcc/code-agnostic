import filecmp
import shutil
from pathlib import Path


def is_entry_symlink(entry: Path) -> bool:
    return entry.is_symlink()


def tree_contains_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    if path.is_file():
        return False
    for child in path.rglob("*"):
        if child.is_symlink():
            return True
    return False


def content_equal(source: Path, target: Path) -> bool:
    if source.is_file() and target.is_file():
        return filecmp.cmp(source, target, shallow=False)
    if source.is_dir() and target.is_dir():
        return _dir_content_equal(source, target)
    return False


def copy_path(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)


def _dir_content_equal(source: Path, target: Path) -> bool:
    left = sorted(_dir_entries(source))
    right = sorted(_dir_entries(target))
    if left != right:
        return False
    for relative in left:
        left_path = source / relative
        right_path = target / relative
        if left_path.is_file() and right_path.is_file():
            if not filecmp.cmp(left_path, right_path, shallow=False):
                return False
            continue
        if left_path.is_dir() and right_path.is_dir():
            continue
        return False
    return True


def _dir_entries(root: Path) -> list[str]:
    result: list[str] = []
    for child in root.rglob("*"):
        relative = child.relative_to(root)
        suffix = "/" if child.is_dir() else ""
        result.append(str(relative) + suffix)
    return result
