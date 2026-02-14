import os
from pathlib import Path

from code_agnostic.constants import (
    GIT_DIRNAME,
    WORKSPACE_IGNORED_DIRS,
)


class WorkspaceService:
    def discover_git_repos(self, workspace_path: Path) -> list[Path]:
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

            dir_names[:] = [
                name
                for name in dir_names
                if not name.startswith(".") and name not in WORKSPACE_IGNORED_DIRS
            ]

        return sorted(set(repos))
