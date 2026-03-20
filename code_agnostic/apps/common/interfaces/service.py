from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from code_agnostic.apps.app_id import AppId, app_scope
from code_agnostic.apps.common.compiled_planning import plan_compiled_text_action
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.apps.common.symlink_planning import (
    load_state_links,
    load_state_paths,
    plan_stale_files_group,
    plan_stale_group,
)
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan


class IAppConfigService(ABC):
    @property
    @abstractmethod
    def app_id(self) -> AppId:
        raise NotImplementedError

    @property
    @abstractmethod
    def app_label(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def action_kind(self) -> ActionKind:
        raise NotImplementedError

    @property
    @abstractmethod
    def repository(self) -> IAppConfigRepository:
        raise NotImplementedError

    @property
    @abstractmethod
    def mapper(self) -> IAppMCPMapper:
        raise NotImplementedError

    @abstractmethod
    def validate_config(self, payload: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        raise NotImplementedError

    @abstractmethod
    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        raise NotImplementedError

    @abstractmethod
    def plan_skill_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
        removable_links: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        raise NotImplementedError

    @abstractmethod
    def plan_agent_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
        removable_links: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        raise NotImplementedError

    def agent_action_removable_links(self, removable_links: list[Path]) -> list[Path]:
        return []

    @staticmethod
    def _normalize_managed_group(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _plan_compiled_text_actions(
        self,
        *,
        sources: list[Path],
        scope: str,
        app: str,
        managed_paths: list[Path],
        removable_links: list[Path],
        compile_source: Callable[[Path], tuple[Path, str]],
        create_detail: str,
        noop_detail: str,
        update_detail: str,
        conflict_message: str,
    ) -> tuple[list[Action], list[Path], list[str]]:
        managed_path_set = {path.resolve(strict=False) for path in managed_paths}
        removable_link_set = {path.resolve(strict=False) for path in removable_links}
        actions: list[Action] = []
        desired_paths: list[Path] = []
        skipped: list[str] = []

        for source in sources:
            target, payload = compile_source(source)
            desired_paths.append(target)
            action = plan_compiled_text_action(
                target=target,
                payload=payload,
                managed_paths=managed_path_set,
                removable_link_paths=removable_link_set,
                scope=scope,
                app=app,
                create_detail=create_detail,
                noop_detail=noop_detail,
                update_detail=update_detail,
            )
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(conflict_message.format(target=target))

        return actions, desired_paths, skipped

    def _build_compiled_group(
        self,
        *,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        resource_name: str,
        plan_actions: Callable[
            [list[Path], Path, str, str, list[Path], list[Path]],
            tuple[list[Action], list[Path], list[str]],
        ],
        managed_links_group: dict[str, Any],
        managed_paths_group: dict[str, Any],
        action_removable_links: list[Path] | None = None,
    ) -> tuple[list[Action], list[str]]:
        managed_link_paths = load_state_links(managed_links_group, scope)
        managed_file_paths = load_state_paths(managed_paths_group, scope)
        compiled_actions, desired_paths, skipped = plan_actions(
            sources,
            target_dir,
            scope,
            self.app_id.value,
            managed_file_paths,
            (
                managed_link_paths
                if action_removable_links is None
                else action_removable_links
            ),
        )
        actions = list(compiled_actions)
        actions.extend(
            plan_stale_group(
                old_links=managed_link_paths,
                desired_links=desired_paths,
                remove_detail=f"remove stale managed {resource_name} symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
                app=self.app_id.value,
                scope=scope,
                skipped=skipped,
                skipped_message="Stale link cleanup skipped (not symlink): {path}",
            )
        )
        actions.extend(
            plan_stale_files_group(
                old_paths=managed_file_paths,
                desired_paths=desired_paths,
                remove_detail=f"remove stale managed {resource_name} file",
                conflict_detail="stale managed path is not a file",
                noop_detail="stale managed file already absent",
                app=self.app_id.value,
                scope=scope,
                skipped=skipped,
                skipped_message="Stale file cleanup skipped (not file): {path}",
            )
        )
        return actions, skipped

    def build_action(self, common_servers: dict[str, MCPServerDTO]) -> Action:
        existing = self.repository.load_config()
        if existing or self.repository.config_path.exists():
            self.validate_config(existing)

        desired_mcp = self.mapper.from_common(common_servers)
        merged = dict(existing)
        self.set_mcp_payload(merged, desired_mcp)
        self.validate_config(merged)

        return Action(
            kind=self.action_kind,
            path=self.repository.config_path,
            status=self.derive_status(existing, merged),
            detail=f"sync {self.app_id.value} config from common mcp base",
            payload=self.build_action_payload(merged),
            app=self.app_id.value,
        )

    def build_plan(
        self,
        common_servers: dict[str, MCPServerDTO],
        source_repository: ISourceRepository,
    ) -> SyncPlan:
        state = source_repository.load_state()
        managed_links_group = self._normalize_managed_group(state.get("managed_links"))
        managed_paths_group = self._normalize_managed_group(state.get("managed_paths"))
        skill_scope = app_scope(self.app_id, "skills")
        agent_scope = app_scope(self.app_id, "agents")

        skill_actions, skill_skipped = self._build_compiled_group(
            sources=source_repository.list_skill_sources(),
            target_dir=self.repository.skills_dir,
            scope=skill_scope,
            resource_name="skill",
            plan_actions=self.plan_skill_actions,
            managed_links_group=managed_links_group,
            managed_paths_group=managed_paths_group,
        )
        agent_actions, agent_skipped = self._build_compiled_group(
            sources=source_repository.list_agent_sources(),
            target_dir=self.repository.agents_dir,
            scope=agent_scope,
            resource_name="agent",
            plan_actions=self.plan_agent_actions,
            managed_links_group=managed_links_group,
            managed_paths_group=managed_paths_group,
            action_removable_links=self.agent_action_removable_links(
                load_state_links(managed_links_group, agent_scope)
            ),
        )
        return SyncPlan(
            actions=[
                self.build_action(common_servers),
                *skill_actions,
                *agent_actions,
            ],
            errors=[],
            skipped=[*skill_skipped, *agent_skipped],
        )
