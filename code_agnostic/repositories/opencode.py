from pathlib import Path
from typing import Any, Optional, Tuple

from code_agnostic.apps.sync.apps.opencode.repository import (
    OpenCodeRepository as AppOpenCodeRepository,
)


class OpenCodeRepository(AppOpenCodeRepository):
    def __init__(self, root: Optional[Path] = None) -> None:
        super().__init__(root=root)

    def load_config_object(self) -> Tuple[dict[str, Any], Optional[Exception]]:
        try:
            return self.load_config(), None
        except Exception as exc:
            return {}, exc
