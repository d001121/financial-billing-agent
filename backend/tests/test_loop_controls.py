"""Small offline regressions for Bill3's repair loop. No external requests."""
import asyncio
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

import pytest
from deepagents.backends import StateBackend
from langchain.agents import create_agent

from backend.harness import budget
from backend.harness.dispatch import PolicyDenied
from backend.middleware.assembly import base_stack
from backend.middleware.dispatch import DispatchPolicy
from backend.extensions.skill_versions import skill_module, skill_state
from backend.tools.skill_bindings import tools_for
from backend.tests.test_host import host, offline_model, proposed_call, request_for
from backend.tools.review import settle_saved
from backend.agents import factory
from backend.agents.supervisor.agent import build_supervisor
from contextlib import asynccontextmanager
from types import SimpleNamespace
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from uuid import uuid4
from backend.api import task_runtime
from unittest.mock import AsyncMock


def save_tool(task):
    return next(t for t in tools_for(task['id'], task['capability'])[1]
                if t.name == 'save_document_extraction')


def test_repeated_candidate_really_stops_and_opens_entity_question(host, monkeypatch):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t.update(status='running', accounting_entity=None))
    calls = []
    candidate = dict(charges=[dict(charge_id='c1', charge_item='THC', amount=100, currency='USD')])
    def respond(body):
        calls.append(body)
        assert len(calls) <= 2, 'repair denial must prevent the next model HTTP request'
        return proposed_call('save_document_extraction', dict(result=candidate), f'save-{len(calls)}')
    async def run():
        model, client = offline_model(monkeypatch, task['id'], respond)
        try:
            common, business = tools_for(task['id'], task['capability'])
            graph = create_agent(model, tools=common, middleware=base_stack(
                task['id'], 1, task['capability'], StateBackend(), business, outcome=True))
            return await graph.ainvoke({**skill_state(task['capability'], task),
                'messages': [dict(role='user', content='核对当前账单')]})
        finally:
            await client.aclose()
    result = asyncio.run(run())
    saved = repo.get('task', task['id'])
    assert len(calls) == 2
    assert result.get('__interrupt__'), {k: saved.get(k) for k in ('automatic_stop', 'status', 'validation', 'review_request')}
    assert saved['review_request']['state'] == 'pending'
    assert saved['automatic_stop']['code'] == 'NO_PROGRESS'
    assert saved['charges'][0]['amount'] == 100
    assert saved['approval'] is None


def test_evidence_repair_cannot_destroy_supported_amount_and_currency(host):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t['sources'][0]['blocks'].append(
        dict(anchor='fee-only', text='THC', authoritative=True)))
    before = repo.get('task', task['id'])
    with pytest.raises(PolicyDenied, match='证据'):
        save_tool(task).invoke(dict(result=dict(charges=[dict(charge_id='c1',
            evidence=[dict(source_id='doc', anchor='fee-only', quote='THC',
                           fields=['charge_item', 'amount', 'currency'])])])) )
    after = repo.get('task', task['id'])
    assert after['charges'] == before['charges']
    assert after['candidate_digests'] if 'candidate_digests' in after else True


def test_explicit_missing_value_stays_null(host):
    repo, _, task = host
    save_tool(task).invoke(dict(result=dict(charges=[dict(charge_id='c1', amount=None,
                                                        currency=None)])))
    row = repo.get('task', task['id'])['charges'][0]
    assert row['amount'] is None and row['currency'] is None


def test_billing_reviewer_has_no_write_tools(host):
    _, _, task = host
    spec = next(s for s in task['capability']['config']['agents']['agents']
                if s['name'] == 'billing-specialist')
    common, business = tools_for(task['id'], task['capability'], spec['skills'],
                                 allowed_tools=spec['tools'])
    assert 'read_task_context' in {t.name for t in common}
    assert 'read_materials' in {t.name for t in business}
    assert not ({'save_document_extraction', 'reconcile_task_charges', 'ask_user'} &
                {t.name for t in common + business})


def test_reviewer_cannot_bypass_allowlist_at_dispatch(host):
    _, _, task = host
    guard = DispatchPolicy(task['id'], 1, allowed_tools=['read_task_context'])
    async def forbidden(request):
        pytest.fail('readonly expert executed a write')
    message = asyncio.run(guard.awrap_tool_call(request_for('save_document_extraction'), forbidden))
    assert message.status == 'error'


def test_expert_budget_counts_real_requests_and_leaves_parent_reserve(host):
    repo, _, task = host
    scope = dict(id='run-1', revision=1, role='reviewer')
    for _ in range(4):
        budget.consume(task['id'], 'model_calls', scope=scope)
    with pytest.raises(PolicyDenied):
        budget.consume(task['id'], 'model_calls', scope=scope)
    assert repo.get('task', task['id'])['usage']['model_calls'] == 4
    assert repo.get('task', task['id'])['status'] != 'budget_exhausted'
    parent = dict(scope, role='supervisor')
    for _ in range(12):
        budget.consume(task['id'], 'model_calls', scope=parent)
    with pytest.raises(PolicyDenied):
        budget.consume(task['id'], 'model_calls', scope=parent)
    assert repo.get('task', task['id'])['usage']['model_calls'] == 16


def test_parallel_experts_share_atomic_run_budget(host):
    repo, _, task = host
    def attempt(index):
        try:
            budget.consume(task['id'], 'model_calls', scope=dict(id='parallel', revision=1, role=f'child-{index}'))
            return True
        except PolicyDenied:
            return False
    with ThreadPoolExecutor(max_workers=8) as workers:
        allowed = list(workers.map(attempt, range(24)))
    assert sum(allowed) == 14  # 16 shared, two calls reserved for the parent
    assert repo.get('task', task['id'])['usage']['model_calls'] == 14


def test_task_total_does_not_reset_with_new_run(host):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t['usage'].update(model_calls=23))
    budget.consume(task['id'], 'model_calls', scope=dict(id='last', revision=1, role='supervisor'))
    with pytest.raises(PolicyDenied):
        budget.consume(task['id'], 'model_calls', scope=dict(id='new', revision=1, role='supervisor'))
    assert repo.get('task', task['id'])['usage']['model_calls'] == 24


def test_stopped_valid_bill_never_claims_automatic_approval(host):
    repo, _, task = host
    def supported(t):
        t['sources'][0]['blocks'][0].update(text='THC USD 100 INV-1', kind='cell')
        for row in (t['charges'][0], t['records'][0]):
            row['evidence'] = [dict(source_id='doc', anchor='p1', quote='THC USD 100 INV-1')]
    repo.mutate('task', task['id'], supported)
    assert settle_saved(task['id'])['auto_review'] is not None
    repo.mutate('task', task['id'], lambda t: t.update(automatic_stop=dict(
        revision=1, code='NO_PROGRESS', message='相同候选无进展')))
    settled = settle_saved(task['id'])
    assert settled['auto_review'] is None
    assert settled['status'] == 'completed_with_gaps'


def test_two_repairs_then_actual_stop_even_with_different_candidates(host, monkeypatch):
    repo, _, task = host
    calls = []
    def respond(body):
        calls.append(body)
        assert len(calls) <= 3
        return proposed_call('save_document_extraction', dict(result=dict(charges=[dict(
            charge_id='c1', document_date=f'2026-10-{20 + len(calls)}')])), str(len(calls)))
    async def run():
        model, client = offline_model(monkeypatch, task['id'], respond)
        try:
            graph = create_agent(model, tools=[save_tool(task)],
                                 middleware=[DispatchPolicy(task['id'], 1)])
            return await graph.ainvoke({'messages': [dict(role='user', content='核对日期')]})
        finally:
            await client.aclose()
    asyncio.run(run())
    saved = repo.get('task', task['id'])
    assert saved['automatic_stop']['code'] == 'REPAIR_LIMIT'
    assert saved['charges'][0]['document_date'] == '2026-10-22'
    assert len(calls) == 3


def test_native_child_limit_returns_blocked_to_parent(host, monkeypatch):
    repo, _, task = host
    monkeypatch.setattr(factory, 'repository', lambda: repo)
    @asynccontextmanager
    async def no_mcp(*args):
        yield [], {}
    monkeypatch.setattr(factory, 'connected_tools', no_mcp)
    parent, child = [], []
    def respond(body):
        system = str(body['messages'][0]['content'])
        if '你是按需调用的账单核验专家' in system:
            child.append(body)
            assert len(child) <= 4
            return proposed_call('read_task_context', {}, f'child-{len(child)}')
        parent.append(body)
        if len(parent) == 1:
            return proposed_call('task', dict(subagent_type='billing-specialist', description=json.dumps(dict(
                goal='核对c1', source_ids=['doc'], charge_ids=['c1'], questions=['金额是否为100 USD'],
                acceptance=['返回差异和真实引用']))), 'delegate')
        assert 'blocked' in str(body['messages'])
        return dict(role='assistant', content='专家额度已到，已保留现有结果。')
    async def run():
        _, bootstrap = offline_model(monkeypatch, task['id'], respond)
        await bootstrap.aclose()
        config = dict(configurable=dict(task_id=task['id'], task_revision=1, task_budget_id='native-child'))
        async with factory.make_graph(config, SimpleNamespace(execution_runtime=None)) as graph:
            return await graph.ainvoke({**skill_state(task['capability'], task),
                'messages': [dict(role='user', content='核对账单')]}, config)
    asyncio.run(run())
    # Parent observes final verification once through the existing stop hook.
    assert len(child) == 4 and len(parent) == 3
    saved = repo.get('task', task['id'])
    assert saved['usage']['model_calls'] == 7
    assert saved['usage']['run_budget']['experts']['billing-specialist'] == 4
    assert saved['charges'] == task['charges']


def test_hidden_model_request_cannot_bypass_scope_or_leave_run_error(host, monkeypatch):
    repo, _, task = host
    scope = dict(id='hidden', revision=1, role='reviewer')
    for _ in range(4):
        budget.consume(task['id'], 'model_calls', scope=scope)
    async def run():
        _, bootstrap = offline_model(monkeypatch, task['id'], lambda b: pytest.fail('blocked HTTP reached transport'))
        await bootstrap.aclose()
        from backend.infrastructure.models import make_model
        from langchain.agents.middleware import ModelRequest
        from langchain.messages import HumanMessage
        model, client = make_model(task['id'], budget_scope=scope)
        try:
            guard = DispatchPolicy(task['id'], 1, scope=scope)
            # Call the wrap boundary directly, simulating a request arriving
            # after preflight (retry/summary/concurrent child).
            async def handler(request):
                return await model.ainvoke([HumanMessage(content='核验')])
            return await guard.awrap_model_call(SimpleNamespace(), handler)
        finally:
            await client.aclose()
    result = asyncio.run(run())
    assert 'blocked' in result.result[0].content
    assert repo.get('task', task['id'])['usage']['model_calls'] == 4


def test_nested_replace_is_reported_instead_of_silently_ignored(host):
    _, _, task = host
    from pydantic import ValidationError
    module = skill_module('document-extraction', task['capability']['version'])
    with pytest.raises(ValidationError, match='replace'):
        module.ExtractionResult.model_validate(dict(charges=[], replace=True))


@pytest.mark.parametrize('failed', [False, True])
def test_authorized_new_run_clears_stop_only_on_accepted_dispatch(host, monkeypatch, failed):
    repo, _, task = host
    stop = dict(revision=1, code='NO_PROGRESS', message='无进展')
    repo.mutate('task', task['id'], lambda t: t.update(automatic_stop=stop, thread_id='thread'))
    post = AsyncMock(side_effect=RuntimeError('rejected') if failed else None,
                     return_value=dict(run_id='new-run'))
    monkeypatch.setattr(task_runtime, 'repository', lambda: repo)
    monkeypatch.setattr(task_runtime, 'sdk', lambda: SimpleNamespace(http=SimpleNamespace(post=post)))
    if failed:
        with pytest.raises(RuntimeError, match='rejected'):
            asyncio.run(task_runtime.start_run(repo.get('task', task['id']), message='继续核对'))
        assert repo.get('task', task['id'])['automatic_stop'] == stop
    else:
        asyncio.run(task_runtime.start_run(repo.get('task', task['id']), message='继续核对'))
        assert not repo.get('task', task['id']).get('automatic_stop')
        assert post.call_args.kwargs['json']['config']['configurable']['task_budget_id']
    assert repo.get('task', task['id'])['usage']['model_calls'] == 0


def test_supported_fact_change_accepted_without_inventing_values(host):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t['sources'][0]['blocks'].append(
        dict(anchor='correct', text='THC EUR 90', kind='cell')))
    assert save_tool(task).invoke(dict(result=dict(charges=[dict(charge_id='c1', amount=90,
        currency='EUR', evidence=[dict(source_id='doc', anchor='correct', quote='THC EUR 90')])])) )['saved']
    row = repo.get('task', task['id'])['charges'][0]
    assert row['amount'] == 90 and row['currency'] == 'EUR'


def test_stopped_native_review_can_resume_and_defer_without_extraction(host, monkeypatch):
    from backend.tests.test_conversation import skip_structured
    skip_structured(monkeypatch)
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t.update(status='running'))
    calls = []
    reply_id = str(uuid4())
    def respond(body):
        calls.append(body)
        if len(calls) <= 2:
            return proposed_call('save_document_extraction', dict(result=dict(charges=[dict(
                charge_id='c1', amount=100)])), str(len(calls)))
        if len(calls) == 3:
            return proposed_call('record_review_decision', dict(reply_id=reply_id, action='defer'), 'defer')
        assert len(calls) == 4
        return dict(role='assistant', content='已暂缓，保留费用和证据。')
    async def run():
        model, http = offline_model(monkeypatch, task['id'], respond)
        saver = InMemorySaver()
        common, business = tools_for(task['id'], task['capability'])
        graph = create_agent(model, tools=common, middleware=base_stack(
            task['id'], 1, task['capability'], StateBackend(), business, outcome=True), checkpointer=saver)
        config = dict(configurable=dict(thread_id='stop-resume'))
        try:
            first = await graph.ainvoke({**skill_state(task['capability'], task),
                'messages': [dict(role='user', content='核对')]}, config)
            pending = first['__interrupt__'][0]
            def human(t):
                t.pop('automatic_stop', None)  # start_run performs this for an authorized reply
                t['conversation'] = [dict(id=reply_id, text='暂缓', revision=1,
                    state='starting', model_seen=False, kind='conversation_review',
                    question=pending.value['description'], interrupt_id=pending.id)]
            repo.mutate('task', task['id'], human)
            return await graph.ainvoke(Command(resume={pending.id: dict(reply_id=reply_id,
                                                     expected_revision=1)}), config)
        finally:
            await http.aclose()
    result = asyncio.run(run())
    assert not result.get('__interrupt__')
    assert repo.get('task', task['id'])['status'] == 'review_deferred', (len(calls),
        repo.get('task', task['id']).get('conversation'),
        [(m.type, str(m.content)[:120]) for m in result['messages'][-5:]])
    assert len(calls) == 4


def test_projected_budget_check_sees_persisted_stop(host, monkeypatch):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t.update(automatic_stop=dict(
        revision=1, code='NO_PROGRESS', message='停止事实')))
    def projected(kind, identity, fields, transform, **kwargs):
        def update(current):
            data = {k: deepcopy(current.get(k)) for k in ('id', 'revision', *fields)}
            transform(data)
            current.update(data)
        return repo.mutate(kind, identity, update, **kwargs)
    monkeypatch.setattr(repo, 'mutate_fields', projected, raising=False)
    with pytest.raises(PolicyDenied, match='停止事实'):
        budget.consume(task['id'], 'model_calls')
    assert repo.get('task', task['id'])['usage']['model_calls'] == 0


def test_native_parent_run_limit_ends_without_after_agent_model_bounce(host, monkeypatch):
    repo, _, task = host
    scope = dict(id='parent-limit', revision=1, role='supervisor')
    seen = []
    def respond(body):
        seen.append(body)
        assert len(seen) <= 16
        return proposed_call('read_task_context', {}, f'read-{len(seen)}')
    async def run():
        _, bootstrap = offline_model(monkeypatch, task['id'], respond)
        await bootstrap.aclose()
        from backend.infrastructure.models import make_model
        model, http = make_model(task['id'], budget_scope=scope)
        try:
            common, business = tools_for(task['id'], task['capability'])
            graph = create_agent(model, tools=common, middleware=base_stack(task['id'], 1,
                task['capability'], StateBackend(), business, outcome=True, scope=scope))
            return await graph.ainvoke({**skill_state(task['capability'], task),
                'messages': [dict(role='user', content='核对')]})
        finally:
            await http.aclose()
    result = asyncio.run(run())
    saved = repo.get('task', task['id'])
    assert len(seen) == saved['usage']['model_calls'] == 16
    assert result.get('__interrupt__')
    assert saved['automatic_stop']['code'] == 'RUN_BUDGET'
    assert saved['auto_review'] is None


def test_child_repair_stop_prevents_parent_resaving_whole_bill(host, monkeypatch):
    repo, _, task = host
    monkeypatch.setattr(factory, 'repository', lambda: repo)
    @asynccontextmanager
    async def no_mcp(*args):
        yield [], {}
    monkeypatch.setattr(factory, 'connected_tools', no_mcp)
    parent, child = [], []
    def respond(body):
        if '你是按需调用的文档阅读专家' in str(body['messages'][0]['content']):
            child.append(body)
            assert len(child) <= 2
            return proposed_call('save_document_extraction', dict(result=dict(charges=[dict(
                charge_id='c1', amount=100)])), f'child-{len(child)}')
        parent.append(body)
        assert len(parent) == 1, 'parent must stop before attempting a whole-bill rewrite'
        return proposed_call('task', dict(subagent_type='document-specialist',
            description=json.dumps(dict(goal='核对c1', source_ids=['doc'], charge_ids=['c1'],
                questions=['核对已保存金额'], acceptance=['返回差异和真实引用']))), 'delegate')
    async def run():
        _, bootstrap = offline_model(monkeypatch, task['id'], respond)
        await bootstrap.aclose()
        config = dict(configurable=dict(task_id=task['id'], task_revision=1, task_budget_id='child-stop'))
        async with factory.make_graph(config, SimpleNamespace(execution_runtime=None)) as graph:
            return await graph.ainvoke({**skill_state(task['capability'], task),
                'messages': [dict(role='user', content='核对')]}, config)
    result = asyncio.run(run())
    assert len(child) == 2 and len(parent) == 1
    assert result.get('__interrupt__')
    assert repo.get('task', task['id'])['automatic_stop']['code'] == 'NO_PROGRESS'
