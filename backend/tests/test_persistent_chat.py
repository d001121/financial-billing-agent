"""Bounded offline checks for persistent chat on the existing native thread."""
import asyncio
from copy import deepcopy
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
import pytest

from backend.api import app
from backend.middleware.conversation import ConversationReplies
from backend.middleware.outcome import TaskOutcome
from backend.middleware.reply_decision import ReplyDecisionMiddleware
from backend.tests.test_conversation import setup_server
from backend.tests.test_host import host, offline_model, proposed_call
from backend.agents.supervisor.agent import build_supervisor
from backend.middleware.assembly import base_stack
from backend.tools import skill_bindings
from backend.extensions.skill_versions import skill_state
from deepagents.backends import StateBackend


def chat_server(monkeypatch, repo):
    sdk, post = setup_server(monkeypatch, repo)
    sdk.threads.get_state.return_value = dict(tasks=[], next=[], values={}, checkpoint={'checkpoint_id': 'saved'})
    sdk.runs.get.return_value = {'status': 'success'}
    post.return_value = {'run_id': 'chat-run'}
    repo.mutate('task', 'task-1', lambda t: t.update(status='review_deferred'))
    return sdk, post


def chat_request():
    return dict(expected_revision=1, reply_id=str(uuid4()), text='解释一下这些费用', conversational=True)


@pytest.mark.parametrize('status', ['review_deferred', 'recovery_required'])
def test_chat_uses_same_thread_and_replay_does_not_dispatch(host, monkeypatch, status):
    repo, _, _ = host
    _, post = chat_server(monkeypatch, repo)
    repo.mutate('task', 'task-1', lambda t: t.update(status=status))
    request = chat_request()
    client = TestClient(app)
    result = client.post('/api/tasks/task-1/reply', json=request)
    assert result.status_code == 200, result.text
    assert post.call_args.args == ('/threads/same-thread/runs',)
    payload = post.call_args.kwargs['json']
    assert 'command' not in payload
    assert payload['input']['messages'][0]['id'] == 'chat-user-' + request['reply_id']
    assert payload['input']['messages'][0]['content'].startswith(request['text'])
    assert result.json()['status'] == status
    assert result.json()['conversation'][-1]['kind'] == 'chat'
    assert client.post('/api/tasks/task-1/reply', json=request).status_code == 200
    assert post.await_count == 1
    assert client.post('/api/tasks/task-1/reply', json={**request, 'text': 'different'}).status_code == 409


@pytest.mark.parametrize('case', ['stale', 'paused', 'budget', 'running', 'native_pending', 'review_pending', 'active_reply'])
def test_blocked_chat_never_dispatches_or_changes_bill(host, monkeypatch, case):
    repo, _, task = host
    sdk, post = chat_server(monkeypatch, repo)
    request = chat_request()
    if case == 'stale': request['expected_revision'] = 0
    if case == 'paused': repo.mutate('task', 'task-1', lambda t: t.update(control='paused'))
    if case == 'budget': repo.mutate('task', 'task-1', lambda t: t['usage'].update(model_calls=t['capability']['config']['runtime']['model_calls']))
    if case == 'running': sdk.runs.get.return_value = {'status': 'running'}
    if case == 'native_pending': sdk.threads.get_state.return_value['tasks'] = [dict(interrupts=[dict(id='actual', value={})])]
    if case == 'review_pending': repo.mutate('task', 'task-1', lambda t: t.update(review_request=dict(state='pending')))
    if case == 'active_reply': repo.mutate('task', 'task-1', lambda t: t.update(conversation=[dict(id='other', state='starting')]))
    result = TestClient(app).post('/api/tasks/task-1/reply', json=request)
    assert result.status_code == 409, result.text
    assert post.await_count == 0
    assert repo.get('task', 'task-1')['records'] == task['records']


def test_failed_dispatch_retains_message_and_can_retry(host, monkeypatch):
    repo, _, _ = host
    _, post = chat_server(monkeypatch, repo)
    post.side_effect = RuntimeError('offline dispatch failure')
    request = chat_request()
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post('/api/tasks/task-1/reply', json=request).status_code == 500
    saved = repo.get('task', 'task-1')['conversation'][-1]
    assert saved['state'] == 'failed' and saved['text'] == request['text']
    post.side_effect = None
    assert client.post('/api/tasks/task-1/reply', json=request).status_code == 200
    assert len(repo.get('task', 'task-1')['conversation']) == 1


@pytest.mark.parametrize('edit', [False, True])
def test_native_chat_answers_or_applies_explicit_edit(host, monkeypatch, edit):
    repo, _, task = host
    reply_id = str(uuid4())
    approval = {'revision': 1, 'decision': 'approved'}
    repo.mutate('task', 'task-1', lambda t: t.update(status='completed', approval=approval,
        export={'kept': True}, conversation=[dict(id=reply_id, text='改金额为65美元' if edit else '解释费用',
        kind='chat', conversational=True, question='', interrupt_id='', revision=1, state='starting', model_seen=False)]))
    before = repo.get('task', 'task-1')
    seen = []
    def respond(request):
        seen.append(request)
        if edit and len(seen) == 1:
            return proposed_call('record_review_decision', dict(reply_id=reply_id, action='edit',
                operations=[dict(op='set', charge_id='c1', field='amount', value=65)]), 'edit')
        return dict(role='assistant', content='THC是码头操作费。' if not edit else '已理解修改。')
    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        backend = StateBackend()
        common, business = skill_bindings.tools_for('task-1', task['capability'])
        graph = build_supervisor(model, common, backend,
            base_stack('task-1', 1, task['capability'], backend, business, outcome=True), [])
        try:
            return await graph.ainvoke({**skill_state(task['capability'], before),
                'messages': [{'role': 'user', 'id': 'chat-user-' + reply_id, 'content': before['conversation'][0]['text']}]})
        finally:
            await http.aclose()
    result = asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert saved['conversation'][0]['state'] == 'completed'
    assert not result.get('__interrupt__')
    if edit:
        assert len(seen) == 2
        assert saved['revision'] == 2 and saved['approval'] is None
        assert saved['validation']['revision'] == 2
        assert saved['records'][0]['charge_details']['amount'] == 65
        assert saved['sources'] == task['sources']
    else:
        assert len(seen) == 1
        assert result['messages'][-1].content == 'THC是码头操作费。'
        for key in ('revision', 'status', 'approval', 'export', 'records', 'validation'):
            assert saved[key] == before[key], key


@pytest.mark.parametrize('edit,resolved', [(False, False), (True, False), (True, True)])
def test_unrelated_chat_or_edit_keeps_native_pending_question(host, monkeypatch, edit, resolved):
    repo, _, task = host
    question = '请核对金额。' if resolved else '请提供当前账单的付款截止日期。'
    review = dict(id='original', revision=1, question=question, state='pending', source='completion')
    repo.mutate('task', 'task-1', lambda t: t.update(review_request=deepcopy(review), status='awaiting_input'))
    reply_id = str(uuid4())
    seen = []
    deferred_id = []
    def respond(request):
        seen.append(request)
        if deferred_id:
            return proposed_call('record_review_decision', dict(reply_id=deferred_id[0], action='defer'), 'defer') if len(seen) == (3 if edit else 2) else dict(role='assistant', content='已暂缓。')
        if edit and len(seen) == 1:
            return proposed_call('record_review_decision', dict(reply_id=reply_id, action='edit',
                operations=[dict(op='set', charge_id='c1', field='amount', value=65)],
                resolves_pending=resolved), 'edit')
        return dict(role='assistant', content='THC是码头操作费。')
    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        saver = InMemorySaver()
        def graph(revision):
            mw = ConversationReplies('task-1', revision, task['capability'])
            return create_agent(model, tools=[], middleware=[TaskOutcome('task-1', revision), mw,
                ReplyDecisionMiddleware('task-1', revision, task['capability'], mw.record_tool)], checkpointer=saver)
        config = {'configurable': {'thread_id': 'pending-chat'}}
        try:
            paused = await graph(1).ainvoke({'messages': [{'role': 'user', 'content': '核对'}]}, config)
            pending = paused['__interrupt__'][0]
            repo.mutate('task', 'task-1', lambda t: t.update(conversation=[dict(id=reply_id,
                text='把金额改为65美元' if edit else 'THC是什么？', question=question, interrupt_id=pending.id,
                conversational=True, kind='conversation_review', revision=1, state='starting', model_seen=False)]))
            result = await graph(1).ainvoke(Command(resume={pending.id: dict(reply_id=reply_id, expected_revision=1)}), config)
            if resolved:
                assert not result.get('__interrupt__')
                return
            assert len(result['__interrupt__']) == 1
            assert result['__interrupt__'][0].value['description'] == question
            assert result['__interrupt__'][0].value['revision'] == (2 if edit else 1)
            assert result['__interrupt__'][0].id != pending.id
            current = repo.get('task', 'task-1')
            assert current['review_request']['state'] == 'pending'
            assert current['status'] == 'awaiting_input'
            next_reply = str(uuid4())
            deferred_id.append(next_reply)
            def add_reply(saved):
                saved['conversation'].append(dict(id=next_reply, text='暂缓', question=question,
                    interrupt_id=result['__interrupt__'][0].id, conversational=True, kind='conversation_review',
                    revision=current['revision'], state='starting', model_seen=False))
            repo.mutate('task', 'task-1', add_reply)
            ended = await graph(current['revision']).ainvoke(Command(resume={result['__interrupt__'][0].id:
                dict(reply_id=next_reply, expected_revision=current['revision'])}), config)
            assert not ended.get('__interrupt__')
        finally:
            await http.aclose()
    asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert saved['review_request']['state'] == 'answered'
    assert saved['status'] == ('completed_with_gaps' if resolved else 'review_deferred')
    assert saved['conversation'][0]['state'] == 'completed'
    if not resolved:
        assert saved['conversation'][1]['state'] == 'completed'
    assert saved['revision'] == (2 if edit else 1)
    assert len(saved.get('history') or []) == (1 if edit else 0)


def test_chat_cannot_force_extraction_or_export_tool(host):
    from unittest.mock import AsyncMock
    from backend.tests.test_host import request_for
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(conversation=[dict(id='chat', kind='chat',
        revision=1, state='starting')]))
    middleware = ConversationReplies('task-1', 1, task['capability'])
    handler = AsyncMock()
    for name in ('intake_documents', 'save_document_extraction', 'prepare_export'):
        result = asyncio.run(middleware.awrap_tool_call(request_for(name), handler))
        assert result.status == 'error'
    assert handler.await_count == 0
