from typing import Final


AGENTS_FILENAME: Final[str] = "AGENTS.md"
CLAUDE_FILENAME: Final[str] = "CLAUDE.md"
GIT_DIRNAME: Final[str] = ".git"
SYNC_STATE_FILENAME: Final[str] = ".sync-state.json"
SYNC_REVISIONS_DIRNAME: Final[str] = ".sync-revisions"
SYNC_STAGING_DIRNAME: Final[str] = ".sync-staging"

RULES_DIRNAME: Final[str] = "rules"
SKILLS_DIRNAME: Final[str] = "skills"
AGENTS_DIRNAME: Final[str] = "agents"

OPENCODE_PROJECT_DIRNAME: Final[str] = ".opencode"
CURSOR_PROJECT_DIRNAME: Final[str] = ".cursor"
CODEX_PROJECT_DIRNAME: Final[str] = ".codex"

OPENCODE_CONFIG_FILENAME: Final[str] = "opencode.json"
CURSOR_CONFIG_FILENAME: Final[str] = "mcp.json"
CODEX_CONFIG_FILENAME: Final[str] = "config.toml"

WORKSPACE_IGNORED_DIRS: Final[tuple[str, ...]] = (
    "node_modules",
    ".venv",
)
