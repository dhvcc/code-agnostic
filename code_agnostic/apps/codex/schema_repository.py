from pathlib import Path

from code_agnostic.apps.common.schema import JsonSchemaRepository

CODEX_SCHEMA_URL = "https://github.com/openai/codex/raw/refs/heads/main/codex-rs/core/config.schema.json"


class CodexSchemaRepository(JsonSchemaRepository):
    def __init__(self, ttl_seconds: int = 3600) -> None:
        super().__init__(
            local_schema_path=Path(__file__).resolve().parent / "schema.json",
            remote_schema_url=CODEX_SCHEMA_URL,
            ttl_seconds=ttl_seconds,
        )
