from pathlib import Path


class SyncAppError(Exception):
    """Base user-facing application error."""


class SyncFileError(SyncAppError):
    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{message}: {path}")


class MissingConfigFileError(SyncFileError):
    def __init__(self, path: Path) -> None:
        super().__init__(path=path, message="Missing required config file")


class InvalidJsonFormatError(SyncFileError):
    def __init__(self, path: Path, detail: str) -> None:
        self.detail = detail
        super().__init__(path=path, message=f"Invalid JSON format ({detail})")


class InvalidConfigSchemaError(SyncFileError):
    def __init__(self, path: Path, detail: str) -> None:
        self.detail = detail
        super().__init__(path=path, message=f"Invalid config schema ({detail})")
