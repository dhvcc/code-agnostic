import os
from pathlib import Path
from typing import Optional

from llm_sync.constants import GIT_DIRNAME, WORKSPACE_IGNORED_DIRS, WORKSPACE_RULE_FILES


def resolve_workspace_rules_file(workspace_path: Path) -> Optional[Path]:
    for candidate in WORKSPACE_RULE_FILES:
        rule_path = workspace_path / candidate
        if rule_path.exists() and rule_path.is_file():
            return rule_path
    return None


def list_workspace_repos(workspace_path: Path) -> list[Path]:
    repos: list[Path] = []
    workspace_real = workspace_path.resolve()

    for root, dir_names, _ in os.walk(str(workspace_real), topdown=True):
        current = Path(root)
        if current == workspace_real:
            pass
        elif (current / GIT_DIRNAME).exists():
            repos.append(current)
            dir_names[:] = []
            continue

        dir_names[:] = [name for name in dir_names if not name.startswith(".") and name not in WORKSPACE_IGNORED_DIRS]

    return sorted(set(repos))
