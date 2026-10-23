"""Validate native component configuration and application references, without execution.

Checked through Docs/API MCP 2026-10-21: MCPAdapter/MCPConfig, SkillsMiddleware
before_agent, and langchain.tools.tool (langchain 1.4.6, deepagents 0.7.29,
FastMCP 4.1.2). These supply transport, Skill discovery and tool schemas, not
the application's file transaction or cross-configuration reference policy.
"""
import importlib.util
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from uuid import uuid4
from .schemas import MODELS, REQUIRED_HOOKS, HOST_TOOLS
from .prompts import resolve_agent_prompts


def _unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f'{label}有重复名称')


def _http_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or any(c.isspace() for c in value):
        raise ValueError('MCP远程地址必须是合法的http(s) URL')
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError('MCP URL端口无效') from exc


def validate_configuration(config, root):
    """Validate a prospective complete config without connecting or invoking tools."""
    from deepagents.backends import FilesystemBackend
    from deepagents.middleware.skills import SkillsMiddleware
    from fastmcp.mcp_config import MCPConfig
    from langchain.tools import tool
    from langgraph.runtime import Runtime as GraphRuntime

    config = dict(config)
    config['agents'] = resolve_agent_prompts(config['agents'], root)
    config = {kind: model.model_validate(config[kind]).model_dump(exclude_unset=True)
              for kind, model in MODELS.items()}
    for kind, key, identity in (('agents', 'agents', 'name'), ('skills', 'skills', 'name'),
                                ('hooks', 'hooks', 'name'), ('mcp', 'servers', 'id')):
        _unique([s[identity] for s in config[kind][key]], kind)
    skills = {s['name']: s for s in config['skills']['skills']}
    skill_directory = (Path(root) / 'skills').resolve()
    modules, temporary_modules = {}, []
    try:
        for name in skills:
            directory = (skill_directory / name).resolve()
            if not directory.is_relative_to(skill_directory) or not (directory / 'SKILL.md').is_file():
                raise ValueError(f'Skill路径或SKILL.md不存在: {name}')
            if not (directory / 'references').is_dir() or not (directory / 'scripts').is_dir():
                raise ValueError(f'Skill缺少references或scripts目录: {name}')
            if not (directory / 'scripts' / 'skill.py').is_file():
                if skills[name].get('tools') or any(h.get('skill') == name for h in config['hooks']['hooks']):
                    raise ValueError(f'Skill工具/Hook绑定需要scripts/skill.py: {name}')
                continue
            module_name = '_validate_skill_' + uuid4().hex
            spec = importlib.util.spec_from_file_location(module_name, directory / 'scripts' / 'skill.py')
            module = importlib.util.module_from_spec(spec)
            temporary_modules.append(module_name)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                raise ValueError(f'Skill无法导入: {name}: {type(exc).__name__}: {exc}') from exc
            modules[name] = module
        # This backend is used solely for trusted admin metadata discovery. It is
        # never installed on an Agent and exposes no filesystem tool to callers.
        discovered = SkillsMiddleware(backend=FilesystemBackend(root_dir=skill_directory), sources=['/']).before_agent(
            {'messages': []}, GraphRuntime(), {})
        metadata = {s['name']: s for s in discovered['skills_metadata']}
        for name in skills:
            if name not in metadata or metadata[name]['path'] != f'/{name}/SKILL.md':
                raise ValueError(f'Skill原生发现失败或frontmatter名称不匹配: {name}')
            names = metadata[name].get('metadata', {}).get('include_tools', '').split()
            if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*', n) for n in names):
                raise ValueError(f'Skill include_tools必须是空格分隔工具名: {name}')
        tool_names = []
        for name, skill in skills.items():
            for binding in skill.get('tools', []):
                fn = getattr(modules[name], binding['function'], None)
                if not callable(fn):
                    raise ValueError(f'Skill工具函数不存在: {name}.{binding["function"]}')
                tool_name = binding.get('name') or binding['function']
                if tool_name in HOST_TOOLS or tool_name.startswith('mcp_'):
                    raise ValueError(f'扩展工具与宿主/原生工具名称冲突: {tool_name}')
                tool(tool_name)(fn)  # Native schema validation; never invokes the function.
                tool_names.append(tool_name)
        _unique(tool_names, 'Skill工具')
        available = HOST_TOOLS | set(tool_names)
        mcp_prefixes = tuple(f'mcp_{s["id"]}__' for s in config['mcp']['servers'])
        for name in skills:
            requested = metadata[name].get('metadata', {}).get('include_tools', '').split()
            missing = [n for n in requested if n not in available and not n.startswith(mcp_prefixes)]
            if missing:
                raise ValueError(f'Skill声明了未绑定的工具: {name}: {", ".join(missing)}')
        for agent in config['agents']['agents']:
            _unique(agent['skills'], f'Agent {agent["name"]} Skills')
            if set(agent['skills']) - set(skills):
                raise ValueError(f'Agent引用未注册Skill: {agent["name"]}')
        hooks = config['hooks']['hooks']
        if REQUIRED_HOOKS - {h['name'] for h in hooks}:
            raise ValueError('缺少必需Hook: ' + ','.join(sorted(REQUIRED_HOOKS - {h['name'] for h in hooks})))
        for hook in hooks:
            native, name = hook.get('native'), hook['name']
            if native:
                if hook.get('skill') or hook.get('function') or {'capability': 'dispatch-policy', 'budget': 'shared-budget'}.get(name) != native:
                    raise ValueError(f'原生Hook绑定无效: {name}')
            elif hook.get('skill') not in modules or not callable(getattr(modules[hook['skill']], hook.get('function') or '', None)):
                raise ValueError(f'Hook的Skill或函数不存在: {name}')
        for server in config['mcp']['servers']:
            url, transport = server.get('url'), server.get('transport')
            if bool(url) == bool(transport):
                raise ValueError(f'MCP须提供且仅提供url或transport: {server["id"]}')
            if url:
                _http_url(url)
            else:
                parsed = MCPConfig.model_validate({'mcpServers': {server['id']: transport}})
                native = parsed.mcpServers[server['id']]
                if hasattr(native, 'url'):
                    _http_url(native.url)
                elif not getattr(native, 'command', '').strip():
                    raise ValueError('MCP stdio command不能为空')
                for key in ('timeout', 'sse_read_timeout'):
                    value = transport.get(key)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or
                            not 0 < value < float('inf')):
                        raise ValueError(f'MCP {key}须为有限正数秒')
    finally:
        for name in temporary_modules:
            sys.modules.pop(name, None)
    return config
