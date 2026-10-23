"""Conversation edits exercise real native HITL and middleware; no external services."""
import asyncio
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
import pytest

from backend.api import app, task_runtime
from backend.api.routes import conversation
from backend.extensions.skill_versions import skill_state
from backend.middleware.assembly import base_stack
from backend.agents.supervisor.agent import build_supervisor
from backend.tools import skill_bindings
from deepagents.backends import StateBackend
from backend.tests.test_host import host, offline_model, proposed_call


def setup_server(monkeypatch, repo, *, payload=None, fail=False):
    repo.mutate('task','task-1',lambda t:t.update(thread_id='same-thread',run_id='old-run',run_status='interrupted',status='awaiting_input'))
    state = dict(tasks=[dict(interrupts=[dict(id='actual-interrupt', value=payload or dict(
        type='tool_approval', name='ask_user',tool_call_id='ask',args={'question':'请核对费用和主体'}))])],
        values={'messages':[{'id':'last-message'}]},checkpoint={'checkpoint_id':'real-saved'})
    post = AsyncMock(side_effect=RuntimeError('unavailable') if fail else None,
        return_value={'result':{'run_id':'reply-run'}})
    sdk = SimpleNamespace(http=SimpleNamespace(post=post),
        runs=SimpleNamespace(get=AsyncMock(return_value={'status':'interrupted'})),
        threads=SimpleNamespace(get_state=AsyncMock(return_value=state)))
    monkeypatch.setattr(task_runtime,'repository',lambda:repo)
    monkeypatch.setattr(task_runtime,'sdk',lambda:sdk)
    monkeypatch.setattr(conversation,'sdk',lambda:sdk)
    return sdk, post


def body(text='主体改为Acme，第一项金额改为65美元'):
    return dict(expected_revision=1,interrupt_id='actual-interrupt',reply_id=str(uuid4()),text=text)


def skip_structured(monkeypatch):
    """Exercise the model-loop fallback instead of the structured decision."""
    async def none(self, request, task, reply):
        return None
    from backend.middleware.reply_decision import ReplyDecisionMiddleware
    monkeypatch.setattr(ReplyDecisionMiddleware, 'structured_decision', none)


def test_reply_is_native_scoped_resume_and_replay_safe(host,monkeypatch):
    repo,_,task=host
    sdk,post=setup_server(monkeypatch,repo)
    client=TestClient(app)
    request=body()
    result=client.post('/api/tasks/task-1/reply',json=request)
    assert result.status_code==200,result.text
    params=post.call_args.kwargs['json']['params']
    assert params['force_resume'] is True
    assert params['input']=={'actual-interrupt':{'type':'respond','message':request['text']}}
    assert params['config']['configurable']['task_revision']==1
    saved=repo.get('task','task-1')
    assert saved['revision']==1 and saved['approval'] is None
    assert saved['conversation'][0]['tool_call_id']=='ask'
    assert client.post('/api/tasks/task-1/reply',json=request).status_code==200
    assert post.await_count==1
    assert client.post('/api/tasks/task-1/reply',json={**request,'text':'different'}).status_code==409


def test_new_native_interrupt_does_not_get_blocked_by_consumed_reply(host,monkeypatch):
    repo,_,_=host
    sdk,post=setup_server(monkeypatch,repo)
    # The previous resume was accepted and produced a new interrupt before
    # the middleware could mark its transport row completed.
    repo.mutate('task','task-1',lambda t:t.update(run_status='success',conversation=[dict(
        id=str(uuid4()), text='主体已确认', question='请选择主体', interrupt_id='old-interrupt',
        revision=1, state='starting', model_seen=True, at='now')]))
    result=TestClient(app).post('/api/tasks/task-1/reply',json=body('湃乐多是付款方'))
    assert result.status_code==200,result.text
    saved=repo.get('task','task-1')
    assert saved['conversation'][0]['state']=='completed'
    assert saved['conversation'][-1]['state']=='starting'
    assert post.await_count==1


@pytest.mark.parametrize('case',['stale','no_interrupt','budget','paused','invalid_text'])
def test_invalid_reply_never_dispatches_or_edits(host,monkeypatch,case):
    repo,_,task=host
    sdk,post=setup_server(monkeypatch,repo)
    request=body()
    if case=='stale':request['expected_revision']=0
    if case=='no_interrupt':request['interrupt_id']='expired'
    if case=='budget':repo.mutate('task','task-1',lambda t:t['usage'].update(model_calls=t['capability']['config']['runtime']['model_calls']))
    if case=='paused':repo.mutate('task','task-1',lambda t:t.update(control='paused'))
    if case=='invalid_text':request['text']=' '
    result=TestClient(app).post('/api/tasks/task-1/reply',json=request)
    assert result.status_code in (409,422),result.text
    assert post.await_count==0
    assert repo.get('task','task-1')['records']==task['records']


def test_gated_action_is_not_approved_by_a_sentence(host,monkeypatch):
    repo,_,_=host
    _,post=setup_server(monkeypatch,repo,payload=dict(type='tool_approval',name='dangerous_action',description='Review action'))
    result=TestClient(app).post('/api/tasks/task-1/reply',json=body('金额改为65美元'))
    assert result.status_code==200,result.text
    reply=post.call_args.kwargs['json']['params']['input']['actual-interrupt']
    assert reply['type']=='reject' and '金额改为65' in reply['message']


def test_native_answer_changes_entity_and_amount_through_existing_skill(host,monkeypatch):
    repo,live,task=host
    skip_structured(monkeypatch)
    repo.mutate('task','task-1',lambda t:t['capability']['config']['runtime'].update(agent_style='codex'))
    _,post=setup_server(monkeypatch,repo)
    saver=InMemorySaver()
    seen=[]
    def respond(request):
        seen.append(request)
        if len(seen)==1:
            return proposed_call('ask_user',dict(question='请核对费用和主体'),'ask')
        if len(seen)==2:
            text=str(request['messages'])
            assert '主体改为Acme' in text and '调用方在真实人工中断' in text
            reply=repo.get('task','task-1')['conversation'][-1]
            return proposed_call('record_review_decision',dict(reply_id=reply['id'],action='edit',
                operations=[dict(op='set',charge_id='c1',field='amount',value=65)],
                set_accounting_entity=True,accounting_entity='Acme'),'apply-reply')
        if len(seen)==4:
            reply=repo.get('task','task-1')['conversation'][-1]
            assert 'Acme是付款方' in str(request['messages'])
            return proposed_call('record_review_decision',dict(reply_id=reply['id'],action='edit',
                operations=[dict(op='set',charge_id='c1',field='debtor',value='Acme')]),'fix-relationship')
        return dict(role='assistant',content='已记录您的修改，正在重新核对。')
    def graph(model,revision):
        backend=StateBackend()
        cap=repo.get('task','task-1')['capability']
        common,business=skill_bindings.tools_for('task-1',cap)
        g=build_supervisor(model,common,backend,base_stack('task-1',revision,cap,backend,business,outcome=True),[])
        g.checkpointer=saver
        return g
    async def exercise():
        model,http=offline_model(monkeypatch,'task-1',respond)
        config={'configurable':{'thread_id':'same-thread'},'recursion_limit':512}
        try:
            paused=await graph(model,1).ainvoke(
                {**skill_state(repo.get('task','task-1')['capability'], repo.get('task','task-1')),
                 'messages':[{'role':'user','content':'提取'}]},config)
            interrupt=paused['__interrupt__'][0]
            sdk=task_runtime.sdk()
            sdk.threads.get_state.return_value=dict(checkpoint={'checkpoint_id':'saved'},
                values={'messages':[{'id':'native-ask'}]},tasks=[dict(interrupts=[dict(id=interrupt.id,value=interrupt.value)])])
            async def dispatch(path,*,json):
                return_value=await graph(model,repo.get('task','task-1')['revision']).ainvoke(
                    Command(resume=json['params']['input']),config)
                sdk.threads.get_state.return_value=dict(checkpoint={'checkpoint_id':'saved'},
                    values={'messages':[]},tasks=[dict(interrupts=[dict(id=i.id,value=i.value)
                        for i in return_value.get('__interrupt__',[])])])
                return {'result':{'run_id':'reply-run'}}
            post.side_effect=dispatch
            request={**body(),'interrupt_id':interrupt.id}
            # Calling endpoint directly keeps this graph/test in the same event loop.
            from starlette.requests import Request
            from backend.infrastructure.repository import dumps
            req=Request({'type':'http'},receive=AsyncMock(return_value={'type':'http.request','body':dumps(request).encode()}))
            await conversation.reply_to_agent('task-1',req)
            mid=repo.get('task','task-1')
            assert mid['revision']==2 and mid['status']=='awaiting_input'
            assert mid['review_request']['source']=='completion'
            question=mid['review_request']['question']
            assert 'AR/AP' in question and 'Acme' in question and 'Carrier' in question
            assert mid['records'][0]['financial_attributes']['posting_type'] is None
            assert mid['auto_review'] is None
            new_interrupt=sdk.threads.get_state.return_value['tasks'][0]['interrupts'][0]
            answer=dict(expected_revision=2,interrupt_id=new_interrupt['id'],reply_id=str(uuid4()),
                        text='Acme是付款方')
            req=Request({'type':'http'},receive=AsyncMock(return_value={'type':'http.request','body':dumps(answer).encode()}))
            await conversation.reply_to_agent('task-1',req)
        finally:await http.aclose()
    asyncio.run(exercise())
    saved=repo.get('task','task-1')
    assert len(seen)==5
    assert saved['revision']==3 and saved['accounting_entity']=='Acme'
    assert saved['records'][0]['charge_details']['amount']==65
    assert saved['records'][0]['human_confirmed']['charge_details.amount']['value']==65
    assert saved['records'][0]['human_confirmed']['financial_attributes.accounting_entity']['value']=='Acme'
    assert saved['approval'] is None and saved.get('review_confirmation') is None
    assert saved['conversation'][0]['state']=='completed'
    assert saved['conversation'][0]['applied_revision']==2
    assert saved['conversation'][1]['applied_revision']==3
    assert saved['sources']==task['sources'] and saved['capability']==task['capability']
    assert not any(e.get('tool')=='intake_documents' for e in repo.receipts)
    assert saved['records'][0]['financial_attributes']['posting_type']=='AP'
    assert saved['status']=='completed_with_gaps'  # Synthetic amount 65 still differs from source 100.
    assert saved['records'][0]['human_confirmed']['debtor']['value']=='Acme'
    # Native after-agent replay must not commit the first edit twice.
    assert len(saved['history'])==2
    state=asyncio.run(saver.aget_tuple({'configurable':{'thread_id':'same-thread'}}))
    last=state.checkpoint['channel_values']['messages'][-1].content
    assert '第 3 版' in last
    assert not state.pending_writes


def test_completion_question_distinguishes_entity_conflict_absence_and_defer(host):
    from backend.hooks.completion import completion_question
    from backend.tools import review
    repo,_,_=host
    repo.mutate('task','task-1',lambda t:t.update(accounting_entity='Unrelated'))
    from backend.tools.artifacts import reconcile_saved
    reconcile_saved('task-1')
    current=review.settle_saved('task-1')
    assert completion_question(current)['field']=='posting_type'
    current['accounting_entity']=None
    entity=completion_question(current)
    assert entity and entity['field']=='accounting_entity' and entity['source']=='completion'
    current['accounting_entity']='Unrelated'
    current['status']='review_deferred'
    assert completion_question(current) is None
    current['status']='completed_with_gaps'
    current['validation']['revision']=0
    assert completion_question(current) is None


def test_entity_candidates_use_all_saved_parties_without_selecting_one(host):
    from backend.extensions.skill_versions import function
    _,_,task=host
    task['accounting_entity']=None
    task['extraction']['documents']=[{'issuer':' Carrier ', 'recipient':'Overseas Trading LLC'},
                                     {'issuer':'carrier', 'recipient':None}]
    question=function(task['capability'],'human-review','entity_question')(task)
    assert question['choices']==['Carrier','Client','Overseas Trading LLC']
    assert task['accounting_entity'] is None
    task['charges']=[]
    task['records']=[{'charge_id':'only-one','transaction_party':{'issuer':'Carrier'}}]
    task['extraction']['documents']=[]
    assert function(task['capability'],'human-review','entity_question')(task)['choices']==['Carrier']


def test_entity_question_waits_for_records_and_current_validation(host):
    from backend.hooks.completion import completion_question
    from backend.extensions.skill_versions import function
    _,_,task=host
    task.update(accounting_entity=None,validation={'revision':1,'issues':[]})
    question=completion_question(task)
    assert question and question['field']=='accounting_entity'
    entity_question=function(task['capability'],'human-review','entity_question')
    assert entity_question(task)['choices']==['Carrier','Client']
    task['charges']=[]
    task['records']=[{'charge_id':'no-parties'}]
    assert entity_question(task)['choices']==[]
    task['validation']['revision']=0
    assert completion_question(task) is None
    task['records']=[]
    assert entity_question(task) is None


def test_entity_absence_opens_a_native_entity_question(host):
    from backend.hooks import completion
    _,_,task=host
    task.update(accounting_entity=None,validation={'revision':1,'issues':[]})
    question=completion.completion_question(task)
    assert question and question['field']=='accounting_entity'


def test_missing_entity_saves_records_then_opens_entity_question(host):
    from backend.hooks.completion import completion_question
    from backend.tools.artifacts import reconcile_saved
    from backend.tools.review import settle_saved
    repo,_,task=host
    repo.mutate('task','task-1',lambda t:t.update(accounting_entity=None))
    reconcile_saved('task-1')
    settled=settle_saved('task-1')
    assert settled['records']
    record=settled['records'][0]
    assert record['operation']=='PENDING_REVIEW'
    assert record['financial_attributes']['posting_type'] is None
    assert record['financial_attributes']['accounting_entity'] is None
    question=completion_question(settled)
    assert question and question['field']=='accounting_entity'


def test_confidence_text_is_not_automatic_confirmation(host,monkeypatch):
    repo,_,task=host
    _,post=setup_server(monkeypatch,repo,payload=dict(kind='confidence_review',revision=1,items=[]))
    result=TestClient(app).post('/api/tasks/task-1/reply',json=body('请修改金额，不能确认'))
    assert result.status_code==200,result.text
    response=post.call_args.kwargs['json']['params']['input']['actual-interrupt']
    assert response['message']=='请修改金额，不能确认' and 'decision' not in response
    assert repo.get('task','task-1')['approval'] is None


def test_explicit_review_opens_native_interrupt_without_model_call(host,monkeypatch):
    from backend.middleware.conversation import ConversationReplies
    from langchain.agents import create_agent
    repo,_,task=host
    sdk,post=setup_server(monkeypatch,repo)
    sdk.threads.get_state.return_value={'tasks':[], 'values':{}}
    seen=[]
    async def exercise():
        model,http=offline_model(monkeypatch,'task-1',lambda request: seen.append(request) or dict(role='assistant',content='不应调用'))
        try:
            middleware=ConversationReplies('task-1',1,task['capability'])
            graph=create_agent(model,tools=[],middleware=[middleware],checkpointer=InMemorySaver())
            async def dispatch(path,*,json):
                assert path.endswith('/runs') and 'command' not in json
                result=await graph.ainvoke(json['input'],{'configurable':{'thread_id':'manual-review'}})
                assert result['__interrupt__'][0].value['kind']=='conversation_review'
                assert result['__interrupt__'][0].value['choices']==['Carrier','Client']
                return {'run_id':'manual-review-run'}
            post.side_effect=dispatch
            from starlette.requests import Request
            from backend.infrastructure.repository import dumps
            req=Request({'type':'http'},receive=AsyncMock(return_value={'type':'http.request','body':dumps(dict(
                expected_revision=1,action='entity')).encode()}))
            await conversation.request_review_conversation('task-1',req)
        finally:await http.aclose()
    asyncio.run(exercise())
    assert seen==[]
    assert repo.get('task','task-1')['review_request']['state']=='pending'
    assert repo.get('task','task-1')['revision']==1


def test_legacy_return_direct_confidence_reply_goes_back_to_model(host,monkeypatch):
    from backend.middleware.conversation import ConversationReplies
    from backend.tools.review import finalize_with_review
    from backend.tools import artifacts
    from langchain.agents import create_agent
    from langchain.tools import tool
    repo,_,task=host
    skip_structured(monkeypatch)
    repo.mutate('task','task-1',lambda t:t['capability']['config']['runtime'].update(agent_style='legacy'))
    repo.mutate('task','task-1',lambda t:t['charges'][0].update(amount=125))
    artifacts.reconcile_saved('task-1')
    saver=InMemorySaver()
    seen=[]
    def respond(request):
        seen.append(request)
        if len(seen)==1:return proposed_call('finish',{},'finish')
        if len(seen)==2:
            reply=repo.get('task','task-1')['conversation'][-1]
            return proposed_call('record_review_decision',dict(reply_id=reply['id'],action='edit',
                operations=[dict(op='set',charge_id='c1',field='amount',value=100)]),'correction')
        return dict(role='assistant',content='已记录更正。')
    async def exercise():
        model,http=offline_model(monkeypatch,'task-1',respond)
        @tool(return_direct=True)
        async def finish()->dict:
            """Finish isolated legacy review."""
            await finalize_with_review('task-1')
            return {'returned':True}
        middleware=ConversationReplies('task-1',1,repo.get('task','task-1')['capability'])
        graph=create_agent(model,tools=[finish],middleware=[middleware],checkpointer=saver)
        config={'configurable':{'thread_id':'legacy-reply'}}
        try:
            paused=await graph.ainvoke({'messages':[{'role':'user','content':'核对'}]},config)
            pending=paused['__interrupt__'][0]
            reply_id=str(uuid4())
            repo.mutate('task','task-1',lambda t:t.update(conversation=[dict(id=reply_id,text='金额改为100美元',
                revision=1,state='starting',model_seen=False,question='核对金额')]))
            result=await graph.ainvoke(Command(resume={pending.id:dict(message='金额改为100美元',
                reply_id=reply_id,expected_revision=1)}),config)
            assert not result.get('__interrupt__')
        finally:await http.aclose()
    asyncio.run(exercise())
    saved=repo.get('task','task-1')
    assert len(seen)==3
    assert saved['revision']==2 and saved['records'][0]['charge_details']['amount']==100
    assert saved['approval'] is None
    assert saved['conversation'][0]['state']=='completed'


def test_successful_native_run_with_pending_checkpoint_is_waiting_input(host,monkeypatch):
    repo,_,_=host
    sdk,_=setup_server(monkeypatch,repo)
    sdk.runs.get.return_value={'status':'success'}
    result=asyncio.run(task_runtime.sync_task(repo.get('task','task-1')))
    assert result['run_status']=='success' and result['status']=='awaiting_input'
    assert len(result['interrupts'])==1


def test_normal_turn_with_projected_null_conversation_hides_reply_tool(host,monkeypatch):
    from backend.middleware.conversation import ConversationReplies
    from langchain.agents import create_agent
    repo,_,task=host
    def projection(kind,task_id,fields):
        current=repo.get(kind,task_id)
        return {key:current.get(key) for key in ['id','revision',*fields]}
    monkeypatch.setattr(repo,'get_fields',projection,raising=False)
    seen=[]
    def respond(request):
        seen.append(request)
        assert 'record_review_decision' not in str(request.get('tools'))
        return dict(role='assistant',content='正常处理，无需人工回复。')
    async def exercise():
        model,http=offline_model(monkeypatch,'task-1',respond)
        try:
            graph=create_agent(model,tools=[],middleware=[ConversationReplies('task-1',1,task['capability'])])
            await graph.ainvoke({'messages':[{'role':'user','content':'处理'}]})
        finally:await http.aclose()
    asyncio.run(exercise())
    assert len(seen)==1


def test_ended_noop_run_exposes_recovery_and_review_request_can_retry(host,monkeypatch):
    repo,_,_=host
    sdk,post=setup_server(monkeypatch,repo)
    sdk.runs.get.return_value={'status':'success'}
    sdk.threads.get_state.return_value=dict(tasks=[],next=[],values={},checkpoint={'checkpoint_id':'saved'})
    pending=dict(id='unopened-review',revision=1,action='edit',charge_id='c1',field='',
                 question='请告诉我正确内容。',state='pending')
    repo.mutate('task','task-1',lambda t:t.update(status='running',review_request=pending))
    synced=asyncio.run(task_runtime.sync_task(repo.get('task','task-1')))
    assert synced['status']=='recovery_required' and synced['run_status']=='success'
    post.return_value={'run_id':'actual-new-turn'}
    result=TestClient(app).post('/api/tasks/task-1/review-conversation',json=dict(expected_revision=1,action='edit',charge_id='c1'))
    assert result.status_code==200,result.text
    assert result.json()['review_request']['id']=='unopened-review'
    assert post.call_args.args==('/threads/same-thread/runs',)
    assert post.call_args.kwargs['json']['input']['messages']
    assert 'command' not in post.call_args.kwargs['json']
    assert repo.get('task','task-1')['revision']==1


def test_ended_run_with_real_interrupt_keeps_reply_available(host,monkeypatch):
    repo,_,_=host
    sdk,_=setup_server(monkeypatch,repo)
    sdk.runs.get.return_value={'status':'success'}
    repo.mutate('task','task-1',lambda t:t.update(status='running'))
    result=asyncio.run(task_runtime.sync_task(repo.get('task','task-1')))
    assert result['status']=='awaiting_input'
    assert result['interrupts'][0]['id']=='actual-interrupt'


def test_edit_before_first_finalize_materializes_records(host):
    """An ask_user answer can arrive before records exist; materialize them."""
    from backend.middleware.conversation import ConversationReplies
    repo,_,task=host
    repo.mutate('task','task-1',lambda t:t.update(records=[],validation=None,export=None,status='processing'))
    reply_id=str(uuid4())
    repo.mutate('task','task-1',lambda t:t.update(conversation=[dict(
        id=reply_id,text='币种是美元',revision=1,state='starting',kind='ask_user',
        model_seen=False,question='请补充币种',turn_model_calls=0)]))
    middleware=ConversationReplies('task-1',1,task['capability'])
    result=middleware.tools[0].invoke(dict(reply_id=reply_id,action='edit',
        operations=[dict(op='set',charge_id='c1',field='currency',value='EUR')]))
    assert result['proposed'] is True
    saved=repo.get('task','task-1')
    assert saved['records'] and saved['records'][0]['charge_id']=='c1'
    assert saved['conversation'][0]['state']=='proposed'


def test_reply_turn_exposes_skill_tools_until_a_decision_is_staged(host):
    from langchain.agents.middleware.types import ModelRequest
    from langchain.messages import AIMessage
    from langchain.tools import tool
    from backend.middleware.conversation import ConversationReplies
    repo,_,task=host
    reply_id=str(uuid4())
    repo.mutate('task','task-1',lambda t:t.update(conversation=[dict(
        id=reply_id,text='请帮我核对一下这些费用',revision=1,state='starting',kind='conversation_review',
        model_seen=False,question='请核对',turn_model_calls=0)]))

    @tool
    def prepare_export()->dict:
        """export"""
        return {}

    @tool
    def write_todos(todos:list)->str:
        """plan"""
        return 'ok'

    @tool
    def read_task_context()->dict:
        """read"""
        return {}

    seen=[]
    async def handler(request):
        seen.append([t.name for t in request.tools])
        return AIMessage(content='按 Skill 处理回复')
    middleware=ConversationReplies('task-1',1,task['capability'])
    request=ModelRequest(model=None,messages=[],
        tools=[prepare_export,write_todos,read_task_context],runtime=None)
    asyncio.run(middleware.awrap_model_call(request,handler))
    assert set(seen[0]) == {'prepare_export','write_todos','read_task_context'}
    repo.mutate('task','task-1',lambda t:t['conversation'][0].update(
        proposal=dict(action='edit',operations=[])))
    asyncio.run(middleware.awrap_model_call(request,handler))
    assert seen[1] == []


def test_ask_user_answer_before_first_finalize_applies_through_revision(host,monkeypatch):
    """The trace failure: an answer arrived while records were still empty."""
    from langgraph.checkpoint.memory import InMemorySaver
    from langchain.agents import create_agent
    from backend.middleware.conversation import ConversationReplies
    repo,_,task=host
    skip_structured(monkeypatch)
    repo.mutate('task','task-1',lambda t:t.update(
        records=[],validation=None,export=None,status='running',accounting_entity=None,review_request={}))
    reply_id=str(uuid4())
    repo.mutate('task','task-1',lambda t:t.update(conversation=[dict(
        id=reply_id,text='本次记账主体用Client',revision=1,state='starting',kind='ask_user',
        model_seen=False,question='请选择主体',turn_model_calls=0)]))
    seen=[]
    def respond(body):
        seen.append(body)
        if len(seen)==1:
            return proposed_call('record_review_decision',dict(reply_id=reply_id,action='edit',
                set_accounting_entity=True,accounting_entity='Client'),'entity')
        return dict(role='assistant',content='已应用主体')
    async def exercise():
        model,http=offline_model(monkeypatch,'task-1',respond)
        try:
            graph=create_agent(model,tools=[],
                middleware=[ConversationReplies('task-1',1,task['capability'])],
                checkpointer=InMemorySaver())
            await graph.ainvoke({'messages':[{'role':'user','content':'继续'}]},
                                {'configurable':{'thread_id':'ask-before-finalize'}})
        finally:
            await http.aclose()
    asyncio.run(exercise())
    saved=repo.get('task','task-1')
    assert len(seen)==2
    assert saved['revision']==2 and saved['accounting_entity']=='Client'
    assert saved['records'] and saved['conversation'][0]['state']=='completed'


def test_reply_turn_allows_skill_recovery_until_a_decision_is_staged(host):
    """The Skill owns the order; only a staged decision is terminal."""
    from langchain.messages import ToolMessage
    from backend.middleware.conversation import ConversationReplies
    from backend.tests.test_host import request_for
    repo,_,task=host
    reply_id=str(uuid4())
    repo.mutate('task','task-1',lambda t:t.update(conversation=[dict(
        id=reply_id,text='主体是Client',revision=1,state='starting',kind='ask_user',
        model_seen=True,question='主体',turn_model_calls=1)]))
    called=[]
    async def handler(request):
        called.append(request.tool_call['name'])
        return ToolMessage(content='ok',tool_call_id=request.tool_call['id'],
                           name=request.tool_call['name'])
    middleware=ConversationReplies('task-1',1,task['capability'])
    allowed=asyncio.run(middleware.awrap_tool_call(
        request_for('save_document_extraction', result={}),handler))
    assert called==['save_document_extraction'] and allowed.status!='error'
    repo.mutate('task','task-1',lambda t:t['conversation'][0].update(
        last_error='请先保存候选', state='proposed'))
    retried=asyncio.run(middleware.awrap_tool_call(request_for('write_todos',todos=[]),handler))
    assert called[-1]=='write_todos' and retried.status!='error'
    repo.mutate('task','task-1',lambda t:t['conversation'][0].update(
        proposal=dict(action='edit',operations=[])))
    blocked=asyncio.run(middleware.awrap_tool_call(
        request_for('save_document_extraction', result={}),handler))
    assert blocked.status=='error' and called.count('save_document_extraction')==1


def test_decision_error_ends_without_after_agent_self_loop(host):
    from backend.middleware.conversation import ConversationReplies
    from backend.middleware.outcome import TaskOutcome
    repo,_,task=host
    reply_id=str(uuid4())
    repo.mutate('task','task-1',lambda t:t.update(status='processing',conversation=[dict(
        id=reply_id,text='主体是Client',revision=1,state='proposed',kind='ask_user',
        model_seen=True,question='主体',decision_error='模型调用上限')]))
    result=asyncio.run(ConversationReplies('task-1',1,task['capability']).aafter_agent(
        {'messages':[]},None))
    assert 'jump_to' not in result
    saved=repo.get('task','task-1')
    assert saved['conversation'][0]['state']=='failed' and saved['status']=='incomplete'
    assert asyncio.run(TaskOutcome('task-1',1).aafter_agent({'messages':[]},None)) is None


def test_tool_arg_normalization_parses_object_strings(host):
    from langchain.messages import ToolMessage
    from langchain.tools import tool
    from langchain.tools.tool_node import ToolCallRequest
    from backend.middleware.recovery import ToolArgNormalization

    @tool
    def save(result: dict) -> dict:
        """save"""
        return {}

    seen = {}
    async def handler(request):
        seen.update(request.tool_call['args'])
        return ToolMessage(content='ok', tool_call_id='1', name='save')
    request = ToolCallRequest(
        tool_call=dict(name='save', args={'result': '{"a": 1}'}, id='1', type='tool_call'),
        tool=save, state={}, runtime=None)
    asyncio.run(ToolArgNormalization().awrap_tool_call(request, handler))
    assert seen['result'] == {'a': 1}


def test_identical_failed_tool_call_is_not_executed_twice(host):
    from langchain.messages import ToolMessage
    from backend.middleware.dispatch import DispatchPolicy
    from backend.tests.test_host import request_for
    repo, _, task = host
    calls = []
    async def handler(request):
        calls.append(1)
        return ToolMessage(content='bad args', tool_call_id=request.tool_call['id'],
                           name=request.tool_call['name'], status='error')
    middleware = DispatchPolicy('task-1', 1)
    first = asyncio.run(middleware.awrap_tool_call(request_for('write_todos', todos=[]), handler))
    second = asyncio.run(middleware.awrap_tool_call(request_for('write_todos', todos=[]), handler))
    assert len(calls) == 1
    assert first.status == 'error' and second.status == 'error'
    assert '相同的参数' in second.content


def test_applied_human_edit_does_not_jump_to_end(host):
    from backend.middleware.conversation import ConversationReplies
    repo, _, task = host
    reply_id = str(uuid4())
    repo.mutate('task', 'task-1', lambda t: t.update(status='processing', conversation=[dict(
        id=reply_id, text='金额改为100', revision=1, state='starting', kind='ask_user',
        model_seen=True, question='金额', turn_model_calls=1,
        proposal=dict(action='edit', operations=[
            dict(op='set', charge_id='c1', field='amount', value=100)]))]))
    result = asyncio.run(ConversationReplies('task-1', 1, task['capability']).aafter_agent(
        {'messages': []}, None))
    assert result and 'jump_to' not in result
    assert repo.get('task', 'task-1')['revision'] == 2


def test_structured_decision_is_applied_without_the_agent_loop(host, monkeypatch):
    from langgraph.checkpoint.memory import InMemorySaver
    from langchain.agents import create_agent
    from backend.middleware.conversation import ConversationReplies
    from backend.middleware.decision import FieldEdit, ReplyDecision
    from backend.middleware.reply_decision import ReplyDecisionMiddleware
    repo, _, task = host
    reply_id = str(uuid4())
    repo.mutate('task', 'task-1', lambda t: t.update(
        status='processing', review_request={}, conversation=[dict(
            id=reply_id, text='随便说说', revision=1, state='starting',
            kind='conversation_review', model_seen=False, question='请核对',
            turn_model_calls=0)]))
    async def fake(self, request, task, reply):
        return ReplyDecision(action='apply', fields=[FieldEdit(field='currency', value='USD')])
    monkeypatch.setattr(ReplyDecisionMiddleware, 'structured_decision', fake)
    calls = []
    def respond(body):
        calls.append(body)
        return dict(role='assistant', content='不应调用')
    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            conversation = ConversationReplies('task-1', 1, task['capability'])
            graph = create_agent(model, tools=[],
                middleware=[conversation, ReplyDecisionMiddleware(
                    'task-1', 1, task['capability'], conversation.record_tool)],
                checkpointer=InMemorySaver())
            await graph.ainvoke({'messages': [{'role': 'user', 'content': '继续'}]},
                                {'configurable': {'thread_id': 'structured-reply'}})
        finally:
            await http.aclose()
    asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert calls == []
    assert saved['revision'] == 2
    assert saved['records'][0]['charge_details']['currency'] == 'USD'


def reply_middleware(host, monkeypatch, text, decision=None, records=1):
    """Build the middleware with a real repo row and a capturing record tool."""
    from backend.middleware.reply_decision import ReplyDecisionMiddleware
    repo, _, task = host
    reply_id = str(uuid4())

    def arrange(current):
        rows = current['records'] if records == 1 else [
            dict(deepcopy(current['records'][0]), charge_id=f'c{index + 1}')
            for index in range(records)]
        current.update(status='awaiting_input', records=rows, review_request={},
                       conversation=[dict(
                           id=reply_id, text=text, revision=1, state='starting',
                           kind='conversation_review', model_seen=False,
                           question='本次为哪家公司记账？', turn_model_calls=0)])
    repo.mutate('task', 'task-1', arrange)
    seen = []

    class RecordTool:
        def invoke(self, payload):
            seen.append(payload)
            return dict(proposed=True)

    async def fake(self, request, task, reply):
        if decision is None:
            raise AssertionError('the model must not be asked for this reply')
        return decision

    monkeypatch.setattr(ReplyDecisionMiddleware, 'structured_decision', fake)
    middleware = ReplyDecisionMiddleware('task-1', 1, task['capability'], RecordTool())
    return middleware, seen, reply_id


def test_candidate_entity_sentence_is_applied_without_a_model_call(host, monkeypatch):
    middleware, seen, _ = reply_middleware(
        host, monkeypatch, '本次记账主体是NEPTUNE SHIPPING LIMITED。', records=3)

    async def handler(request):
        raise AssertionError('the agent loop must not run')

    asyncio.run(middleware.awrap_model_call(SimpleNamespace(), handler))
    assert seen == [dict(
        reply_id=seen[0]['reply_id'], action='edit', operations=None,
        set_accounting_entity=True, accounting_entity='NEPTUNE SHIPPING LIMITED', resolves_pending=False)]


def test_model_invented_null_fields_are_dropped_and_the_entity_is_applied(host, monkeypatch):
    from backend.middleware.decision import FieldEdit, ReplyDecision
    decision = ReplyDecision(action='apply', accounting_entity='Client', fields=[
        FieldEdit(field='posting_type', value=None),
        FieldEdit(field='payment_term', value=None)])
    middleware, seen, _ = reply_middleware(
        host, monkeypatch, '本次记账主体是Client。', decision=decision, records=3)
    # The deterministic sentence path wins before the model is consulted.
    asyncio.run(middleware.awrap_model_call(SimpleNamespace(), lambda request: None))
    assert seen[0]['operations'] is None
    assert seen[0]['accounting_entity'] == 'Client'

    middleware, seen, _ = reply_middleware(
        host, monkeypatch, '记账主体用Client', decision=decision, records=3)
    asyncio.run(middleware.awrap_model_call(SimpleNamespace(), lambda request: None))
    assert seen[0]['operations'] is None
    assert seen[0]['accounting_entity'] == 'Client'


def test_explicit_absence_keeps_the_null_edit(host, monkeypatch):
    from backend.middleware.decision import FieldEdit, ReplyDecision
    decision = ReplyDecision(action='apply', fields=[FieldEdit(field='payment_term', value=None)])
    middleware, seen, _ = reply_middleware(
        host, monkeypatch, '付款方式没有，留空', decision=decision, records=1)
    asyncio.run(middleware.awrap_model_call(SimpleNamespace(), lambda request: None))
    assert seen[0]['operations'] == [dict(op='set', charge_id='c1', field='payment_term', value=None)]
    assert seen[0]['accounting_entity'] is None


def test_structured_multi_charge_edits_keep_their_targets(host, monkeypatch):
    from backend.middleware.decision import FieldEdit, ReplyDecision
    decision = ReplyDecision(action='apply', accounting_entity='Carrier', fields=[
        FieldEdit(charge_id='c1', field='payment_term', value=None),
        FieldEdit(charge_id='c2', field='quantity', value=None)])
    middleware, seen, _ = reply_middleware(host, monkeypatch,
        '主体用Carrier，第一笔付款方式清空，第二笔数量清空', decision=decision, records=2)
    asyncio.run(middleware.awrap_model_call(SimpleNamespace(), lambda request: None))
    assert seen[0]['operations'] == [
        dict(op='set', charge_id='c1', field='payment_term', value=None),
        dict(op='set', charge_id='c2', field='quantity', value=None)]


def test_unscoped_multi_charge_edit_uses_native_agent_without_staging(host, monkeypatch):
    from backend.middleware.decision import FieldEdit, ReplyDecision
    decision = ReplyDecision(action='apply', fields=[FieldEdit(field='amount', value=20)])
    middleware, seen, _ = reply_middleware(host, monkeypatch,
        '第二笔金额改20', decision=decision, records=2)
    called = []
    async def handler(request):
        called.append(request)
        return 'native'
    assert asyncio.run(middleware.awrap_model_call(SimpleNamespace(), handler)) == 'native'
    assert len(called) == 1 and not seen


def test_rejected_reply_proposal_returns_to_model_instead_of_completing(host):
    from backend.middleware.conversation import ConversationReplies
    repo, _, task = host
    reply_id = str(uuid4())
    repo.mutate('task', 'task-1', lambda t: t.update(review_request={}, conversation=[dict(
        id=reply_id, text='修改第二笔', revision=1, state='proposed', kind='conversation_review',
        model_seen=True, retry_count=1, last_error='缺少费用ID；可用费用：c1, c2')]))
    result = asyncio.run(ConversationReplies('task-1', 1, task['capability']).aafter_agent(
        {'messages': []}, None))
    assert result['jump_to'] == 'model'
    assert repo.get('task', 'task-1')['conversation'][0]['state'] == 'proposed'


def test_targeted_structured_reply_commits_multiple_rows_through_native_graph(host, monkeypatch):
    from langgraph.checkpoint.memory import InMemorySaver
    from langchain.agents import create_agent
    from backend.middleware.conversation import ConversationReplies
    from backend.middleware.decision import FieldEdit, ReplyDecision
    from backend.middleware.reply_decision import ReplyDecisionMiddleware
    repo, _, task = host
    reply_id = str(uuid4())
    def arrange(current):
        second = dict(deepcopy(current['records'][0]), charge_id='c2', quantity=11)
        current['records'].append(second)
        current.update(status='processing', review_request={}, conversation=[dict(
            id=reply_id, text='第一笔付款方式清空，第二笔数量清空', revision=1,
            state='starting', kind='conversation_review', model_seen=False,
            question='核对费用', turn_model_calls=0)])
    repo.mutate('task', 'task-1', arrange)
    async def classify(self, request, current, reply):
        return ReplyDecision(action='apply', fields=[
            FieldEdit(charge_id='c1', field='payment_term', value=None),
            FieldEdit(charge_id='c2', field='quantity', value=None)])
    monkeypatch.setattr(ReplyDecisionMiddleware, 'structured_decision', classify)
    calls = []
    def respond(body):
        calls.append(body)
        raise AssertionError('successful structured decision must need no extra model request')
    async def run():
        model, client = offline_model(monkeypatch, 'task-1', respond)
        try:
            conversation = ConversationReplies('task-1', 1, task['capability'])
            graph = create_agent(model, tools=[], middleware=[conversation,
                ReplyDecisionMiddleware('task-1', 1, task['capability'], conversation.record_tool)],
                checkpointer=InMemorySaver())
            return await graph.ainvoke({'messages': [{'role': 'user', 'content': '继续'}]},
                {'configurable': {'thread_id': 'targeted-two-row-reply'}})
        finally:
            await client.aclose()
    result = asyncio.run(run())
    saved = repo.get('task', 'task-1')
    assert saved['revision'] == 2 and not result.get('__interrupt__') and not calls
    assert saved['conversation'][0]['state'] == 'completed'
    by_id = {r['charge_id']: r for r in saved['records']}
    assert by_id['c1']['charge_details']['payment_term'] is None
    assert by_id['c2']['quantity'] is None
    assert by_id['c1']['charge_details']['amount'] == by_id['c2']['charge_details']['amount'] == 100


def test_pure_role_reply_maps_to_ar_without_reopening_the_question(host, monkeypatch):
    repo, _, _ = host
    middleware, seen, _ = reply_middleware(host, monkeypatch, '是收款方', records=2)
    repo.mutate('task', 'task-1', lambda current: current.update(
        accounting_entity='NEPTUNE SHIPPING LIMITED'))

    async def handler(request):
        raise AssertionError('the role answer must not need the model')

    asyncio.run(middleware.awrap_model_call(SimpleNamespace(), handler))
    operations = seen[0]['operations']
    assert [op['field'] for op in operations] == [
        'creditor', 'posting_type', 'creditor', 'posting_type']
    assert {op['value'] for op in operations if op['field'] == 'creditor'} == {
        'NEPTUNE SHIPPING LIMITED'}
    assert {op['value'] for op in operations if op['field'] == 'posting_type'} == {'AR'}


def test_role_variants_are_recognised_only_when_the_reply_is_pure():
    from backend.middleware.reply_decision import role_from_reply
    assert role_from_reply('是收款方') == 'AR'
    assert role_from_reply('付款方。') == 'AP'
    assert role_from_reply('本主体是付款方') == 'AP'
    assert role_from_reply('是AR') == 'AR'
    assert role_from_reply('付款方式改成CC') is None
    assert role_from_reply('本次记账主体是NEPTUNE是收款方。') is None


def test_pure_role_reply_commits_ar_and_does_not_reopen_the_question(host, monkeypatch):
    from langchain.agents import create_agent
    from backend.middleware.conversation import ConversationReplies
    from backend.middleware.reply_decision import ReplyDecisionMiddleware
    repo, _, task = host
    reply_id = str(uuid4())

    def arrange(current):
        current['accounting_entity'] = 'NEPTUNE SHIPPING LIMITED'
        for row in [*current['records'], *current['charges']]:
            row['creditor'] = 'NEPTUNE SHIPPING LIMITED'
            row['debtor'] = None
            if 'financial_attributes' in row:
                row['financial_attributes']['posting_type'] = None
        current.update(status='awaiting_input', review_request={}, conversation=[dict(
            id=reply_id, text='是收款方', revision=1, state='starting',
            kind='conversation_review', model_seen=False,
            question='请说明本主体是收款方还是付款方', turn_model_calls=0)])
    repo.mutate('task', 'task-1', arrange)
    calls = []

    async def no_model(self, request, task, reply):
        calls.append('model')
        raise AssertionError('a pure role answer must not need the model')

    monkeypatch.setattr(ReplyDecisionMiddleware, 'structured_decision', no_model)

    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1',
                                    lambda body: dict(role='assistant', content='不应调用'))
        try:
            conversation = ConversationReplies('task-1', 1, task['capability'])
            graph = create_agent(model, tools=[], middleware=[conversation,
                ReplyDecisionMiddleware('task-1', 1, task['capability'], conversation.record_tool)],
                checkpointer=InMemorySaver())
            await graph.ainvoke({'messages': [{'role': 'user', 'content': '继续'}]},
                                {'configurable': {'thread_id': 'role-answer'}})
        finally:
            await http.aclose()
    asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert calls == []
    assert saved['revision'] == 2
    assert all(r['financial_attributes']['posting_type'] == 'AR' for r in saved['records'])
    assert all(r['creditor'] == 'NEPTUNE SHIPPING LIMITED' for r in saved['records'])
    assert (saved.get('review_request') or {}).get('state') != 'pending'


@pytest.mark.parametrize('entity', ['NEPTUNE SHIPPING LIMITED', 'TAR', 'SHA'])
def test_candidate_entity_sentence_commits_a_revision_without_the_model(host, monkeypatch, entity):
    """The exact failure of task daca: one entity sentence, three charges."""
    from langchain.agents import create_agent
    from backend.middleware.conversation import ConversationReplies
    from backend.middleware.reply_decision import ReplyDecisionMiddleware
    repo, _, task = host
    reply_id = str(uuid4())

    def arrange(current):
        second = deepcopy(current['charges'][0])
        second.update(charge_id='c2', line_id='line2', amount=Decimal('55'))
        current['charges'].append(second)
        current['records'].append(dict(deepcopy(current['records'][0]), charge_id='c2',
                                       charge_details=dict(current['records'][0]['charge_details'],
                                                           amount=55)))
        current.update(status='awaiting_input', review_request=dict(
            action='entity', field='accounting_entity', choices=[entity]), conversation=[dict(
            id=reply_id, text=f'本次记账主体是{entity}。', revision=1, conversational=True,
            state='starting', kind='conversation_review', model_seen=False,
            question='本次为哪家公司记账？', turn_model_calls=0)])
    repo.mutate('task', 'task-1', arrange)
    calls = []

    async def no_model(self, request, task, reply):
        calls.append('model')
        raise AssertionError('the entity sentence must not need the model')

    monkeypatch.setattr(ReplyDecisionMiddleware, 'structured_decision', no_model)

    def respond(body):
        calls.append('http')
        return dict(role='assistant', content='不应调用')

    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            conversation = ConversationReplies('task-1', 1, task['capability'])
            graph = create_agent(model, tools=[],
                middleware=[conversation, ReplyDecisionMiddleware(
                    'task-1', 1, task['capability'], conversation.record_tool)],
                checkpointer=InMemorySaver())
            await graph.ainvoke({'messages': [{'role': 'user', 'content': '继续'}]},
                                {'configurable': {'thread_id': 'entity-sentence'}})
        finally:
            await http.aclose()
    asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert calls == []
    assert saved['revision'] == 2
    assert saved['accounting_entity'] == entity
    assert {r['financial_attributes']['accounting_entity'] for r in saved['records']} == {
        entity}


@pytest.mark.parametrize('entity', ['TAR', 'SHA'])
def test_entity_choice_does_not_authorize_model_party_edits(entity):
    from backend.middleware.conversation import _normalise_review_operations
    from backend.middleware.reply_decision import entity_from_reply
    task = dict(records=[dict(charge_id='c1')], review_request=dict(choices=[entity]))
    assert entity_from_reply(task, dict(text=entity)) == entity
    edits, ignored = _normalise_review_operations(task, [
        dict(op='set', charge_id='c1', field='creditor', value='guessed company'),
        dict(op='set', charge_id='c1', field='posting_type', value='AR')],
        f'本次记账主体是{entity}。')
    assert edits == [] and ignored == ['creditor', 'posting_type']
    edits, _ = _normalise_review_operations(task, [
        dict(op='set', charge_id='c1', field='posting_type', value='AR')], '本主体是AR')
    assert len(edits) == 1


@pytest.mark.parametrize('op', [None, 'update'])
def test_invalid_operation_schema_can_be_corrected_in_native_loop(host, monkeypatch, op):
    from langchain.agents import create_agent
    from backend.middleware.conversation import ConversationReplies
    repo, _, task = host
    reply_id = str(uuid4())
    repo.mutate('task', 'task-1', lambda t: t.update(review_request={}, conversation=[dict(
        id=reply_id, text='本次记账主体是TAR。', revision=1, state='starting',
        kind='conversation_review', model_seen=False, turn_model_calls=0)]))
    calls = []
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            edit = dict(charge_id='c1', field='creditor', value='unrequested company')
            if op is not None:
                edit['op'] = op
            return proposed_call('record_review_decision', dict(reply_id=reply_id,
                action='edit', operations=[edit], set_accounting_entity=True,
                accounting_entity='TAR'), 'bad-operation')
        if len(calls) == 2:
            saved = repo.get('task', 'task-1')
            assert not saved['conversation'][0].get('decision_error')
            assert saved['revision'] == 1
            assert 'operations' in str(body['messages'][-1]['content'])
            return proposed_call('record_review_decision', dict(reply_id=reply_id,
                action='edit', set_accounting_entity=True, accounting_entity='TAR'), 'fixed')
        return dict(role='assistant', content='主体提案已记录')
    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            graph = create_agent(model, tools=[], middleware=[
                ConversationReplies('task-1', 1, task['capability'])], checkpointer=InMemorySaver())
            await graph.ainvoke({'messages': [{'role': 'user', 'content': '继续'}]},
                {'configurable': {'thread_id': 'operation-schema'}})
        finally:
            await http.aclose()
    asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert len(calls) == 3 and saved['revision'] == 2
    assert saved['accounting_entity'] == 'TAR'
    assert saved['conversation'][0]['state'] == 'completed'
    assert not saved['conversation'][0].get('decision_error')


def test_entity_guard_leaves_role_and_mixed_sentences_to_the_model():
    from backend.middleware.reply_decision import entity_from_reply
    task = {'review_request': {'choices': ['Acme', 'NEPTUNE SHIPPING LIMITED']}}
    assert entity_from_reply(
        task, {'text': '本次记账主体是NEPTUNE SHIPPING LIMITED。'}) == 'NEPTUNE SHIPPING LIMITED'
    assert entity_from_reply(task, {'text': 'Acme。'}) == 'Acme'
    assert entity_from_reply(
        task, {'text': '本次记账主体是湃乐多是收款方（TAR）。'}) is None
    assert entity_from_reply(
        task, {'text': '本次记账主体是Acme，金额改成50。'}) is None
    assert entity_from_reply(task, {'text': '暂缓'}) is None


def test_missing_charge_id_with_several_records_is_rejected_with_options():
    from langchain_core.tools import ToolException
    from backend.middleware.conversation import _normalise_review_operations
    task = {'records': [dict(charge_id='c1'), dict(charge_id='c2')]}
    with pytest.raises(ToolException) as raised:
        _normalise_review_operations(task, [dict(op='set', field='amount', value=1)], '')
    assert '请指定要修改的费用' in str(raised.value)
    assert 'c1' in str(raised.value) and 'c2' in str(raised.value)


def test_tool_validation_error_is_returned_to_the_model(host):
    from backend.middleware.dispatch import DispatchPolicy
    from backend.tests.test_host import request_for
    repo, _, task = host
    calls = []
    async def handler(request):
        calls.append(1)
        raise ValueError('材料不属于当前任务')
    result = asyncio.run(DispatchPolicy('task-1', 1).awrap_tool_call(
        request_for('intake_documents', asset_ids=['x']), handler))
    assert result.status == 'error'
    assert '工具参数或业务校验失败' in result.content
    assert len(calls) == 1


def test_intake_uses_the_task_assets_not_model_typos(host):
    from backend.tools.skill_bindings import tools_for
    repo, _, task = host
    common, business = tools_for('task-1', task['capability'])
    intake = next(item for item in [*common, *business]
                  if getattr(item, 'name', None) == 'intake_documents')
    result = asyncio.run(intake.ainvoke(
        {'asset_ids': ['644d3f08-wrong'], 'include_content': False}))
    assert isinstance(result, dict) and result.get('sources') == []


def test_require_idle_tolerates_missing_run_metadata(host, monkeypatch):
    import httpx
    from langgraph_sdk.errors import NotFoundError
    from backend.api.task_runtime import require_idle
    repo, _, task = host
    sdk, _ = setup_server(monkeypatch, repo)
    repo.mutate('task', 'task-1', lambda t: t.update(run_id='lost-run'))
    request = httpx.Request('GET', 'http://test/runs/lost-run')
    sdk.runs.get.side_effect = NotFoundError(
        'missing', response=httpx.Response(404, request=request), body=None)
    asyncio.run(require_idle(repo.get('task', 'task-1')))


def test_reply_recovers_by_saving_candidates_then_retrying_the_edit(host, monkeypatch):
    """Skill-driven recovery: the reply tool's error tells the Agent to save
    candidates first; the Agent can then retry the same edit."""
    from langgraph.checkpoint.memory import InMemorySaver
    from langchain.agents import create_agent
    from backend.middleware.conversation import ConversationReplies
    repo, _, task = host
    cap = repo.get('task', 'task-1')['capability']
    repo.mutate('task', 'task-1', lambda t: t.update(
        charges=[], records=[], status='processing', review_request={},
        conversation=[dict(id=str(uuid4()), text='本次记账主体是Client。', revision=1,
                           state='starting', kind='ask_user', model_seen=False,
                           question='主体', turn_model_calls=0)]))
    reply_id = repo.get('task', 'task-1')['conversation'][0]['id']
    module = skill_bindings.skill_module('document-extraction', cap['version'])
    refs = module.citation_index(repo.get('task', 'task-1'))
    rid = next(k for k, r in refs.items() if 'THC' in r['quote'])
    _, business = skill_bindings.tools_for(task['id'], cap)
    save = next(t for t in business if t.name == 'save_document_extraction')
    calls = []
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return proposed_call('record_review_decision', dict(
                reply_id=reply_id, action='edit', set_accounting_entity=True,
                accounting_entity='Client'), 'entity-first')
        if len(calls) == 2:
            assert '请先保存候选费用' in str(body['messages'][-1]['content'])
            return proposed_call('save_document_extraction', dict(result=dict(charges=[dict(
                source_id='doc', line_id='line1', charge_item='THC', amount=100,
                currency='USD', creditor='Carrier', debtor='Client',
                evidence=[dict(ref_id=rid, fields=['charge_item', 'amount',
                                                   'currency', 'creditor', 'debtor'])])])), 'save')
        if len(calls) == 3:
            return proposed_call('record_review_decision', dict(
                reply_id=reply_id, action='edit', set_accounting_entity=True,
                accounting_entity='Client'), 'entity-retry')
        return dict(role='assistant', content='主体已应用')
    async def exercise():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            graph = create_agent(model, tools=[save],
                middleware=[ConversationReplies('task-1', 1, cap)],
                checkpointer=InMemorySaver())
            await graph.ainvoke({'messages': [{'role': 'user', 'content': '继续'}]},
                                {'configurable': {'thread_id': 'reply-recovery'}})
        finally:
            await http.aclose()
    asyncio.run(exercise())
    saved = repo.get('task', 'task-1')
    assert len(calls) == 4
    assert saved['revision'] == 2 and saved['accounting_entity'] == 'Client'
    assert saved['records'] and saved['conversation'][0]['state'] == 'completed'


def test_empty_tool_call_ids_are_normalized(monkeypatch):
    from langchain.agents.middleware.types import ModelRequest, ModelResponse
    from langchain.messages import AIMessage
    from backend.middleware.recovery import ToolCallIdNormalization
    async def handler(request):
        return ModelResponse(result=[AIMessage(content='', tool_calls=[
            {'name': 'x', 'args': {}, 'id': '', 'type': 'tool_call'}])], structured_response={'keep': True})
    result = asyncio.run(ToolCallIdNormalization().awrap_model_call(
        ModelRequest(model=None, messages=[], tools=[], runtime=None), handler))
    assert result.result[0].tool_calls[0]['id']
    assert result.structured_response == {'keep': True}


def test_edit_payload_with_non_edit_label_is_applied_as_edit(host):
    from backend.middleware.conversation import ConversationReplies
    repo, _, task = host
    reply_id = str(uuid4())
    repo.mutate('task', 'task-1', lambda t: t.update(conversation=[dict(
        id=reply_id, text='本次主体是Client', revision=1, state='starting',
        kind='conversation_review', model_seen=True, question='主体', turn_model_calls=1)]))
    middleware = ConversationReplies('task-1', 1, task['capability'])
    result = middleware.tools[0].invoke(dict(
        reply_id=reply_id, action='answer', set_accounting_entity=True,
        accounting_entity='Client'))
    assert result['proposed'] is True and result['action'] == 'edit'


def test_human_reply_turn_stops_at_configured_model_limit(host):
    from copy import deepcopy
    from langchain.agents.middleware.types import ModelRequest
    from langchain.messages import AIMessage
    from backend.middleware.conversation import ConversationReplies
    repo,_,task=host
    cap=deepcopy(task['capability'])
    cap['config']['runtime']['turn_model_calls']=2
    reply_id=str(uuid4())
    repo.mutate('task','task-1',lambda t:t.update(conversation=[dict(
        id=reply_id,text='请帮我核对一下这些费用',revision=1,state='starting',kind='conversation_review',
        model_seen=False,question='请核对',turn_model_calls=2)]))
    called=[]
    async def handler(request):
        called.append(1)
        return AIMessage(content='不应调用')
    middleware=ConversationReplies('task-1',1,cap)
    result=asyncio.run(middleware.awrap_model_call(
        ModelRequest(model=None,messages=[],tools=[],runtime=None),handler))
    assert not called
    assert '上限' in result.content
    assert repo.get('task','task-1')['conversation'][0]['decision_error']
