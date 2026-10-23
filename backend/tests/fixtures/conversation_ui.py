"""Isolated native Agent Server/UI fixture. No real bills, OCR, or remote model."""
import asyncio
import json
import time
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langgraph_sdk import get_client

from backend.api import task_runtime
from backend.api.routes import conversation,confidence
from backend.extensions.snapshots import snapshot
from backend.extensions.skill_versions import function
from backend.infrastructure.repository import dumps,now
from backend.middleware.conversation import ConversationReplies
from backend.tools.human_input import human_input_tool
from backend.tests.test_host import FakeRepository
from backend.tools import artifacts,review as review_runtime
from backend.harness import dispatch

repo=FakeRepository()
for module in (conversation,confidence,task_runtime,artifacts,review_runtime,dispatch):
    module.repository=lambda:repo
import backend.middleware.conversation as conversation_middleware
conversation_middleware.repository=lambda:repo
client=get_client(url='http://127.0.0.1:2025')
conversation.sdk=lambda:client
task_runtime.sdk=lambda:client


def call(text,name,args,id):
    return AIMessage(content=text,additional_kwargs={'tool_calls':[dict(id=id,type='function',
        function={'name':name,'arguments':json.dumps(args,ensure_ascii=False)})]})


def answers():
    if repo.get('task','conversation-ui').get('entity_choice_fixture'):
        yield '已提取合成账单的费用与原文。接下来确认本次记账公司。'
    else:
        yield call('已读取 **合成账单**，需要您核对一处信息。','ask_user',{'question':'请告诉我正确的记账主体和第一项费用金额。'},'fixture-question')
    for index in range(10):
        reply=repo.get('task','conversation-ui')['conversation'][-1]
        entity='Unrelated' if 'Unrelated' in reply['text'] else 'Client'
        edits=[] if repo.get('task','conversation-ui').get('entity_choice_fixture') else [dict(op='set',charge_id='c1',field='amount',value=65)]
        if 'Unrelated是付款方' in reply['text']:
            edits.append(dict(op='set',charge_id='c1',field='debtor',value='Unrelated'))
        yield call('收到您的回复，正在核对并保存。','record_review_decision',dict(reply_id=reply['id'],action='edit',
            operations=edits, set_accounting_entity=True,accounting_entity=entity),f'fixture-revision-{index}')
        yield '已记录修改，后续以当前版本的核验结果为准。'


class FixtureModel(GenericFakeChatModel):
    def bind_tools(self,tools,**kwargs):return self
    def _stream(self,*args,**kwargs):
        for chunk in super()._stream(*args,**kwargs):
            time.sleep(.03)
            yield chunk


model=FixtureModel(messages=answers())

def make_graph():
    task=repo.get('task','conversation-ui',required=False)
    cap=task['capability'] if task else snapshot()
    return create_agent(model,tools=[human_input_tool()],middleware=[
        HumanInTheLoopMiddleware(interrupt_on={'ask_user':{'allowed_decisions':['respond','reject']}},interrupt_mode='per_call'),
        ConversationReplies('conversation-ui',task['revision'] if task else 1,cap)],name='workorder-agent')


app=FastAPI()
@app.middleware('http')
async def slow_synthetic_reply(request,call_next):
    # Expose optimistic sending in the browser against real native execution.
    if request.url.path.endswith('/reply'):
        await asyncio.sleep(3)
    return await call_next(request)
app.include_router(conversation.router)
app.include_router(confidence.router)
app.mount('/app',StaticFiles(directory=Path(__file__).resolve().parents[3]/'frontend'/'dist',html=True))
from backend.infrastructure.repository import Conflict
from backend.api.responses import response
@app.exception_handler(Conflict)
async def conflict(request,exc):return response({'message':str(exc)},409)
@app.exception_handler(ValueError)
async def invalid(request,exc):return response({'message':str(exc)},422)

@app.post('/fixture/start')
async def start(without_entity: bool = False):
    if repo.get('task','conversation-ui',required=False):return response(repo.get('task','conversation-ui'))
    cap=snapshot()
    cap=deepcopy(cap)
    cap['config']['runtime']['agent_style']='codex'
    thread=await client.threads.create(metadata={'application':'isolated-conversation-ui'})
    charge=dict(charge_id='c1',source_id='doc',line_id='line1',document_id='doc',charge_item='Handling',
        amount=Decimal(100),currency='USD',reference_no='TEST-001',creditor='Carrier',debtor='Client',
        issuer='Carrier',recipient='Client',evidence=[dict(source_id='doc',anchor='p1',quote='Handling USD 100')])
    task=dict(id='conversation-ui',title='会话交互验证 · 合成账单',revision=1,created_at=now(),updated_at=now(),
        control='running',status='queued',accounting_entity=None if without_entity else 'Client',
        entity_choice_fixture=without_entity,thread_id=thread['thread_id'],run_id=None,
        capability=cap,charges=[charge],records=[],sources=[dict(source_id='doc',name='合成材料.txt',format='text',status='ready',
        blocks=[dict(anchor='p1',text='Handling USD 100',authoritative=True)])],asset_ids=[],issues=[],intake_issues=[],
        chunks=[dict(chunk_id='chunk1',source_id='doc',anchor='p1')],coverage=[dict(chunk_id='chunk1',source_id='doc',anchor='p1',
        status='extracted',charge_ids=['c1'],reason='synthetic')],totals=[],existing_records=[],update_instructions=[],
        usage=dict(model_calls=0,tool_calls=0,active_seconds=0),approval=None,validation=None,export=None)
    task['extraction']={k:deepcopy(task[k]) for k in ('charges','coverage','totals','issues')}
    task['records']=function(cap,'billing-reconciliation','reconcile_charges')(task)['records']
    repo.objects['task','conversation-ui']=task
    if without_entity:
        artifacts.reconcile_saved('conversation-ui')
        review_runtime.settle_saved('conversation-ui')
        task=repo.get('task','conversation-ui')
    return response(await task_runtime.start_run(task,message='验证合成账单会话。'))

@app.get('/api/health')
def health():return {'status':'ok','services':{'database':{'status':'ok'},'redis':{'status':'ok'}},'model':'synthetic-native-fixture'}
@app.get('/api/assets')
def assets():return []
@app.get('/api/samples')
def samples():return []
@app.get('/api/bills')
@app.get('/api/tasks')
async def bills():
    task=repo.get('task','conversation-ui',required=False)
    return response([await task_runtime.sync_task(task)] if task else [])
@app.get('/api/tasks/{task_id}')
async def get_task(task_id:str):return response(await task_runtime.sync_task(repo.get('task',task_id)))
@app.get('/fixture/result')
def result():return response(repo.get('task','conversation-ui'))
