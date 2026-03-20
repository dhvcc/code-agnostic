"""CLI package - organized command modules and shared utilities."""

from code_agnostic.cli.aliases import AliasedGroup
from code_agnostic.cli.helpers import (
    ensure_exclude_entries,
    require_workspace_entry,
    status_row_for_app,
    workspace_config_root,
)
from code_agnostic.cli.options import (
    app_option,
    import_app_option,
    manageable_app_option,
    verbose_option,
    workspace_option,
)

__all__ = [
    "AliasedGroup",
    "app_option",
    "import_app_option",
    "manageable_app_option",
    "verbose_option",
    "workspace_option",
    "require_workspace_entry",
    "workspace_config_root",
    "status_row_for_app",
    "ensure_exclude_entries",
]
