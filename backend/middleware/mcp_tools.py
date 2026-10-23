"""Resolve dynamic MCP tools, then delegate execution to the native handler."""

from langchain.agents.middleware import AgentMiddleware

from backend.config.transactions import read_config


class MCPTools(AgentMiddleware):
    def __init__(self, tools, provenance):
        self.dynamic = {tool.name: tool for tool in tools}
        self.provenance = provenance

    async def awrap_model_call(self, request, handler):
        enabled = {
            server['id'] for server in read_config('mcp')['servers']
            if server.get('enabled', True)
        }
        additions = [
            tool for name, tool in self.dynamic.items()
            if self.provenance[name] in enabled
        ]
        return await handler(request.override(tools=[*request.tools, *additions]))

    async def awrap_tool_call(self, request, handler):
        if request.tool_call['name'] in self.dynamic:
            request = request.override(tool=self.dynamic[request.tool_call['name']])
        return await handler(request)
