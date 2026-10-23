"""Compose the supervisor and configured specialists for one native server run."""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from deepagents.backends import StateBackend
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime

from backend.extensions.snapshots import snapshot
from backend.infrastructure.models import make_model
from backend.infrastructure.repository import repository
from backend.mcp.connections import connected_tools
from backend.middleware.assembly import base_stack
from backend.tools.skill_bindings import tools_for
from backend.harness.dispatch import check

from .billing.agent import build_billing_agent
from .document.agent import build_document_agent
from .supervisor.agent import build_supervisor


@asynccontextmanager
async def make_graph(config: RunnableConfig, runtime: ServerRuntime):
    task_id = config.get('configurable', {}).get('task_id')
    if task_id:
        repo = repository()
        # The factory runs on every state/stream request; loading the whole
        # task payload (sources, OCR text, messages) took ~1s per build.
        if hasattr(repo, 'get_fields'):
            task = await asyncio.to_thread(repo.get_fields, 'task', task_id, ['capability'])
        else:
            task = await asyncio.to_thread(repo.get, 'task', task_id)
    else:
        task = None
    expected = config.get('configurable', {}).get('task_revision')
    if task_id and expected is not None:
        await asyncio.to_thread(check, task_id, revision=expected, policy_only=True)
    cap = task['capability'] if task else await asyncio.to_thread(snapshot)
    revision = task['revision'] if task else 1
    scope = dict(id=config.get('configurable', {}).get('task_budget_id') or str(uuid4()),
                 revision=revision, role='supervisor')
    model, client = make_model(task_id, cap['config']['runtime'], budget_scope=scope)
    clients = [client]
    try:
        async with connected_tools(cap, runtime.execution_runtime) as (tools, provenance):
            backend = StateBackend()
            common, business = tools_for(task_id, cap)
            subagents = []
            for spec in cap['config']['agents']['agents']:
                if not spec.get('enabled', True):
                    continue
                child_backend = StateBackend()
                allowed_tools = spec.get('tools')
                child_common, child_business = tools_for(task_id, cap, spec.get('skills'), allowed_tools=allowed_tools)
                child_scope = dict(scope, role=spec['name'])
                child_model, child_client = make_model(task_id, cap['config']['runtime'], budget_scope=child_scope)
                clients.append(child_client)
                middleware = base_stack(
                    task_id, revision, cap, child_backend, child_business,
                    spec.get('skills'), tools, provenance,
                    scope=child_scope, allowed_tools=allowed_tools,
                )
                prompt = spec['prompt'] + (
                    f'\n当前任务ID={task_id}，revision={revision}。返回实际结果、建议和真实引用；未保存不得声称已保存。'
                )
                # Roles, skills and prompts remain configuration driven; names do not route work.
                if spec['type'] == 'deep-agent':
                    child = build_document_agent(
                        child_model, child_common, child_backend, middleware, prompt, spec['name'],
                    )
                else:
                    child = build_billing_agent(
                        child_model, child_common, middleware, prompt, spec['name'],
                    )
                subagents.append(dict(
                    name=spec['name'], description=spec['description'], runnable=child,
                ))
            stack = base_stack(
                task_id, revision, cap, backend, business, None,
                tools, provenance, outcome=True,
                scope=scope,
            )
            yield build_supervisor(model, common, backend, stack, subagents)
    finally:
        for owned_client in clients:
            await owned_client.aclose()
