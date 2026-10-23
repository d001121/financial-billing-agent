"""Targeted revision/turn integration; native LangChain, isolated storage/network."""
import asyncio
import os
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from deepagents.backends import StateBackend
import pytest

from backend.api import app, task_runtime
from backend.middleware import feedback as feedback_middleware
from backend.middleware.assembly import base_stack
from backend.agents.supervisor.agent import build_supervisor
from backend.tools import artifacts, skill_bindings
from backend.tests.test_host import host, offline_model, proposed_call


def server(monkeypatch, repo, *, pending=False, fail=False):
    monkeypatch.setattr(task_runtime, 'repository', lambda: repo)
    state = dict(checkpoint={'checkpoint_id': 'saved'}, next=['tools'] if pending else [], values={},
                 tasks=[dict(interrupts=[dict(id='question', value={'question': 'who pays?'})])] if pending else [])
    post = AsyncMock(side_effect=RuntimeError('unavailable') if fail else None,
                     return_value={'run_id': 'new-run'})
    sdk = SimpleNamespace(http=SimpleNamespace(post=post),
        threads=SimpleNamespace(get_state=AsyncMock(return_value=state)),
        runs=SimpleNamespace(get=AsyncMock(return_value={'status': 'success'})))
    monkeypatch.setattr(task_runtime, 'sdk', lambda: sdk)
    from backend.api.routes import tasks as tasks_route
    monkeypatch.setattr(tasks_route, 'sdk', lambda: sdk)
    repo.mutate('task', 'task-1', lambda t: t.update(thread_id='same-thread', run_id='old-run', status='completed_with_gaps'))
    return sdk, post


def revise(client):
    return client.patch('/api/tasks/task-1/revision', json=dict(expected_revision=1,
        accounting_entity='Client', operations=[], reason='核对第一页，Client是本次记账主体'))


def test_revision_applies_deterministically_without_an_agent_turn(host, monkeypatch):
    repo, _, original = host
    _, post = server(monkeypatch, repo)
    before = repo.get('task', 'task-1')
    client = TestClient(app)
    response = revise(client)
    assert response.status_code == 200, response.text
    task = response.json()
    assert task['revision'] == 2
    assert task['status'] in ('completed', 'completed_with_gaps')
    assert task.get('feedback') is None
    assert post.await_count == 0
    assert task['sources'] == before['sources'] and task['usage'] == before['usage']
    assert task['records'][0]['human_confirmed']['financial_attributes.accounting_entity']['value'] == 'Client'
    assert client.patch('/api/tasks/task-1/revision', json=dict(expected_revision=1,
        operations=[], accounting_entity='Wrong', reason='stale')).status_code == 409


@pytest.mark.parametrize('condition', ['interrupt', 'paused', 'budget', 'dispatch_failure', 'state_failure'])
def test_feedback_preserves_edit_and_waits_or_retries(host, monkeypatch, condition):
    """Legacy pending feedback can still be resumed through the control action."""
    repo, _, _ = host
    sdk, post = server(monkeypatch, repo, pending=condition == 'interrupt', fail=condition == 'dispatch_failure')
    if condition == 'state_failure':
        sdk.threads.get_state.side_effect = RuntimeError('checkpoint unavailable')
    if condition == 'paused':
        repo.mutate('task', 'task-1', lambda t: t.update(control='paused'))
    if condition == 'budget':
        repo.mutate('task', 'task-1', lambda t: t['usage'].update(model_calls=t['capability']['config']['runtime']['model_calls']))
    repo.mutate('task', 'task-1', lambda t: t.update(revision=2, feedback=dict(
        revision=2, state='pending', model_seen=False, reason='test', changes=[])))
    client = TestClient(app)
    result = client.post('/api/tasks/task-1/control', json={'action': 'resume'})
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved['revision'] == 2
    assert saved['feedback']['state'] in {'waiting', 'failed', 'blocked', 'running'}



def test_native_interrupt_resume_sees_current_revision_feedback(host, monkeypatch):
    from langchain.agents import create_agent
    from langchain.agents.middleware import HumanInTheLoopMiddleware
    from langgraph.types import Command
    from backend.tools.human_input import human_input_tool
    repo, _, task = host
    calls = []
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return proposed_call('ask_user', {'question': '请说明主体'}, 'subject')
        assert '补充当前主体' in str(body['messages'])
        assert 'revision' in str(body['messages'])
        return dict(role='assistant', content='收到当前版本的主体，继续核对。')
    async def run():
        model, client = offline_model(monkeypatch, 'task-1', respond)
        graph = create_agent(model, tools=[human_input_tool()], checkpointer=InMemorySaver(), middleware=[
            HumanInTheLoopMiddleware(interrupt_on={'ask_user': {'allowed_decisions':['respond']}}, interrupt_mode='per_call'),
            feedback_middleware.RevisionFeedback('task-1', 2)])
        config = {'configurable': {'thread_id': 'pending-subject'}}
        try:
            interrupted = await graph.ainvoke({'messages':[{'role':'user','content':'提取'}]}, config)
            entry = interrupted['__interrupt__'][0]
            repo.mutate('task', 'task-1', lambda t: t.update(revision=2, feedback=dict(
                revision=2, state='waiting', model_seen=False, reason='补充当前主体', changes=[], accounting_entity='Client')))
            result = await graph.ainvoke(Command(resume={entry.id:{'type':'respond','message':'Client'}}), config)
            assert not result.get('__interrupt__')
        finally:
            await client.aclose()
    asyncio.run(run())
    assert repo.get('task', 'task-1')['feedback']['model_seen']
    assert len(calls) == 2


def test_intake_reuses_persisted_supplemented_materials(host, monkeypatch):
    repo, _, task = host
    def setup(t):
        t['asset_ids'] = ['original-asset']
        t['sources'][0]['blocks'].append(dict(anchor='supplement', text='Already read extra context'))
        t['intake'] = [dict(asset_id='original-asset', sources=deepcopy(t['sources']), issues=[],
                            ocr_response_format=os.environ.get('OCR_RESPONSE_FORMAT', 'text'),
                            ocr_text_pointer=t.get('ocr_text_pointer'))]
    repo.mutate('task', 'task-1', setup)
    before = repo.get('task', 'task-1')
    # No asset object/network exists: any reparsing would fail this test.
    _, business = skill_bindings.tools_for('task-1', task['capability'])
    intake = next(t for t in business if t.name == 'intake_documents')
    asyncio.run(intake.ainvoke({'include_content':False}))
    saved = repo.get('task', 'task-1')
    assert saved['sources'] == before['sources']
    assert saved['intake'] == before['intake']


def test_explicit_resume_delivers_historical_edit_without_migrating_capability(host, monkeypatch):
    repo, _, task = host
    sdk, post = server(monkeypatch, repo)
    repo.mutate('task', 'task-1', lambda t: t.update(revision=2, reason='历史人工补充主体',
        history=[dict(revision=2, history=[dict(op='set',charge_id='c1',field='financial_attributes.accounting_entity',
                                                before=None,after='Client')])]))
    result = TestClient(app).post('/api/tasks/task-1/control', json={'action':'resume'})
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved['revision'] == 2 and saved['capability'] == task['capability']
    assert saved['feedback']['reason'] == '历史人工补充主体'
    assert post.await_count == 1


def test_native_failure_keeps_feedback_retryable(host, monkeypatch):
    repo, _, task = host
    sdk, _ = server(monkeypatch, repo)
    repo.mutate('task', 'task-1', lambda t: t.update(status='running',
        feedback=dict(revision=1,state='running',model_seen=True,reason='test',changes=[])))
    sdk.runs.get.return_value = {'status':'error'}
    result = asyncio.run(task_runtime.sync_task(repo.get('task', 'task-1')))
    assert result['status'] == 'recovery_required'
    assert result['feedback']['state'] == 'failed'
    assert result['records'] == task['records']
