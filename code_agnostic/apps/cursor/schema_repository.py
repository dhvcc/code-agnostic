from pathlib import Path

from code_agnostic.apps.common.schema import JsonSchemaRepository


class CursorSchemaRepository(JsonSchemaRepository):
    def __init__(self, ttl_seconds: int = 3600) -> None:
        super().__init__(
            local_schema_path=Path(__file__).resolve().parent / "schema.json",
            remote_schema_url=None,
            ttl_seconds=ttl_seconds,
        )
