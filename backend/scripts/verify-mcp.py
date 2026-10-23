"""Verify the bundled MCP adapter over a real local stdio connection, offline."""

import asyncio
import json
import sys
from pathlib import Path

from fastmcp import FastMCP
from langchain.mcp import MCPAdapter


def serve() -> None:
    server = FastMCP("portable-dependency-check")

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two integers to verify local MCP transport."""
        return a + b

    server.run(transport="stdio", show_banner=False, log_level="ERROR")


async def verify() -> None:
    project_root = Path(__file__).resolve().parents[1]
    assert Path(sys.executable).resolve() == (project_root / "bishi1/python.exe").resolve()
    config = {
        "mcpServers": {
            "probe": {
                "command": sys.executable,
                "args": ["-B", str(Path(__file__).resolve()), "--server"],
            }
        }
    }
    adapter = MCPAdapter(config)
    try:
        async with asyncio.timeout(30):
            async with adapter:
                tools = await adapter.list_tools(cache_mode="refresh")
            # Tools remain usable after discovery; stdio may reuse its session.
            assert [tool.name for tool in tools] == ["add"], [tool.name for tool in tools]
            tool = tools[0]
            result = await tool.ainvoke(
                {
                    "name": tool.name,
                    "args": {"a": 19, "b": 23},
                    "id": "portable-mcp-check",
                    "type": "tool_call",
                }
            )
            assert result.status == "success", result
            assert result.content[0]["text"] == "42", result.content
    finally:
        # Adapter context exit alone can leave a keep-alive stdio child running.
        async with asyncio.timeout(10):
            await adapter.client.close()
    print(
        json.dumps(
            {
                "mcp_stdio": "ok",
                "tool_discovery": "ok",
                "call_after_discovery_context": "ok",
                "client_closed": True,
                "tool": tool.name,
                "result": 42,
                "project_external_workdir": Path.cwd().resolve() != project_root,
            }
        )
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--server"]:
        serve()
    elif not sys.argv[1:]:
        asyncio.run(verify())
    else:
        raise SystemExit("Usage: python.cmd scripts/verify-mcp.py [--server]")
