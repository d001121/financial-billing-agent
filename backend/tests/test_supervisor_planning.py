"""Real native plan/delegate/observe/replan/verify loop; synthetic model/storage."""
import asyncio
import json

from deepagents.backends import StateBackend
from langchain.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from backend.extensions.skill_versions import skill_state
from backend.agents.billing.agent import build_billing_agent
from backend.agents.supervisor.agent import build_supervisor
from backend.middleware.assembly import base_stack
from backend.middleware.outcome import TaskOutcome
from backend.tools import artifacts, skill_bindings
from backend.tests.test_host import host, offline_model, proposed_call


def test_supervisor_replans_after_specialist_and_verifies_corrected_artifact(host, monkeypatch):
    repo, _, original = host
    def start(task):
        task.update(status='running')
        task['sources'][0]['blocks'][0]['text'] = 'Client pay Carrier: THC USD 100'
        task['charges'][0].update(amount=90, debtor=None)
    repo.mutate('task', 'task-1', start)
    cap = original['capability']
    main, specialists = [], []
    plans = [
        [dict(content='核对候选金额与付款关系', status='in_progress'),
         dict(content='保存并核验实际账单', status='pending')],
        [dict(content='专家已指出金额应为100，付款方需补读', status='completed'),
         dict(content='核对付款关系并修正候选', status='in_progress'),
         dict(content='核验实际产物与置信度', status='pending')],
        [dict(content='专家金额疑点已核对并修正为100', status='completed'),
         dict(content='付款方Client、收款方Carrier已按原文核对', status='completed'),
         dict(content='已阅读当前版本核验和置信度回执', status='completed')],
    ]
    def respond(body):
        system = str([m['content'] for m in body['messages'] if m['role'] in ('system', 'developer')])
        if '按需调用的账单核验专家' in system:
            specialists.append(body)
            assert json.loads(body['messages'][-1]['content'])['host']['revision'] == 1
            return dict(role='assistant', content='原文金额100，候选90不符，建议修正。付款方未在委派文本给出，请主控补读。未保存。')
        main.append(body)
        step = len(main)
        if step == 1:
            return proposed_call('write_todos', dict(todos=plans[0]), 'plan-start')
        if step == 2:
            return proposed_call('task', dict(subagent_type='billing-specialist', description=json.dumps(dict(
                goal='核验c1候选金额90与原文THC USD 100', source_ids=['doc'], charge_ids=['c1'],
                questions=['金额是否一致？'], acceptance=['返回具体差异、依据及未解决事项']), ensure_ascii=False)), 'delegate')
        if step == 3:
            assert '未保存' in body['messages'][-1]['content']
            return proposed_call('write_todos', dict(todos=plans[1]), 'plan-change')
        if step == 4:
            return proposed_call('read_materials', {}, 'follow-up-read')
        if step == 5:
            assert 'Client pay Carrier' in body['messages'][-1]['content']
            module = skill_bindings.skill_module('document-extraction', cap['version'])
            refs = module.citation_index(repo.get('task', 'task-1'))
            rid = next(k for k, r in refs.items() if 'Client pay Carrier' in r['quote'])
            return proposed_call('save_document_extraction', dict(finalize=True, replace=True,
                result=dict(charges=[dict(charge_id='c1', line_id='line1', document_id='doc',
                    reference_no=None, charge_item='THC', amount=100, currency='USD', creditor='Carrier', debtor='Client',
                    evidence=[dict(ref_id=rid, fields=['charge_item','amount','currency','creditor','debtor'])])])), 'correct')
        if step == 6:
            result = json.loads(body['messages'][-1]['content'])
            assert result['verification']['revision'] == 1
            assert result['verification']['review_score'] > 0
            return proposed_call('prepare_export', {}, 'final-check')
        if step == 7:
            result = json.loads(body['messages'][-1]['content'])
            assert result['verification']['review_score'] > 0
            assert result['records'][0]['financial_attributes']['posting_type'] == 'AP'
            return proposed_call('write_todos', dict(todos=plans[2]), 'plan-finish')
        assert step == 8
        return dict(role='assistant', content='金额已按原文修正为100 USD，方向AP；已有字段置信度100/100。')
    async def execute():
        model, client = offline_model(monkeypatch, 'task-1', respond)
        try:
            spec = next(s for s in cap['config']['agents']['agents'] if s['name'] == 'billing-specialist')
            child_backend = StateBackend()
            child_common, child_business = skill_bindings.tools_for('task-1', cap, spec['skills'])
            child = build_billing_agent(model, child_common,
                base_stack('task-1', 1, cap, child_backend, child_business, spec['skills']), spec['prompt'], spec['name'])
            backend = StateBackend()
            common, business = skill_bindings.tools_for('task-1', cap)
            graph = build_supervisor(model, common, backend,
                base_stack('task-1', 1, cap, backend, business, outcome=True),
                [dict(name=spec['name'], description=spec['description'], runnable=child)])
            graph.checkpointer = InMemorySaver()
            config = {'configurable': {'thread_id': 'dynamic-plan'}, 'recursion_limit': 256}
            result = await graph.ainvoke({**skill_state(cap, repo.get('task', 'task-1')),
                'messages': [{'role':'user','content':'核对候选费用并保存结果'}]}, config)
            snapshot = await graph.aget_state(config)
            assert snapshot.values['todos'] == plans[-1]
            return result
        finally:
            await client.aclose()
    state = asyncio.run(execute())
    saved = repo.get('task', 'task-1')
    assert len(main) == 8 and len(specialists) == 1
    assert saved['usage']['model_calls'] == 9
    assert saved['records'][0]['charge_details']['amount'] == 100
    assert saved['status'] == 'completed' and saved['approval'] is None
    tools = [m.name for m in state['messages'] if isinstance(m, ToolMessage)]
    assert tools == ['write_todos','task','write_todos','read_materials',
                     'save_document_extraction','prepare_export','write_todos']
    receipt = next(m for m in state['messages'] if isinstance(m, ToolMessage) and m.name == 'prepare_export')
    assert receipt.artifact['revision'] == saved['revision']
    assert receipt.artifact['verification']['review_score'] == saved['validation']['confidence']['review_score']
    assert not any(e.get('tool') == 'intake_documents' for e in repo.receipts)


def test_fallback_check_returns_to_model_once_instead_of_silent_background_finish(host, monkeypatch):
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(status='running'))
    seen = []
    def respond(body):
        seen.append(body)
        if len(seen) == 1:
            return dict(role='assistant', content='候选已保存。')
        assert len(seen) == 2
        assert '当前版本最终核验已返回主控' in str(body['messages'])
        assert 'review_score' in str(body['messages'])
        return dict(role='assistant', content='核验已返回，按实际置信度与缺口结束。')
    async def execute():
        model, client = offline_model(monkeypatch, 'task-1', respond)
        try:
            backend = StateBackend()
            common, business = skill_bindings.tools_for('task-1', task['capability'])
            graph = build_supervisor(model, common, backend,
                base_stack('task-1', 1, task['capability'], backend, business, outcome=True), [])
            return await graph.ainvoke({**skill_state(task['capability'], task),
                'messages':[{'role':'user','content':'核验已保存候选'}]})
        finally:
            await client.aclose()
    result = asyncio.run(execute())
    assert len(seen) == 2
    assert '核验已返回' in result['messages'][-1].content
    assert repo.get('task', 'task-1')['validation']['confidence']


def test_verification_projection_is_bounded_and_does_not_recalculate_or_copy_ocr():
    result = artifacts.verification_summary(dict(revision=4, ok=False,
        confidence=dict(score=70, review_score=60, review_required=True,
            review_items=[dict(field='amount', score=0) for _ in range(50)]),
        sources=[dict(text='x' * 100000)]))
    assert result['revision'] == 4 and result['review_item_count'] == 50
    assert len(result['review_items']) == 8 and len(json.dumps(result)) < 1000


def test_same_revision_write_invalidates_an_earlier_final_check(host):
    from backend.tools.review import settle_saved
    repo, _, _ = host
    checked = settle_saved('task-1')
    assert checked['status'] in ('completed', 'completed_with_gaps')
    old_receipt = ToolMessage(content='{}', name='prepare_export', tool_call_id='old',
        artifact=dict(revision=1, verification={'review_score': 100}))
    artifacts.reconcile_saved('task-1')
    assert repo.get('task', 'task-1')['export'] is None
    state = {'messages': [old_receipt,
        ToolMessage(content='候选已重新保存', name='save_document_extraction', tool_call_id='new')]}
    middleware = TaskOutcome('task-1', 1)
    result = asyncio.run(middleware.aafter_agent(state, None))
    assert result['jump_to'] == 'model'
    assert repo.get('task', 'task-1')['export'] is not None
    assert asyncio.run(middleware.aafter_agent(state, None)) is None


def test_completed_human_edit_does_not_bounce_back_to_the_model(host):
    """The human edit already committed and revalidated; no extra model round."""
    from backend.middleware.outcome import TaskOutcome
    repo, _, _ = host
    repo.mutate('task', 'task-1', lambda t: t.update(
        export=None, status='completed_with_gaps', review_request={}, feedback=None,
        conversation=[dict(id='reply-1', state='completed', revision=1,
                           applied_revision=1, text='币种是美元')]))
    middleware = TaskOutcome('task-1', 1)
    assert asyncio.run(middleware.aafter_agent({'messages': []}, None)) is None


def test_invalid_tool_call_without_id_returns_to_model_once(monkeypatch):
    from langchain.agents import create_agent
    from langchain.tools import tool
    from langgraph.checkpoint.memory import InMemorySaver
    from backend.middleware.recovery import InvalidToolCallRecovery

    @tool
    def save_document_extraction(result: dict, finalize: bool = False) -> dict:
        """save the candidate extraction"""
        return {'saved': True}

    calls = []
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return dict(role='assistant', content='', tool_calls=[dict(type='function',
                function=dict(name='save_document_extraction',
                              arguments='{"result": {"charges": [1, 2}'))])
        assert '[tool-call-recovery]' in str(body['messages'])
        return dict(role='assistant', content='已改为合法参数并重试')
    async def execute():
        model, client = offline_model(monkeypatch, None, respond)
        try:
            graph = create_agent(model, tools=[save_document_extraction],
                                 middleware=[InvalidToolCallRecovery()],
                                 checkpointer=InMemorySaver())
            return await graph.ainvoke({'messages': [{'role': 'user', 'content': '保存'}]},
                                       {'configurable': {'thread_id': 'invalid-call'}})
        finally:
            await client.aclose()
    result = asyncio.run(execute())
    assert len(calls) == 2
    assert '已改为合法参数并重试' in result['messages'][-1].content
