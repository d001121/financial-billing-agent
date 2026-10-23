"""Preserve stable server-qualified tool names and dispatch provenance."""


def namespace_tools(server_id, tools):
    namespaced, provenance = [], {}
    for tool in tools:
        named = tool.model_copy(update={'name': f'mcp_{server_id}__{tool.name}'})
        namespaced.append(named)
        provenance[named.name] = server_id
    return namespaced, provenance
