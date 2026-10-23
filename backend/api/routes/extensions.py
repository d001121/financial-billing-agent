"""Extension configuration and official MCP connectivity probes."""
import asyncio

from fastapi import APIRouter, Request
from httpx import HTTPError
from httpx2 import HTTPError as MCPHTTPError
from langchain_core.tools import ToolException
from pydantic import ValidationError

from backend.config.transactions import read_config, write_config
from backend.infrastructure.repository import loads
from backend.extensions import packages
from backend.harness.dispatch import PolicyDenied

from ..responses import response

router = APIRouter(tags=['extensions'])


@router.get('/api/extensions/skills')
def list_packages():
    return response({'skills': packages.catalog()})


@router.get('/api/extensions/skills/{name}/resource')
def read_package_resource(name: str, path: str = 'SKILL.md'):
    return response(packages.resource(name, path))


@router.post('/api/extensions/skills/import')
async def import_package(request: Request):
    form = await request.form()
    archive = form.get('file')
    if not hasattr(archive, 'read'):
        raise ValueError('请选择Skill ZIP文件')
    try:
        expected = int(form.get('expected_version', ''))
        tools = loads(form.get('tools') or '[]')
        content = await archive.read(20 * 1024 * 1024 + 1)
        result = await asyncio.to_thread(packages.install, content, expected, tools)
    except (ValidationError, TypeError) as exc:
        raise ValueError(str(exc)) from exc
    return response(result, 201)


@router.get('/api/config/{kind}')
def get_configuration(kind: str):
    return response(read_config(kind))


@router.put('/api/config/{kind}')
async def put_configuration(kind: str, request: Request):
    body = loads(await request.body())
    value = await asyncio.to_thread(write_config, kind, body.get('config', body), body.get('expected_version'))
    return response(value)


@router.post('/api/config/mcp/test')
async def test_mcp(request: Request):
    from langchain.mcp import MCPAdapter
    body = loads(await request.body())
    server = body.get('server', body)
    from backend.config.schemas import Server
    try:
        server = Server.model_validate(server).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if bool(server.get('url')) == bool(server.get('transport')):
        raise ValueError('MCP须提供且仅提供url或transport')
    target = server.get('url') or {'mcpServers': {server['id']: server['transport']}}
    adapter = MCPAdapter(target)
    try:
        try:
            async with asyncio.timeout(30):
                async with adapter:
                    tools = await adapter.list_tools(cache_mode='refresh')
        finally:
            await adapter.client.close()
        return response({'ok': True, 'tools': [dict(name=t.name, description=t.description,
                         schema=t.args) for t in tools]})
    except (TimeoutError, ConnectionError, RuntimeError, OSError, HTTPError, MCPHTTPError) as exc:
        return response({'ok': False, 'message': f'MCP连接失败（{type(exc).__name__}），请检查地址、进程和认证配置'}, 502)


@router.post('/api/config/mcp/call')
async def call_mcp(request: Request):
    """Explicit admin diagnostic; use the same native adapter as Agent calls."""
    from langchain.mcp import MCPAdapter
    body = loads(await request.body())
    server = next((s for s in read_config('mcp')['servers'] if s['id'] == body.get('server_id')), None)
    if not server or not server.get('enabled', True):
        raise PolicyDenied('MCP未注册或已禁用，测试调用未执行')
    if not isinstance(body.get('arguments', {}), dict):
        raise ValueError('工具参数须为JSON对象')
    target = server.get('url') or {'mcpServers': {server['id']: server['transport']}}
    adapter = MCPAdapter(target)
    try:
        try:
            async with asyncio.timeout(30):
                async with adapter:
                    tools = await adapter.list_tools(cache_mode='refresh')
                    tool = next((t for t in tools if t.name == body.get('tool')), None)
                    if tool is None:
                        raise ValueError('工具不在该服务实际发现的列表中')
                    result = await tool.ainvoke(body.get('arguments', {}))
                    return response(dict(ok=True, server_id=server['id'], tool=tool.name, result=result))
        finally:
            await adapter.client.close()
    except (TimeoutError, ConnectionError, RuntimeError, OSError, HTTPError, MCPHTTPError, ToolException) as exc:
        return response(dict(ok=False, server_id=server['id'], tool=body.get('tool'),
            message=f'MCP调用失败（{type(exc).__name__}）；远端是否执行须核对回执，未自动重试'), 502)
