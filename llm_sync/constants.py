from typing import Final, Tuple


AGENTS_FILENAME: Final[str] = "AGENTS.md"
CLAUDE_FILENAME: Final[str] = "CLAUDE.md"
GIT_DIRNAME: Final[str] = ".git"

WORKSPACE_RULE_FILES: Final[Tuple[str, ...]] = (
    AGENTS_FILENAME,
    AGENTS_FILENAME.lower(),
    CLAUDE_FILENAME,
    CLAUDE_FILENAME.lower(),
)
WORKSPACE_RULE_FILES_DISPLAY: Final[str] = "AGENTS.md/CLAUDE.md"

WORKSPACE_IGNORED_DIRS: Final[Tuple[str, ...]] = (
    "node_modules",
    ".venv",
)
