from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from code_agnostic.agents.claude import claude_agent_target_path
from code_agnostic.agents.codex import normalize_codex_agent_filename
from code_agnostic.agents.copilot import copilot_agent_filename
from code_agnostic.agents.models import Agent, AgentMetadata
from code_agnostic.agents.parser import parse_agent
from code_agnostic.apps.app_id import AppId
from code_agnostic.constants import (
    AGENTS_DIRNAME,
    AGENTS_FILENAME,
    AGENTS_PROJECT_DIRNAME,
    CLAUDE_LOCAL_FILENAME,
    CLAUDE_PROJECT_DIRNAME,
    CODEX_AGENTS_OVERRIDE_FILENAME,
    CODEX_CONFIG_FILENAME,
    CODEX_PROJECT_DIRNAME,
    COPILOT_PROJECT_CONFIG_FILENAME,
    COPILOT_PROJECT_DIRNAME,
    CURSOR_CONFIG_FILENAME,
    CURSOR_PROJECT_DIRNAME,
    OPENCODE_CONFIG_FILENAME,
    OPENCODE_PROJECT_DIRNAME,
    SKILLS_DIRNAME,
)
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository


@dataclass(frozen=True)
class WorkspaceArtifactPath:
    relative_path: Path
    app_id: AppId | None
    scope: str
    label: str


def git_exclude_entries_for_repo(
    ws_source: WorkspaceConfigRepository,
    app_ids: list[AppId],
    *,
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
) -> list[str]:
    entries = [
        item.relative_path.as_posix()
        for item in repo_artifact_paths(
            ws_source,
            app_ids,
            workspace_path=workspace_path,
            repo_path=repo_path,
            include_workspace_root_rules=True,
        )
    ]
    return sorted(dict.fromkeys(entries))


def repo_artifact_paths(
    ws_source: WorkspaceConfigRepository,
    app_ids: list[AppId],
    *,
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
    include_workspace_root_rules: bool = False,
) -> list[WorkspaceArtifactPath]:
    artifacts: list[WorkspaceArtifactPath] = []
    if (
        include_workspace_root_rules
        and ws_source.has_rules()
        and (repo_path is None or workspace_path is None or repo_path == workspace_path)
    ):
        artifacts.append(
            WorkspaceArtifactPath(
                relative_path=Path(AGENTS_FILENAME),
                app_id=None,
                scope="rules",
                label="workspace rules",
            )
        )

    for app_id in app_ids:
        artifacts.extend(_repo_artifact_paths_for_app(ws_source, app_id, repo_path))
    return artifacts


def _repo_artifact_paths_for_app(
    ws_source: WorkspaceConfigRepository,
    app_id: AppId,
    repo_path: Path | None,
) -> list[WorkspaceArtifactPath]:
    artifacts: list[WorkspaceArtifactPath] = []
    config_path = _repo_config_path(ws_source, app_id)
    if config_path is not None:
        artifacts.append(
            WorkspaceArtifactPath(
                relative_path=config_path,
                app_id=app_id,
                scope=f"ws:{app_id.value}:repo_mcp",
                label=f"{app_id.value} config",
            )
        )

    if ws_source.has_rules():
        rules_path = _repo_rules_path(app_id)
        if rules_path is not None:
            artifacts.append(
                WorkspaceArtifactPath(
                    relative_path=rules_path,
                    app_id=app_id,
                    scope=f"ws:{app_id.value}:repo_rules",
                    label=f"{app_id.value} rules",
                )
            )

    for source in ws_source.list_skill_sources():
        artifacts.append(
            WorkspaceArtifactPath(
                relative_path=_skill_path(app_id, source),
                app_id=app_id,
                scope=f"ws:{app_id.value}:repo_skills_dir",
                label=f"{app_id.value} skills",
            )
        )

    for source in ws_source.list_agent_sources():
        artifacts.append(
            WorkspaceArtifactPath(
                relative_path=_agent_path(app_id, source, repo_path),
                app_id=app_id,
                scope=f"ws:{app_id.value}:repo_agents_dir",
                label=f"{app_id.value} agents",
            )
        )
    return artifacts


def _repo_config_path(
    ws_source: WorkspaceConfigRepository,
    app_id: AppId,
) -> Path | None:
    if app_id == AppId.CLAUDE:
        return None
    if app_id == AppId.CURSOR:
        return (
            Path(CURSOR_PROJECT_DIRNAME) / CURSOR_CONFIG_FILENAME
            if ws_source.has_mcp()
            else None
        )
    if app_id == AppId.OPENCODE:
        if ws_source.has_mcp() or ws_source.has_rules():
            return Path(OPENCODE_CONFIG_FILENAME)
        return None
    if app_id == AppId.CODEX:
        if (
            ws_source.has_mcp()
            or ws_source.has_agents()
            or ws_source.codex_base_path.exists()
        ):
            return Path(CODEX_PROJECT_DIRNAME) / CODEX_CONFIG_FILENAME
    if app_id == AppId.COPILOT:
        return (
            Path(COPILOT_PROJECT_DIRNAME) / COPILOT_PROJECT_CONFIG_FILENAME
            if ws_source.has_mcp()
            else None
        )
    return None


def _repo_rules_path(app_id: AppId) -> Path | None:
    if app_id == AppId.CODEX:
        return Path(CODEX_AGENTS_OVERRIDE_FILENAME)
    if app_id == AppId.CLAUDE:
        return Path(CLAUDE_LOCAL_FILENAME)
    return None


def _skill_path(app_id: AppId, source: Path) -> Path:
    if app_id == AppId.CODEX:
        return Path(AGENTS_PROJECT_DIRNAME) / SKILLS_DIRNAME / source.name / "SKILL.md"
    project_dir = _project_dir_name(app_id)
    return Path(project_dir) / SKILLS_DIRNAME / source.name / "SKILL.md"


def _agent_path(app_id: AppId, source: Path, repo_path: Path | None) -> Path:
    if app_id == AppId.CODEX:
        agent = _parse_agent_or_fallback(source)
        target_name = normalize_codex_agent_filename(
            agent.metadata.name,
            agent.name,
        )
        return Path(CODEX_PROJECT_DIRNAME) / AGENTS_DIRNAME / f"{target_name}.toml"
    if app_id == AppId.CLAUDE:
        return claude_agent_target_path(
            Path(CLAUDE_PROJECT_DIRNAME) / AGENTS_DIRNAME,
            _parse_agent_or_fallback(source),
        )
    if app_id == AppId.OPENCODE:
        return _opencode_agent_dir(repo_path) / (
            f"{source.name}.md" if source.is_dir() else source.name
        )
    if app_id == AppId.CURSOR:
        return (
            Path(CURSOR_PROJECT_DIRNAME)
            / AGENTS_DIRNAME
            / (source.name if source.is_file() else f"{source.name}.md")
        )
    if app_id == AppId.COPILOT:
        return (
            Path(COPILOT_PROJECT_DIRNAME)
            / AGENTS_DIRNAME
            / copilot_agent_filename(source)
        )
    raise ValueError(f"Unsupported app for workspace agent artifact: {app_id.value}")


def _opencode_agent_dir(repo_path: Path | None) -> Path:
    base = Path(OPENCODE_PROJECT_DIRNAME)
    if repo_path is None:
        return base / AGENTS_DIRNAME
    plural = repo_path / OPENCODE_PROJECT_DIRNAME / AGENTS_DIRNAME
    singular = repo_path / OPENCODE_PROJECT_DIRNAME / "agent"
    if plural.exists():
        return base / AGENTS_DIRNAME
    if singular.exists():
        return base / "agent"
    return base / AGENTS_DIRNAME


def _project_dir_name(app_id: AppId) -> str:
    if app_id == AppId.OPENCODE:
        return OPENCODE_PROJECT_DIRNAME
    if app_id == AppId.CURSOR:
        return CURSOR_PROJECT_DIRNAME
    if app_id == AppId.CODEX:
        return CODEX_PROJECT_DIRNAME
    if app_id == AppId.CLAUDE:
        return CLAUDE_PROJECT_DIRNAME
    if app_id == AppId.COPILOT:
        return COPILOT_PROJECT_DIRNAME
    raise ValueError(f"Unsupported app for workspace artifact: {app_id.value}")


def _parse_agent_or_fallback(source: Path) -> Agent:
    try:
        return parse_agent(source)
    except Exception:
        name = source.name if source.is_dir() else source.stem
        return Agent(
            name=name,
            source_path=source,
            metadata=AgentMetadata(name=name),
            content="",
        )
