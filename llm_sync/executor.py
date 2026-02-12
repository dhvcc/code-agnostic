import os
from datetime import datetime
from pathlib import Path

from llm_sync.models import PlanResult
from llm_sync.repositories.common import CommonRepository
from llm_sync.repositories.opencode import OpenCodeRepository
from llm_sync.utils import backup_file, write_json
from llm_sync.workspaces import list_workspace_repos, resolve_workspace_rules_file


def _collect_managed_links(target_root: Path, source_root: Path) -> list[str]:
    if not target_root.exists():
        return []

    managed: list[str] = []
    for child in target_root.iterdir():
        if not child.is_symlink():
            continue
        target = os.path.realpath(child)
        if target.startswith(str(source_root.resolve())):
            managed.append(str(child))
    return managed


def _collect_workspace_links(common: CommonRepository) -> list[str]:
    managed: list[str] = []
    for workspace in common.load_workspaces():
        workspace_path = Path(workspace["path"])
        if not workspace_path.exists() or not workspace_path.is_dir():
            continue
        rules_file = resolve_workspace_rules_file(workspace_path)
        if rules_file is None:
            continue
        rules_target = str(rules_file.resolve())
        for repo in list_workspace_repos(workspace_path):
            target = repo / "AGENTS.md"
            if not target.is_symlink():
                continue
            if os.path.realpath(target) == rules_target:
                managed.append(str(target))
    return managed


def execute_apply(plan: PlanResult, common: CommonRepository, opencode: OpenCodeRepository) -> tuple[int, int, list[str]]:
    applied = 0
    failed = 0
    failures: list[str] = []

    for action in plan.actions:
        try:
            if action.kind == "write_json":
                if action.status == "noop":
                    continue
                if action.path.exists():
                    backup_file(action.path)
                write_json(action.path, action.payload)
                applied += 1
                continue

            if action.kind == "symlink":
                if action.status == "noop":
                    continue
                if action.status == "conflict":
                    failed += 1
                    failures.append(f"Conflict (not overwritten): {action.path}")
                    continue
                if action.source is None:
                    failed += 1
                    failures.append(f"Missing source for symlink action: {action.path}")
                    continue
                action.path.parent.mkdir(parents=True, exist_ok=True)
                if action.path.exists() or action.path.is_symlink():
                    action.path.unlink()
                action.path.symlink_to(action.source.resolve())
                applied += 1
                continue

            if action.kind == "remove_symlink":
                if action.status == "noop":
                    continue
                if action.status == "conflict":
                    failed += 1
                    failures.append(f"Stale cleanup conflict (not symlink): {action.path}")
                    continue
                if action.path.is_symlink():
                    action.path.unlink()
                    applied += 1
                continue

            failed += 1
            failures.append(f"Unknown action kind: {action.kind}")
        except Exception as exc:
            failed += 1
            failures.append(f"{action.kind} failed for {action.path}: {exc}")

    managed_skill_links = _collect_managed_links(opencode.skills_dir, common.skills_dir)
    managed_agent_links = _collect_managed_links(opencode.agents_dir, common.agents_dir)
    managed_workspace_links = _collect_workspace_links(common)

    state = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "managed_skill_links": sorted(set(managed_skill_links)),
        "managed_agent_links": sorted(set(managed_agent_links)),
        "managed_workspace_links": sorted(set(managed_workspace_links)),
        "skipped": plan.skipped,
    }
    common.save_state(state)

    summary_lines = [
        "# LLM Sync State",
        "",
        f"- Updated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Applied changes: {applied}",
        f"- Failed changes: {failed}",
        f"- Managed skill links: {len(set(managed_skill_links))}",
        f"- Managed agent links: {len(set(managed_agent_links))}",
        f"- Managed workspace links: {len(set(managed_workspace_links))}",
    ]
    if failures:
        summary_lines.extend(["", "## Failures"])
        summary_lines.extend([f"- {item}" for item in failures])
    common.state_md.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    return applied, failed, failures
