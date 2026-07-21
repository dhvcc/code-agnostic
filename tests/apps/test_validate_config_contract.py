"""One validation contract across every editor: empty/absent config is valid,
non-object config is rejected, schema checks (where present) run on top."""

from pathlib import Path

import pytest

from code_agnostic.apps.app_id import AppId
from code_agnostic.apps.common.framework import create_registered_app_service
from code_agnostic.errors import InvalidConfigSchemaError

APPS = [AppId.OPENCODE, AppId.CURSOR, AppId.CODEX, AppId.CLAUDE, AppId.COPILOT]


@pytest.mark.parametrize("app_id", APPS, ids=lambda a: a.value)
def test_empty_and_none_config_is_valid(app_id: AppId, tmp_path: Path) -> None:
    service = create_registered_app_service(app_id, root=tmp_path / app_id.value)
    service.validate_config({})
    service.validate_config(None)


@pytest.mark.parametrize("app_id", APPS, ids=lambda a: a.value)
@pytest.mark.parametrize("bad", ["a string", ["a", "list"], 42])
def test_non_object_config_is_rejected(
    app_id: AppId, bad: object, tmp_path: Path
) -> None:
    service = create_registered_app_service(app_id, root=tmp_path / app_id.value)
    # Every editor — including Claude, which previously did no validation —
    # now rejects a non-object config through the shared contract.
    with pytest.raises(InvalidConfigSchemaError):
        service.validate_config(bad)
