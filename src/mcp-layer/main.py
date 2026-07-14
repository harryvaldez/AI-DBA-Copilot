"""AI DBA Copilot - MCP Layer Service"""

import os

import httpx
import uvicorn
from fastapi import FastAPI

app = FastAPI(title="AI DBA Copilot - MCP Layer", version="0.1.0")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:8080")


async def _check_mcp_connectivity() -> str:
    """Probe MCP server; return connected or degraded."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{MCP_SERVER_URL.rstrip('/')}/health")
            if response.status_code < 500:
                return "connected"
    except httpx.HTTPError:
        pass
    return "degraded"


@app.get("/health")
async def health():
    mcp_status = await _check_mcp_connectivity()
    status = "ok" if mcp_status == "connected" else "degraded"
    return {
        "status": status,
        "service": "mcp-layer",
        "version": "0.1.0",
        "mcp_connectivity": mcp_status,
        "mcp_server_url": MCP_SERVER_URL,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)
