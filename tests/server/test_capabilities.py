"""
W6: prompts and resources are served empty.

MCPServer always registers the prompts/list and resources/list handlers, and
the SDK advertises a capability for every registered handler, so the server
cannot stop advertising them without reaching into SDK internals.
"""

from typing import Any

from mcp import ClientSession


def test_prompts_and_resources_are_empty(harness: Any) -> None:
    """Both capabilities are advertised; both lists are empty."""

    async def scenario(client: ClientSession) -> dict[str, Any]:
        initialized = client.initialize_result
        assert initialized is not None
        return {
            "capabilities": initialized.capabilities,
            "prompts": (await client.list_prompts()).prompts,
            "resources": (await client.list_resources()).resources,
        }

    out = harness.run(scenario)
    assert out["capabilities"].prompts is not None
    assert out["capabilities"].resources is not None
    assert out["prompts"] == []
    assert out["resources"] == []
