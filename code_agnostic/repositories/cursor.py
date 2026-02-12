from pathlib import Path
from typing import Optional


class CursorRepository:
    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root or (Path.home() / ".cursor")

    @property
    def root(self) -> Path:
        return self._root
