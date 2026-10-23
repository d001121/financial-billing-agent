"""Offline task contracts and native compiled specialist handoffs."""
import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from langchain.messages import ToolMessage
from backend.agents import factory
from backend.extensions.skill_versions import skill_state, skill_module
from backend.middleware.dispatch import DispatchPolicy
from backend.middleware.delegation import constrain_child_call
from backend.harness.dispatch import PolicyDenied
from langchain.messages import HumanMessage
import pytest
from backend.tests.test_host import host, request_for, offline_model, proposed_call


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


def native_handoff(host, monkeypatch, content, *, save=False):
    repo, _, task = host
    monkeypatch.setattr(factory, 'repository', lambda: repo)
    @asynccontextmanager
    async def no_mcp(*args):
        yield [], {}
    monkeypatch.setattr(factory, 'connected_tools', no_mcp)
    parent, child = [], []
    role = 'document-specialist' if save else 'billing-specialist'
    def respond(body):
        system = str(body['messages'][0]['content'])
        if ('你是按需调用的文档阅读专家' if save else '你是按需调用的账单核验专家') in system:
            child.append(body)
            assert len(child) <= (2 if save else 1), 'handoff format must not cause another model request'
            if save and len(child) == 1:
                return proposed_call('save_document_extraction', dict(result=dict(charges=[dict(
                    charge_id='c1', amount=100)])), 'child-save')
            return dict(role='assistant', content=content)
        parent.append(body)
        if len(parent) == 1:
            return proposed_call('task', dict(subagent_type=role, description=json.dumps(contract())), 'delegate')
        return dict(role='assistant', content='已查看核验结果。')
    async def run():
        _, bootstrap = offline_model(monkeypatch, task['id'], respond)
        await bootstrap.aclose()
        config = dict(configurable=dict(task_id=task['id'], task_revision=1, task_budget_id='handoff'))
        async with factory.make_graph(config, SimpleNamespace(execution_runtime=None)) as graph:
            await graph.ainvoke({**skill_state(task['capability'], task),
                'messages': [dict(role='user', content='核对账单，主会话敏感标记不传专家')]}, config)
    asyncio.run(run())
    tool = next(m for body in parent[1:] for m in body['messages']
                if m.get('role') == 'tool' and m.get('tool_call_id') == 'delegate')
    return json.loads(tool['content']), child, repo.get('task', task['id'])


def report(**changes):
    return dict(status='done', summary='未发现具体差异', saved=False,
                proposals=[], issues=[], evidence_refs=[]) | changes


def test_native_invalid_handoff_is_blocked_without_format_retry(host, monkeypatch):
    value, child, _ = native_handoff(host, monkeypatch, '已核验没有问题')
    assert value['status'] == 'blocked'
    assert value['issues'][0]['code'] == 'INVALID_HANDOFF'
    assert len(child) == 1


def test_native_handoff_cannot_claim_unperformed_save(host, monkeypatch):
    value, _, _ = native_handoff(host, monkeypatch, json.dumps(report(saved=True)))
    assert value['status'] == 'blocked' and value['saved'] is False
    assert any(i['code'] == 'UNSAVED_CLAIM' for i in value['issues'])


def test_native_handoff_rejects_unknown_reference(host, monkeypatch):
    value, _, _ = native_handoff(host, monkeypatch, json.dumps(report(evidence_refs=['invented-ref'])))
    assert value['status'] == 'blocked'
    assert any(i['code'] == 'CITATION_UNKNOWN' for i in value['issues'])


def test_native_valid_handoff_has_host_version_usage_and_isolated_context(host, monkeypatch):
    value, child, saved = native_handoff(host, monkeypatch, json.dumps(report()))
    assert value['status'] == 'done' and value['saved'] is False
    assert value['task_id'] == saved['id'] and value['revision'] == 1
    assert value['resource_usage']['role_run_model_calls'] == 1
    assert '主会话敏感标记' not in str(child)


def test_native_saved_handoff_matches_actual_save_receipt(host, monkeypatch):
    _, _, task = host
    refs = skill_module('document-extraction', task['capability']['version']).citation_index(task)
    value, child, saved = native_handoff(host, monkeypatch,
        json.dumps(report(saved=True, evidence_refs=[next(iter(refs))])), save=True)
    assert value['status'] == 'done' and value['saved'] is True, json.dumps(dict(
        report=value, history=saved.get('dispatch_history'),
        tools=[m for b in child for m in b['messages'] if m.get('role') == 'tool']), ensure_ascii=False)
    assert len(child) == 2


def test_native_modification_proposal_requires_real_references(host, monkeypatch):
    value, _, _ = native_handoff(host, monkeypatch, json.dumps(report(proposals=[dict(
        charge_id='c1', field='amount', value=101)])))
    assert value['status'] == 'blocked'
    assert any(i['code'] == 'CITATION_REQUIRED' for i in value['issues'])


@pytest.mark.parametrize('args', [dict(result=dict(charges=[dict(charge_id='foreign', amount=100)])),
    dict(result={}, replace=True), dict(result='{"charges":[]}')])
def test_document_expert_cannot_escape_scope_or_replace_whole_bill(args):
    request = request_for('save_document_extraction', **args)
    request = request.override(state=dict(messages=[HumanMessage(content=json.dumps(dict(
        contract_version=1, contract=contract(), host={})))]))
    with pytest.raises(PolicyDenied):
        constrain_child_call(request)


def test_default_child_read_opens_only_delegated_sources():
    request = request_for('read_materials')
    request = request.override(state=dict(messages=[HumanMessage(content=json.dumps(dict(
        contract_version=1, contract=contract(), host={})))]))
    bounded = constrain_child_call(request)
    assert bounded.tool_call['args']['windows'] == [dict(source_id='doc')]


def test_exhausted_expert_is_rejected_before_delegation_starts(host):
    repo, task = strict_contract(host)
    repo.mutate('task', task['id'], lambda t: t['usage'].update(model_calls=4,
        run_budget=dict(id='limited', model_calls=4, experts={'billing-specialist':4})))
    async def forbidden(request):
        raise AssertionError('exhausted expert started')
    result = asyncio.run(DispatchPolicy(task['id'], 1,
        scope=dict(id='limited', revision=1, role='supervisor')).awrap_tool_call(request_for('task',
        subagent_type='billing-specialist', description=json.dumps(contract())), forbidden))
    assert result.status == 'error'
    assert repo.get('task', task['id'])['usage']['tool_calls'] == 0
