import json
from pathlib import Path

import pytest


@pytest.fixture
def write_json():
    def _write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    return _write
