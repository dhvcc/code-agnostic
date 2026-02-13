from pathlib import Path

from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.apps.common.utils import common_mcp_to_dto, dto_to_common_mcp
from code_agnostic.core.repository import CoreRepository
from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError
from code_agnostic.imports.adapters import create_import_adapter
from code_agnostic.imports.filesystem import (
    content_equal,
    copy_path,
    is_entry_symlink,
    remove_path,
    tree_contains_symlink,
)
from code_agnostic.imports.models import (
    ConflictPolicy,
    ImportAction,
    ImportActionKind,
    ImportActionStatus,
    ImportApplyResult,
    ImportPlan,
    ImportSection,
)
from code_agnostic.utils import read_json_safe, write_json


class ImportService:
    def __init__(self, core_repository: CoreRepository | None = None) -> None:
        self._core = core_repository or CoreRepository()

    def plan(
        self,
        source_app: str,
        include: list[ImportSection] | None = None,
        exclude: list[ImportSection] | None = None,
        conflict_policy: ConflictPolicy = ConflictPolicy.SKIP,
        source_root: Path | None = None,
        follow_symlinks: bool = False,
    ) -> ImportPlan:
        adapter = create_import_adapter(source_app, source_root)
        sections = include or self._default_sections_for_app(source_app)
        excluded = set(exclude or [])
        sections = [section for section in sections if section not in excluded]

        actions: list[ImportAction] = []
        errors: list[str] = []
        skipped: list[str] = []

        unsupported = self._unsupported_sections(adapter.app_id.value, sections)
        for section in unsupported:
            skipped.append(
                f"Section unsupported for {adapter.app_id.value}: {section.value}"
            )

        active_sections = [
            section for section in sections if section not in unsupported
        ]

        if ImportSection.MCP in active_sections:
            mcp_actions, mcp_errors, mcp_skipped = self._plan_mcp(
                adapter=adapter,
                conflict_policy=conflict_policy,
            )
            actions.extend(mcp_actions)
            errors.extend(mcp_errors)
            skipped.extend(mcp_skipped)

        if ImportSection.SKILLS in active_sections:
            skill_actions, skill_errors, skill_skipped = self._plan_assets(
                section=ImportSection.SKILLS,
                source_dir=adapter.skills_dir,
                target_dir=self._core.skills_dir,
                conflict_policy=conflict_policy,
                follow_symlinks=follow_symlinks,
            )
            actions.extend(skill_actions)
            errors.extend(skill_errors)
            skipped.extend(skill_skipped)

        if ImportSection.AGENTS in active_sections and adapter.agents_dir is not None:
            agent_actions, agent_errors, agent_skipped = self._plan_assets(
                section=ImportSection.AGENTS,
                source_dir=adapter.agents_dir,
                target_dir=self._core.agents_dir,
                conflict_policy=conflict_policy,
                follow_symlinks=follow_symlinks,
            )
            actions.extend(agent_actions)
            errors.extend(agent_errors)
            skipped.extend(agent_skipped)

        return ImportPlan(
            source_app=adapter.app_id.value,
            sections=sections,
            actions=actions,
            errors=errors,
            skipped=skipped,
        )

    def apply(self, plan: ImportPlan) -> ImportApplyResult:
        if plan.errors:
            return ImportApplyResult(
                applied=0, failed=len(plan.errors), failures=plan.errors
            )

        applied = 0
        failed = 0
        failures: list[str] = []

        for action in plan.actions:
            if action.kind == ImportActionKind.NOTE:
                continue
            if action.status not in (
                ImportActionStatus.CREATE,
                ImportActionStatus.UPDATE,
            ):
                continue

            try:
                if action.kind == ImportActionKind.WRITE_MCP_BASE:
                    if not isinstance(action.payload, dict):
                        raise ValueError("invalid MCP payload")
                    write_json(self._core.mcp_base_path, action.payload)
                    applied += 1
                    continue

                if action.kind == ImportActionKind.COPY_PATH:
                    if action.source is None or action.target is None:
                        raise ValueError("missing source/target")
                    if action.target.exists() or action.target.is_symlink():
                        remove_path(action.target)
                    copy_path(action.source, action.target)
                    applied += 1
                    continue

                failed += 1
                failures.append(f"Unsupported action kind: {action.kind.value}")
            except Exception as exc:
                failed += 1
                failures.append(str(exc))

        return ImportApplyResult(applied=applied, failed=failed, failures=failures)

    @staticmethod
    def _default_sections_for_app(source_app: str) -> list[ImportSection]:
        if source_app.lower() == "codex":
            return [ImportSection.MCP, ImportSection.SKILLS]
        return [ImportSection.MCP, ImportSection.SKILLS, ImportSection.AGENTS]

    @staticmethod
    def _unsupported_sections(
        source_app: str, sections: list[ImportSection]
    ) -> list[ImportSection]:
        unsupported: list[ImportSection] = []
        if source_app == "codex" and ImportSection.AGENTS in sections:
            unsupported.append(ImportSection.AGENTS)
        return unsupported

    def _plan_mcp(self, adapter, conflict_policy: ConflictPolicy):
        actions: list[ImportAction] = []
        errors: list[str] = []
        skipped: list[str] = []

        try:
            source_dto = adapter.mapper.to_common(adapter.load_mcp_payload())
        except (InvalidJsonFormatError, InvalidConfigSchemaError) as exc:
            return actions, [str(exc)], skipped

        existing_payload, existing_error = read_json_safe(self._core.mcp_base_path)
        if existing_error is not None:
            return (
                actions,
                [f"Invalid JSON format ({existing_error}): {self._core.mcp_base_path}"],
                skipped,
            )

        if existing_payload is None:
            existing_payload = {"mcpServers": {}}
        if not isinstance(existing_payload, dict):
            return (
                actions,
                [
                    f"Invalid config schema (must be a JSON object): {self._core.mcp_base_path}"
                ],
                skipped,
            )

        existing_servers = existing_payload.get("mcpServers")
        if existing_servers is None:
            existing_servers = {}
        if not isinstance(existing_servers, dict):
            return (
                actions,
                [
                    f"Invalid config schema (must contain object key 'mcpServers'): {self._core.mcp_base_path}"
                ],
                skipped,
            )

        merged: dict[str, MCPServerDTO] = common_mcp_to_dto(existing_servers)
        changed = not self._core.mcp_base_path.exists()

        for name in sorted(source_dto):
            incoming = source_dto[name]
            current = merged.get(name)
            if current is None:
                merged[name] = incoming
                changed = True
                actions.append(
                    ImportAction(
                        section=ImportSection.MCP,
                        kind=ImportActionKind.NOTE,
                        status=ImportActionStatus.CREATE,
                        detail=f"Import MCP server '{name}'",
                    )
                )
                continue

            if current == incoming:
                actions.append(
                    ImportAction(
                        section=ImportSection.MCP,
                        kind=ImportActionKind.NOTE,
                        status=ImportActionStatus.NOOP,
                        detail=f"MCP server '{name}' already matches",
                    )
                )
                continue

            if conflict_policy == ConflictPolicy.OVERWRITE:
                merged[name] = incoming
                changed = True
                actions.append(
                    ImportAction(
                        section=ImportSection.MCP,
                        kind=ImportActionKind.NOTE,
                        status=ImportActionStatus.UPDATE,
                        detail=f"Overwrite MCP server '{name}'",
                    )
                )
                continue

            actions.append(
                ImportAction(
                    section=ImportSection.MCP,
                    kind=ImportActionKind.NOTE,
                    status=ImportActionStatus.CONFLICT,
                    detail=f"Conflict on MCP server '{name}'",
                )
            )
            if conflict_policy == ConflictPolicy.FAIL:
                errors.append(f"Conflict on MCP server '{name}'")
            else:
                skipped.append(f"MCP server skipped due to conflict: {name}")

        normalized_payload = {"mcpServers": dto_to_common_mcp(merged)}
        actions.append(
            ImportAction(
                section=ImportSection.MCP,
                kind=ImportActionKind.WRITE_MCP_BASE,
                status=(
                    ImportActionStatus.CREATE
                    if not self._core.mcp_base_path.exists()
                    else ImportActionStatus.UPDATE
                    if changed
                    else ImportActionStatus.NOOP
                ),
                detail="Write merged MCP base",
                target=self._core.mcp_base_path,
                payload=normalized_payload,
            )
        )

        return actions, errors, skipped

    def _plan_assets(
        self,
        section: ImportSection,
        source_dir: Path,
        target_dir: Path,
        conflict_policy: ConflictPolicy,
        follow_symlinks: bool,
    ):
        actions: list[ImportAction] = []
        errors: list[str] = []
        skipped: list[str] = []

        if not source_dir.exists() or not source_dir.is_dir():
            skipped.append(f"Source {section.value} directory missing: {source_dir}")
            return actions, errors, skipped

        for entry in sorted(source_dir.iterdir(), key=lambda item: item.name):
            if entry.name.startswith("."):
                continue

            if not follow_symlinks and is_entry_symlink(entry):
                skipped.append(f"Skipped symlink {section.value} entry: {entry}")
                actions.append(
                    ImportAction(
                        section=section,
                        kind=ImportActionKind.COPY_PATH,
                        status=ImportActionStatus.SKIP,
                        detail=f"Skip symlink entry '{entry.name}'",
                        source=entry,
                        target=target_dir / entry.name,
                    )
                )
                continue

            if not follow_symlinks and tree_contains_symlink(entry):
                skipped.append(
                    f"Skipped {section.value} entry with nested symlink: {entry}"
                )
                actions.append(
                    ImportAction(
                        section=section,
                        kind=ImportActionKind.COPY_PATH,
                        status=ImportActionStatus.SKIP,
                        detail=f"Skip nested symlink entry '{entry.name}'",
                        source=entry,
                        target=target_dir / entry.name,
                    )
                )
                continue

            target = target_dir / entry.name
            if not target.exists() and not target.is_symlink():
                actions.append(
                    ImportAction(
                        section=section,
                        kind=ImportActionKind.COPY_PATH,
                        status=ImportActionStatus.CREATE,
                        detail=f"Import {section.value} '{entry.name}'",
                        source=entry,
                        target=target,
                    )
                )
                continue

            if content_equal(entry, target):
                actions.append(
                    ImportAction(
                        section=section,
                        kind=ImportActionKind.COPY_PATH,
                        status=ImportActionStatus.NOOP,
                        detail=f"{section.value.title()} '{entry.name}' unchanged",
                        source=entry,
                        target=target,
                    )
                )
                continue

            if conflict_policy == ConflictPolicy.OVERWRITE:
                actions.append(
                    ImportAction(
                        section=section,
                        kind=ImportActionKind.COPY_PATH,
                        status=ImportActionStatus.UPDATE,
                        detail=f"Overwrite {section.value} '{entry.name}'",
                        source=entry,
                        target=target,
                    )
                )
                continue

            actions.append(
                ImportAction(
                    section=section,
                    kind=ImportActionKind.COPY_PATH,
                    status=ImportActionStatus.CONFLICT,
                    detail=f"Conflict on {section.value} '{entry.name}'",
                    source=entry,
                    target=target,
                )
            )
            if conflict_policy == ConflictPolicy.FAIL:
                errors.append(f"Conflict on {section.value} '{entry.name}'")
            else:
                skipped.append(f"Skipped conflict on {section.value} '{entry.name}'")

        return actions, errors, skipped
