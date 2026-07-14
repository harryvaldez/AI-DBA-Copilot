"""Unit tests for mcp-layer MCP connectivity probing."""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_MAIN_PATH = Path(__file__).resolve().parents[2] / "src" / "mcp-layer" / "main.py"
_SPEC = importlib.util.spec_from_file_location("mcp_layer_main", _MAIN_PATH)
assert _SPEC is not None and _SPEC.loader is not None
mcp_layer_main = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mcp_layer_main)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, "connected"),
        (204, "connected"),
        (401, "degraded"),
        (404, "degraded"),
        (500, "degraded"),
        (503, "degraded"),
    ],
)
async def test_check_mcp_connectivity_status_codes(status_code: int, expected: str) -> None:
    response = MagicMock()
    response.status_code = status_code

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(mcp_layer_main.httpx, "AsyncClient", return_value=mock_client):
        assert await mcp_layer_main._check_mcp_connectivity() == expected
