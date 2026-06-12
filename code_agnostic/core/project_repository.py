from pathlib import Path

from code_agnostic.core.workspace_repository import WorkspaceConfigRepository


class ProjectConfigRepository(WorkspaceConfigRepository):
    """Source repository for project-level config."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
