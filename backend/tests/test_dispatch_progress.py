"""Offline dispatch policy regressions; no model, OCR or database requests."""
import asyncio
import json
from langchain.messages import ToolMessage
from backend.middleware.dispatch import DispatchPolicy
from backend.tests.test_host import host, request_for


DESCRIPTION = json.dumps(dict(goal='核对c1', source_ids=['doc'], charge_ids=['c1'],
    questions=['金额与原文是否一致'], acceptance=['返回差异和引用']))


def test_completed_expensive_call_is_not_reexecuted_after_graph_rebuild(host):
    repo, _, task = host
    executions = []
    async def invoke(request):
        executions.append(request.tool_call['name'])
        return ToolMessage(content='已接入材料', tool_call_id=request.tool_call['id'])
    async def run():
        await DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('intake_documents'), invoke)
        return await DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('intake_documents'), invoke)
    result = asyncio.run(run())
    assert executions == ['intake_documents']
    assert result.status == 'error'
    assert repo.get('task', task['id'])['automatic_stop']['code'] == 'NO_PROGRESS'


def test_new_candidate_allows_followup_delegation_with_same_goal(host):
    repo, _, task = host
    executions = []
    async def invoke(request):
        executions.append(1)
        return ToolMessage(content='结果', tool_call_id=request.tool_call['id'])
    async def run():
        args = dict(subagent_type='billing-specialist', description=DESCRIPTION)
        await DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('task', **args), invoke)
        repo.mutate('task', task['id'], lambda t: t['charges'][0].update(amount=101))
        return await DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('task', **args), invoke)
    result = asyncio.run(run())
    assert len(executions) == 2 and result.status == 'success'


def test_parallel_identical_delegation_executes_only_once(host):
    _, _, task = host
    executions = []
    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        async def invoke(request):
            executions.append(1)
            started.set()
            await release.wait()
            return ToolMessage(content='结果', tool_call_id=request.tool_call['id'])
        args = dict(subagent_type='billing-specialist', description=DESCRIPTION)
        first = asyncio.create_task(DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('task', **args), invoke))
        await asyncio.wait_for(started.wait(), 3)
        second = asyncio.create_task(DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('task', **args), invoke))
        await asyncio.sleep(0.05)
        release.set()
        return await asyncio.gather(first, second)
    results = asyncio.run(run())
    assert len(executions) == 1
    assert sum(m.status == 'error' for m in results) == 1


def test_transient_transport_failure_keeps_native_retry_available(host):
    _, _, task = host
    executions = []
    async def invoke(request):
        executions.append(1)
        if len(executions) == 1:
            raise ConnectionError('temporary')
        return ToolMessage(content='材料', tool_call_id=request.tool_call['id'])
    async def run():
        guard = DispatchPolicy(task['id'], 1)
        try:
            await guard.awrap_tool_call(request_for('intake_documents'), invoke)
        except ConnectionError:
            pass
        return await guard.awrap_tool_call(request_for('intake_documents'), invoke)
    result = asyncio.run(run())
    assert len(executions) == 2 and result.status == 'success'


def test_native_nested_interrupt_resumes_its_original_call(host):
    from langgraph.errors import GraphInterrupt
    _, _, task = host
    executions = []
    async def invoke(request):
        executions.append(1)
        if len(executions) == 1:
            raise GraphInterrupt()
        return ToolMessage(content='已恢复', tool_call_id=request.tool_call['id'])
    async def run():
        args = dict(subagent_type='billing-specialist', description=DESCRIPTION)
        try:
            await DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('task', **args), invoke)
        except GraphInterrupt:
            pass
        return await DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('task', **args), invoke)
    assert asyncio.run(run()).status == 'success'
    assert len(executions) == 2


def test_unknown_result_is_not_blindly_retried(host):
    _, _, task = host
    executions = []
    async def invoke(request):
        executions.append(1)
        raise RuntimeError('lost acknowledgement')
    async def run():
        try:
            await DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('intake_documents'), invoke)
        except RuntimeError:
            pass
        return await DispatchPolicy(task['id'], 1).awrap_tool_call(request_for('intake_documents'), invoke)
    assert asyncio.run(run()).status == 'error'
    assert len(executions) == 1
