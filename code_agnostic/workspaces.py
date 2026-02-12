import os
from pathlib import Path
from typing import Optional

from code_agnostic.constants import AGENTS_FILENAME, GIT_DIRNAME, WORKSPACE_IGNORED_DIRS, WORKSPACE_RULE_FILES


class WorkspaceService:
    def resolve_rules_file(self, workspace_path: Path) -> Optional[Path]:
        for candidate in WORKSPACE_RULE_FILES:
            rule_path = workspace_path / candidate
            if rule_path.exists() and rule_path.is_file():
                return rule_path
        return None


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

            dir_names[:] = [name for name in dir_names if not name.startswith(".") and name not in WORKSPACE_IGNORED_DIRS]

        return sorted(set(repos))

    def workspace_sync_targets(self, workspace_path: Path, rules_file: Optional[Path]) -> list[Path]:
        if rules_file is None:
            return []
        return [repo / AGENTS_FILENAME for repo in self.discover_git_repos(workspace_path)]


def resolve_workspace_rules_file(workspace_path: Path) -> Optional[Path]:
    return WorkspaceService().resolve_rules_file(workspace_path)


def list_workspace_repos(workspace_path: Path) -> list[Path]:
    return WorkspaceService().discover_git_repos(workspace_path)
