"""Offline task contracts and native compiled specialist handoffs."""
import asyncio
import json
from langchain.messages import ToolMessage
from backend.middleware.dispatch import DispatchPolicy
from backend.tests.test_host import host, request_for


def contract(**changes):
    return dict(goal='核对费用金额', source_ids=['doc'], charge_ids=['c1'],
                questions=['c1金额与原文是否一致'], acceptance=['返回差异和真实引用'], **changes)


def strict_contract(host):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t['capability']['config']['agents']['agents'][1].update(
        delegation_contract=True))
    return repo, task


def test_delegation_rejects_vague_prompt_before_child_executes(host):
    repo, task = strict_contract(host)
    calls = []
    async def invoke(request):
        calls.append(request)
        return ToolMessage(content='ok', tool_call_id=request.tool_call['id'])
    result = asyncio.run(DispatchPolicy(task['id'], 1).awrap_tool_call(request_for(
        'task', subagent_type='billing-specialist', description='你去处理一下'), invoke))
    assert result.status == 'error' and not calls
    assert repo.get('task', task['id'])['usage']['tool_calls'] == 0


def test_host_injects_real_task_version_candidates_and_budget(host):
    _, task = strict_contract(host)
    seen = []
    async def invoke(request):
        seen.append(json.loads(request.tool_call['args']['description']))
        return ToolMessage(content='ok', tool_call_id=request.tool_call['id'])
    result = asyncio.run(DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('task',
        subagent_type='billing-specialist', description=json.dumps(contract())), invoke))
    assert result.status == 'success'
    envelope = seen[0]
    assert envelope['host']['task_id'] == task['id']
    assert envelope['host']['revision'] == 1
    assert envelope['host']['accounting_entity'] == 'Client'
    assert envelope['host']['model_call_limit'] == 4
    assert envelope['candidates'][0]['charge_id'] == 'c1'
    assert 'conversation' not in envelope and 'sources' not in envelope


def test_foreign_scope_is_rejected_without_dispatch(host):
    _, task = strict_contract(host)
    async def forbidden(request):
        raise AssertionError('foreign source reached child')
    payload = contract()
    payload['source_ids'] = ['foreign-source']
    result = asyncio.run(DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('task',
        subagent_type='billing-specialist', description=json.dumps(payload)), forbidden))
    assert result.status == 'error'
