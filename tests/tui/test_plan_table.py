from pathlib import Path

from code_agnostic.models import Action, ActionKind, ActionStatus
from code_agnostic.tui.tables import PlanTable


def test_plan_table_labels_scoped_sources_by_name() -> None:
    workspace_action = Action(
        kind=ActionKind.WRITE_TEXT,
        path=Path("/workspace/.agents/skills/review/SKILL.md"),
        status=ActionStatus.CREATE,
        detail="create compiled codex skill",
        app="workspace",
        workspace="team",
    )
    project_action = Action(
        kind=ActionKind.WRITE_TEXT,
        path=Path("/project/.agents/skills/review/SKILL.md"),
        status=ActionStatus.CREATE,
        detail="create compiled codex skill",
        app="codex",
        project="demo",
    )

    assert PlanTable._source_label_for_action(workspace_action) == "Workspace: team"
    assert PlanTable._source_label_for_action(project_action) == "Project: demo"
