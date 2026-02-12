from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class IConfigRepository(ABC):
    @property
    @abstractmethod
    def root(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_state(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_state(self, data: dict[str, Any]) -> None:
        raise NotImplementedError
