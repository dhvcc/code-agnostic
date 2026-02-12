from pathlib import Path
from typing import Any, Dict, List, Optional

from llm_sync.constants import AGENTS_FILENAME
from llm_sync.models import ActionStatus, PlanResult
from llm_sync.repositories.common import CommonRepository
from llm_sync.repositories.opencode import OpenCodeRepository
from llm_sync.utils import is_under
from llm_sync.workspaces import list_workspace_repos, resolve_workspace_rules_file


def _opencode_actions(plan: PlanResult, opencode: OpenCodeRepository) -> List[Any]:
    skills_root = opencode.skills_dir.resolve()
    agents_root = opencode.agents_dir.resolve()

    relevant = []
    for action in plan.actions:
        if action.path == opencode.config_path:
            relevant.append(action)
            continue
        if is_under(action.path, skills_root) or is_under(action.path, agents_root):
            relevant.append(action)
    return relevant


def _synced_from_actions(actions: List[Any]) -> bool:
    if not actions:
        return True
    return all(action.status == ActionStatus.NOOP for action in actions)


def build_editor_status(plan: PlanResult, opencode: OpenCodeRepository) -> List[Dict[str, str]]:
    opencode_actions = _opencode_actions(plan, opencode)
    opencode_synced = _synced_from_actions(opencode_actions)
    opencode_detail = "in sync" if opencode_synced else "out of sync"
    cursor_detail = "not managed"

    return [
        {
            "name": "opencode",
            "status": "synced" if opencode_synced else "drift",
            "detail": opencode_detail,
        },
        {
            "name": "cursor",
            "status": "disabled",
            "detail": cursor_detail,
        },
    ]


def _repo_sync_status(repo_path: Path, rules_file: Path) -> Dict[str, str]:
    target = repo_path / AGENTS_FILENAME
    desired = str(rules_file.resolve())
    if target.is_symlink() and str(target.resolve()) == desired:
        return {"repo": repo_path.name, "status": "synced", "detail": "linked"}
    return {"repo": repo_path.name, "status": "needs_sync", "detail": f"missing or mismatched {AGENTS_FILENAME}"}


def build_workspace_status(common: CommonRepository) -> List[Dict[str, Any]]:
    status_rows: List[Dict[str, Any]] = []

    for workspace in common.load_workspaces():
        workspace_path = Path(workspace["path"])
        row: Dict[str, Any] = {
            "name": workspace["name"],
            "path": str(workspace_path),
            "status": "synced",
            "detail": "all git repos synced",
            "repos": [],
        }

        if not workspace_path.exists() or not workspace_path.is_dir():
            row["status"] = "error"
            row["detail"] = "workspace path missing"
            status_rows.append(row)
            continue

        rules_file: Optional[Path] = resolve_workspace_rules_file(workspace_path)
        if rules_file is None:
            row["status"] = "error"
            row["detail"] = "no workspace rules file"
            status_rows.append(row)
            continue

        repos = list_workspace_repos(workspace_path)
        repo_rows = [_repo_sync_status(repo, rules_file) for repo in repos]
        row["repos"] = repo_rows

        if not repos:
            row["detail"] = "no git repos found"
        elif any(item["status"] != "synced" for item in repo_rows):
            row["status"] = "drift"
            row["detail"] = "one or more repos need sync"

        status_rows.append(row)

    return status_rows
