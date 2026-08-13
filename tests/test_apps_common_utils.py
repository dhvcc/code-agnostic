import pytest

from code_agnostic.apps.common.utils import apply_mcp_servers
from code_agnostic.errors import SyncAppError


@pytest.mark.parametrize(
    "desired",
    [
        {"command": "user-tool"},
        {"command": "managed-tool"},
    ],
)
def test_apply_mcp_servers_rejects_unmanaged_same_name(
    desired: dict[str, str],
) -> None:
    existing = {"demo": {"command": "user-tool"}}

    with pytest.raises(
        SyncAppError,
        match="MCP server 'demo' conflicts with an unmanaged existing server",
    ):
        apply_mcp_servers(
            existing,
            {"demo": desired},
        )

    assert existing == {"demo": {"command": "user-tool"}}


def test_apply_mcp_servers_updates_previously_managed_same_name() -> None:
    assert apply_mcp_servers(
        {"demo": {"command": "old-tool"}},
        {"demo": {"command": "new-tool"}},
        previously_managed={"demo"},
    ) == {"demo": {"command": "new-tool"}}


def test_apply_mcp_servers_replaces_owned_output() -> None:
    assert apply_mcp_servers(
        {"user": {"command": "user-tool"}},
        {"demo": {"command": "managed-tool"}},
        replace=True,
    ) == {"demo": {"command": "managed-tool"}}
