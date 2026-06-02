from pathlib import Path

import code_agnostic

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def test_runtime_version_matches_package_metadata() -> None:
    with Path("pyproject.toml").open("rb") as handle:
        package_version = tomllib.load(handle)["project"]["version"]

    assert code_agnostic.__version__ == package_version
