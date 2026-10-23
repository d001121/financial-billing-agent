"""Own per-run MCPAdapter clients while native tools own each call session."""

from contextlib import asynccontextmanager

from langchain.mcp import MCPAdapter

from backend.config.transactions import read_config

from .discovery import namespace_tools


@asynccontextmanager
async def connected_tools(capability, execution_runtime):
    adapters = []
    tools, provenance = [], {}
    try:
        if execution_runtime:
            live = {
                server['id'] for server in read_config('mcp')['servers']
                if server.get('enabled', True)
            }
            for server in capability['config']['mcp']['servers']:
                if server['id'] not in live or not server.get('enabled', True):
                    continue
                target = server.get('url') or {
                    'mcpServers': {server['id']: server['transport']},
                }
                adapter = MCPAdapter(target)
                adapters.append(adapter)
                async with adapter:
                    discovered = await adapter.list_tools(cache_mode='refresh')
                named, owners = namespace_tools(server['id'], discovered)
                tools.extend(named)
                provenance.update(owners)
        yield tools, provenance
    finally:
        for adapter in adapters:
            await adapter.client.close()
