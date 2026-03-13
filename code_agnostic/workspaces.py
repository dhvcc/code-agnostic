import os
from pathlib import Path

from code_agnostic.constants import (
    GIT_DIRNAME,
    WORKSPACE_IGNORED_DIRS,
)


class WorkspaceService:
    def resolve_git_dir(self, repo_path: Path) -> Path | None:
        git_entry = repo_path / GIT_DIRNAME
        if git_entry.is_dir():
            return git_entry
        if not git_entry.is_file():
            return None

        first_line = git_entry.read_text(encoding="utf-8").splitlines()
        if not first_line:
            return None
        prefix, _, raw_path = first_line[0].partition(":")
        if prefix.strip().lower() != "gitdir":
            return None

        raw_path = raw_path.strip()
        if not raw_path:
            return None
        git_dir = Path(raw_path)
        if not git_dir.is_absolute():
            git_dir = (repo_path / git_dir).resolve()
        return git_dir

    def discover_git_repos(self, workspace_path: Path) -> list[Path]:
        repos: list[Path] = []
        workspace_real = workspace_path.resolve()

        for root, dir_names, _ in os.walk(str(workspace_real), topdown=True):
            current = Path(root)
            if current == workspace_real:
                pass
            elif self.resolve_git_dir(current) is not None:
                repos.append(current)
                dir_names[:] = []
                continue

            dir_names[:] = [
                name
                for name in dir_names
                if not name.startswith(".") and name not in WORKSPACE_IGNORED_DIRS
            ]

        return sorted(set(repos))
