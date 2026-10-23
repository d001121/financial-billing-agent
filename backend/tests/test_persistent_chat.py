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


@pytest.mark.parametrize('case', ['stale', 'paused', 'running', 'native_pending', 'review_pending', 'active_reply'])
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
        assert len(seen) == 1
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
def test_unrelated_chat_or_edit_keeps_reminder_without_hijacking_answer(host, monkeypatch, edit, resolved):
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
            return proposed_call('record_review_decision', dict(reply_id=deferred_id[0], action='defer'), 'defer') if len(seen) == 2 else dict(role='assistant', content='已暂缓。')
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
            assert not result.get('__interrupt__')
            assert result['messages'][-1].content != question
            current = repo.get('task', 'task-1')
            assert current['review_request']['state'] == 'pending'
            assert current['review_request']['blocking'] is False
            next_reply = str(uuid4())
            deferred_id.append(next_reply)
            def add_reply(saved):
                saved['conversation'].append(dict(id=next_reply, text='暂缓', question=question,
                    interrupt_id='', conversational=True, kind='chat',
                    revision=current['revision'], state='starting', model_seen=False))
            repo.mutate('task', 'task-1', add_reply)
            ended = await graph(current['revision']).ainvoke({'messages': [dict(role='user',
                id='chat-user-' + next_reply, content='暂缓')]}, config)
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


def test_informational_review_does_not_lock_new_chat(host, monkeypatch):
    repo, _, _ = host
    _, post = chat_server(monkeypatch, repo)
    repo.mutate('task', 'task-1', lambda t: t.update(review_request=dict(
        id='reminder', revision=1, state='pending', blocking=False, question='请说明收付款关系')))
    result = TestClient(app).post('/api/tasks/task-1/reply', json=chat_request())
    assert result.status_code == 200, result.text
    assert post.await_count == 1


def test_answer_receipt_does_not_block_followup_decision(host):
    from backend.tests.test_host import request_for
    from unittest.mock import AsyncMock
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(conversation=[dict(id='reply',
        revision=1, text='是不是有一个费用是没用的', state='starting', model_seen=True,
        kind='conversation_review', conversational=True)]))
    middleware = ConversationReplies('task-1', 1, task['capability'])
    middleware.record_tool.invoke(dict(reply_id='reply', action='answer'))
    handler = AsyncMock(return_value='native followup')
    result = asyncio.run(middleware.awrap_tool_call(request_for('ask_user'), handler))
    assert result == 'native followup' and handler.await_count == 1
    assert not repo.get('task', 'task-1')['conversation'][0].get('proposal')


def test_explicit_reply_gets_bounded_allowance_without_resetting_usage(host, monkeypatch):
    from backend.harness.budget import consume
    from backend.harness.dispatch import PolicyDenied
    repo, _, task = host
    _, post = chat_server(monkeypatch, repo)
    limits = task['capability']['config']['runtime']
    repo.mutate('task', 'task-1', lambda t: t['usage'].update(
        model_calls=limits['model_calls'], tool_calls=limits['tool_calls'], active_seconds=0))
    result = TestClient(app).post('/api/tasks/task-1/reply', json=chat_request())
    assert result.status_code == 200, result.text
    current = repo.get('task', 'task-1')
    assert current['usage']['model_calls'] == limits['model_calls']
    assert current['usage']['tool_calls'] == limits['tool_calls']
    scope = dict(id=current['dispatch_budget_id'], revision=1, role='supervisor')
    for _ in range(limits['turn_model_calls']):
        consume('task-1', 'model_calls', scope=scope)
    with pytest.raises(PolicyDenied):
        consume('task-1', 'model_calls', scope=scope)
    assert repo.get('task', 'task-1')['usage']['model_calls'] == limits['model_calls'] + limits['turn_model_calls']
    assert post.await_count == 1


@pytest.mark.parametrize('has_next', [False, True])
def test_failed_native_reply_retries_from_actual_checkpoint(host, monkeypatch, has_next):
    repo, _, _ = host
    sdk, post = chat_server(monkeypatch, repo)
    request = chat_request() | dict(interrupt_id='consumed-interrupt')
    repo.mutate('task', 'task-1', lambda t: t.update(conversation=[dict(
        id=request['reply_id'], text=request['text'], interrupt_id='consumed-interrupt',
        question='旧待办', revision=1, kind='conversation_review', conversational=True,
        state='failed', decision_error='failed model request', turn_model_calls=6)]))
    sdk.threads.get_state.return_value['next'] = ['model'] if has_next else []
    post.return_value = {'result': {'run_id': 'retry'}} if has_next else {'run_id': 'retry'}
    result = TestClient(app).post('/api/tasks/task-1/reply', json=request)
    assert result.status_code == 200, result.text
    sent = post.call_args.kwargs['json']
    if has_next:
        assert 'input' not in sent['params']  # resume failed node, no fake interrupt answer
    else:
        assert sent['input']['messages'][0]['content'].startswith(request['text'])
    row = repo.get('task', 'task-1')['conversation'][-1]
    assert row['state'] == 'starting' and not row.get('decision_error')
    assert row['attempts'][-1]['decision_error'] == 'failed model request'


@pytest.mark.parametrize('has_next', [False, True])
def test_continue_uses_actual_checkpoint_and_bounded_human_allowance(host, monkeypatch, has_next):
    repo, _, _ = host
    sdk, post = chat_server(monkeypatch, repo)
    monkeypatch.setattr('backend.api.routes.tasks.sdk', lambda: sdk)
    sdk.threads.get_state.return_value['next'] = ['model'] if has_next else []
    post.return_value = {'result': {'run_id': 'continued'}} if has_next else {'run_id': 'continued'}
    maximum = repo.get('task', 'task-1')['capability']['config']['runtime']['model_calls']
    repo.mutate('task', 'task-1', lambda t: t['usage'].update(model_calls=maximum))
    result = TestClient(app).post('/api/tasks/task-1/control', json=dict(action='resume'))
    assert result.status_code == 200, result.text
    sent = post.call_args.kwargs['json']
    if has_next:
        assert post.call_args.args == ('/threads/same-thread/commands',)
        assert 'input' not in sent['params']
    else:
        assert post.call_args.args == ('/threads/same-thread/runs',)
        assert sent['input']['messages'][0]['content']
    saved = repo.get('task', 'task-1')
    assert saved['usage']['model_calls'] == maximum
    assert saved['usage']['human_turn']['ceilings']['model_calls'] == maximum + 6


def test_explicit_continue_feedback_can_retry_after_previous_allowance_is_used(host, monkeypatch):
    from backend.api.task_runtime import continue_feedback
    repo, _, _ = host
    sdk, post = chat_server(monkeypatch, repo)
    maximum = repo.get('task', 'task-1')['capability']['config']['runtime']['model_calls']
    repo.mutate('task', 'task-1', lambda t: t.update(
        feedback=dict(state='failed', revision=1, operations=[], reason='更正费用'),
        usage=dict(model_calls=maximum, tool_calls=0, active_seconds=0)))
    task = repo.get('task', 'task-1')
    blocked = asyncio.run(continue_feedback(task))
    assert blocked['status'] == 'budget_exhausted' and post.await_count == 0
    result = asyncio.run(continue_feedback(repo.get('task', 'task-1'), human_reply=True))
    assert result['run_id'] == 'chat-run' and post.await_count == 1


def test_delete_obsolete_charge_revalidates_and_resolves_its_old_question(host, monkeypatch):
    from backend.tools.review import settle_saved
    from backend.tools.artifacts import reconcile_saved
    from backend.hooks.completion import completion_question
    repo, _, task = host
    def arrange(t):
        empty = deepcopy(t['charges'][0])
        empty.update(charge_id='c2', line_id='empty', charge_item=None, amount=None,
                     creditor=None, debtor=None, evidence=[])
        t['charges'].append(empty)
    repo.mutate('task', 'task-1', arrange)
    reconcile_saved('task-1')
    settled = settle_saved('task-1')
    review = dict(completion_question(settled), id='old-posting', revision=1, state='pending', blocking=False)
    reply_id = str(uuid4())
    repo.mutate('task', 'task-1', lambda t: t.update(review_request=review, conversation=[dict(
        id=reply_id, text='删除没有费用的第二条c2，保留第一条', kind='chat', conversational=True,
        revision=1, state='starting', model_seen=False, question='', interrupt_id='')]))
    seen = []
    def respond(body):
        seen.append(body)
        if len(seen) == 1:
            return proposed_call('record_review_decision', dict(action='edit',
                operations=[dict(op='delete', charge_id='c2')]), 'delete-empty')
        return dict(role='assistant', content='已提出删除第二条。')
    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            mw = ConversationReplies('task-1', 1, task['capability'])
            graph = create_agent(model, tools=[], middleware=[TaskOutcome('task-1', 1), mw,
                ReplyDecisionMiddleware('task-1', 1, task['capability'], mw.record_tool)])
            return await graph.ainvoke({'messages': [dict(role='user',
                id='chat-user-' + reply_id, content='删除c2')]})
        finally:
            await http.aclose()
    result = asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert not result.get('__interrupt__') and len(seen) == 1
    assert saved['revision'] == 2 and [r['charge_id'] for r in saved['records']] == ['c1']
    assert [r['charge_id'] for r in saved['charges']] == ['c1']
    assert saved['review_request']['state'] == 'resolved'
    assert saved['accounting_entity'] == task['accounting_entity']


@pytest.mark.parametrize('kind', ['chat', 'conversation_review'])
def test_chat_cannot_force_extraction_or_export_tool(host, kind):
    from unittest.mock import AsyncMock
    from backend.tests.test_host import request_for
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(conversation=[dict(id='chat', kind=kind,
        conversational=True,
        revision=1, state='starting')]))
    middleware = ConversationReplies('task-1', 1, task['capability'])
    handler = AsyncMock()
    for name in ('intake_documents', 'save_document_extraction', 'prepare_export'):
        result = asyncio.run(middleware.awrap_tool_call(request_for(name), handler))
        assert result.status == 'error'
    assert handler.await_count == 0


def test_old_reply_receipt_cannot_complete_a_new_user_turn(host):
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(conversation=[
        dict(id='old', text='旧问题', revision=1, state='completed', proposal=dict(action='answer')),
        dict(id='current', text='请删除空费用', revision=1, state='starting', conversational=True)]))
    tool = ConversationReplies('task-1', 1, task['capability']).record_tool
    rejected = tool.invoke(dict(reply_id='old', action='answer'))
    assert 'current' in rejected and '旧回合' in rejected
    saved = repo.get('task', 'task-1')
    assert not saved['conversation'][-1].get('proposal')
    assert saved['conversation'][-1]['state'] == 'starting'
    result = tool.invoke(dict(reply_id='current', action='edit',
        operations=[dict(op='set', charge_id='c1', field='amount', value=65)]))
    assert result['proposed'] is True


def test_review_tool_schema_hides_host_identity_and_runtime(host):
    _, _, task = host
    schema = ConversationReplies('task-1', 1, task['capability']).record_tool.tool_call_schema.model_json_schema()
    assert 'action' in schema['properties']
    assert 'reply_id' not in schema['properties'] and 'runtime' not in schema['properties']


@pytest.mark.parametrize('bound_reply', ['current', 'old'])
def test_native_tool_uses_host_turn_identity_without_model_copying_ids(host, monkeypatch, bound_reply):
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(conversation=[
        dict(id='old', text='旧问题', revision=1, state='completed', proposal=dict(action='answer')),
        dict(id='current', text='暂缓', revision=1, state='starting', kind='chat', conversational=True)],
        usage=dict(model_calls=0, tool_calls=0, active_seconds=0,
                   human_turn=dict(id='turn', reply_id=bound_reply, ceilings={}))))
    calls = []
    def respond(body):
        calls.append(body)
        schema = next(t['function']['parameters'] for t in body['tools']
                      if t['function']['name'] == 'record_review_decision')
        assert 'reply_id' not in schema['properties'] and 'runtime' not in schema['properties']
        if len(calls) == 1:
            return proposed_call('record_review_decision', dict(action='defer'), 'defer-current')
        assert bound_reply == 'old'
        assert '旧回合' in str(body['messages'])
        return dict(role='assistant', content='当前回合身份不一致，未应用旧回执。')
    async def run():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            mw = ConversationReplies('task-1', 1, task['capability'])
            graph = create_agent(model, tools=[], middleware=[mw])
            return await graph.ainvoke({'messages': [dict(role='user', content='暂缓')]},
                {'configurable': {'task_budget_id': 'turn'}})
        finally:
            await http.aclose()
    asyncio.run(run())
    saved = repo.get('task', 'task-1')
    assert saved['revision'] == 1
    if bound_reply == 'current':
        assert len(calls) == 1 and saved['conversation'][-1]['proposal']['action'] == 'defer'
        assert saved['status'] == 'review_deferred'
    else:
        assert len(calls) == 2 and not saved['conversation'][-1].get('proposal')


def test_native_reply_can_save_first_candidate_when_none_exist(host):
    from backend.tests.test_host import request_for
    from unittest.mock import AsyncMock
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(records=[], charges=[], conversation=[
        dict(id='initial', revision=1, state='starting', kind='ask_user', conversational=True)]))
    handler = AsyncMock(return_value='first candidate saved')
    middleware = ConversationReplies('task-1', 1, task['capability'])
    result = asyncio.run(middleware.awrap_tool_call(request_for('save_document_extraction'), handler))
    assert result == 'first candidate saved' and handler.await_count == 1


def test_rejected_direct_export_returns_to_model_instead_of_completing_question(host, monkeypatch):
    from langchain.tools import tool
    repo, _, task = host
    reply_id = str(uuid4())
    repo.mutate('task', 'task-1', lambda t: t.update(status='completed_with_gaps', conversation=[
        dict(id=reply_id, revision=1, state='starting', text='是不是有多余费用',
             kind='conversation_review', conversational=True)]))
    calls = []
    @tool(return_direct=True)
    def prepare_export() -> str:
        """Export current records."""
        raise AssertionError('A conversational question must not execute export')
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return proposed_call('prepare_export', {}, 'wrong-export')
        assert len(calls) == 2
        assert any(m.get('role') == 'tool' and '只读工具' in str(m.get('content')) for m in body['messages'])
        return dict(role='assistant', content='应先核对具体费用，不能擅自导出。')
    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            middleware = ConversationReplies('task-1', 1, task['capability'])
            graph = create_agent(model, tools=[prepare_export], middleware=[middleware])
            return await graph.ainvoke({'messages': [dict(role='user', content='核对费用')]})
        finally:
            await http.aclose()
    result = asyncio.run(exercise())
    assert len(calls) == 2 and '不能擅自导出' in result['messages'][-1].content
    assert repo.get('task', 'task-1')['conversation'][-1]['state'] == 'completed'


def test_validation_uses_the_same_granted_ceiling_as_dispatch(host):
    from backend.hooks.guards import validate_native_hook
    _, _, task = host
    maximum = task['capability']['config']['runtime']['model_calls']
    task['usage'].update(model_calls=maximum + 1, human_turn=dict(
        id='turn', ceilings=dict(model_calls=maximum + 6)))
    assert validate_native_hook('budget', task) == []
    task['usage']['model_calls'] = maximum + 7
    assert validate_native_hook('budget', task)[0]['code'] == 'BUDGET_EXCEEDED'


def test_stopped_conversation_is_retryable_without_new_blocking_interrupt(host):
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(
        automatic_stop=dict(code='RUN_BUDGET', revision=1, message='本轮额度已用尽'),
        conversation=[dict(id='stopped', revision=1, state='starting',
                           text='请核对多余费用', conversational=True, kind='conversation_review')]))
    middleware = ConversationReplies('task-1', 1, task['capability'])
    asyncio.run(middleware.aafter_agent({'messages': []}, None))
    saved = repo.get('task', 'task-1')
    assert saved['conversation'][-1]['state'] == 'failed'
    assert saved['conversation'][-1]['decision_error'] == '本轮额度已用尽'
    assert saved['review_request']['blocking'] is False


def test_failed_staged_proposal_retries_without_paying_for_another_model(host, monkeypatch):
    repo, _, task = host
    chat_server(monkeypatch, repo)
    request = chat_request() | dict(interrupt_id='consumed', text='把金额改为65')
    proposal = dict(action='edit', resolves_pending=True,
                    operations=[dict(op='set', charge_id='c1', field='amount', value=65)])
    repo.mutate('task', 'task-1', lambda t: t.update(review_request=dict(
        id='old-question', revision=1, state='pending', blocking=False, question='请确认金额'), conversation=[dict(
        id=request['reply_id'], text=request['text'], interrupt_id='consumed', revision=1,
        state='failed', decision_error='本轮额度用尽', proposal=proposal, conversational=True)]))
    response = TestClient(app).post('/api/tasks/task-1/reply', json=request)
    assert response.status_code == 200, response.text
    row = repo.get('task', 'task-1')['conversation'][-1]
    assert row['proposal'] == proposal and row['attempts'][-1]['proposal'] == proposal
    def no_model(body):
        raise AssertionError('A valid staged proposal needs no additional model HTTP request')
    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', no_model)
        try:
            middleware = ConversationReplies('task-1', 1, task['capability'])
            graph = create_agent(model, tools=[], middleware=[TaskOutcome('task-1', 1), middleware,
                ReplyDecisionMiddleware('task-1', 1, task['capability'], middleware.record_tool)])
            return await graph.ainvoke({'messages': [dict(role='user', content=request['text'])]})
        finally:
            await http.aclose()
    asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert saved['revision'] == 2 and saved['records'][0]['charge_details']['amount'] == 65
    assert saved['conversation'][-1]['state'] == 'completed'
    assert saved['review_request']['state'] == 'answered'
