"""Real ZIP/config transactions and MCP stdio diagnostics in an isolated root."""
import asyncio
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import sys
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain.messages import AIMessage, ToolMessage
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from deepagents.backends import StateBackend
from deepagents.middleware import SkillsMiddleware, FilesystemMiddleware
import pytest

from backend.api.responses import response
from backend.api.routes import extensions
from backend.config import transactions
from backend.extensions import packages, snapshots, skill_versions
from backend.harness import dispatch
from backend.infrastructure.repository import Conflict
from backend.tests.test_configuration import config_root
from backend.tests.test_improvement import MemoryRepository


def archive(files):
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as output:
        for name, content in files.items():
            output.writestr(name, content)
    return buffer.getvalue()


def package_files():
    return {'probe/SKILL.md': '---\nname: audit-probe\ndescription: Add precise integers for a control audit\nmetadata:\n  version: "1.0.0"\n  include_tools: audit_add\n---\nRead references/usage.md and call audit_add.\n',
            'probe/references/usage.md': 'Add the two input integers. No model or network.',
            'probe/scripts/skill.py': 'def add(a: int, b: int) -> int:\n    """Add two exact integers."""\n    return a + b\n'}


@pytest.fixture
def host(config_root, monkeypatch):
    app = FastAPI()
    app.include_router(extensions.router)
    for exception, status in ((ValueError, 422), (Conflict, 409), (dispatch.PolicyDenied, 409), (KeyError, 404)):
        async def error(request, exc, code=status):
            return response({'message': str(exc)}, code)
        app.add_exception_handler(exception, error)
    with TestClient(app) as client:
        yield client


def test_import_native_discovery_tools_snapshot_and_disable(host, config_root, monkeypatch):
    version = transactions.read_config('skills')['version']
    imported = host.post('/api/extensions/skills/import', data={'expected_version': version,
        'tools': '[{"function":"add","name":"audit_add"}]'},
        files={'file': ('audit.zip', archive(package_files()), 'application/zip')})
    assert imported.status_code == 201, imported.text
    catalog = host.get('/api/extensions/skills').json()['skills']
    assert next(s for s in catalog if s['name'] == 'audit-probe')['registered']
    assert 'call audit_add' in host.get('/api/extensions/skills/audit-probe/resource').json()['content']
    assert host.get('/api/extensions/skills/audit-probe/resource', params={'path':'../../.env'}).status_code == 422
    repo = MemoryRepository()
    monkeypatch.setattr(snapshots, 'repository', lambda: repo)
    monkeypatch.setattr(snapshots, 'RELEASES', config_root / 'releases')
    monkeypatch.setattr(skill_versions, 'RELEASES', config_root / 'releases')
    cap = snapshots.snapshot()
    tools, owners = skill_versions.configured_tools(cap)
    assert owners['audit_add'] == 'audit-probe'
    class NativeFixtureModel(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self
    model = NativeFixtureModel(messages=iter([
        AIMessage(content='',tool_calls=[dict(name='read_file',args={'file_path':'/skills/audit-probe/SKILL.md'},id='read')]),
        AIMessage(content='',tool_calls=[dict(name='audit_add',args={'a':19,'b':23},id='add')]),
        AIMessage(content='完成')]))
    backend=StateBackend()
    graph=create_agent(model,tools=[],middleware=[FilesystemMiddleware(backend=backend,tools=['read_file']),
        SkillsMiddleware(backend=backend,sources=['/skills/'],tools=tools)])
    result=asyncio.run(graph.ainvoke({'messages':[{'role':'user','content':'使用audit-probe计算19+23'}],
        'files':skill_versions.skill_files(cap,names=['audit-probe'])}))
    executed=[m for m in result['messages'] if isinstance(m,ToolMessage) and m.name=='audit_add']
    assert len(executed)==1 and executed[0].content=='42'
    repo.create('task',dict(id='probe',revision=1,control='running'))
    monkeypatch.setattr(dispatch,'repository',lambda:repo)
    config = transactions.read_config('skills')
    next(s for s in config['skills'] if s['name']=='audit-probe')['enabled']=False
    transactions.write_config('skills',config,config['version'])
    with pytest.raises(dispatch.PolicyDenied,match='禁用'):
        dispatch.check('probe',skill='audit-probe')
    fresh=snapshots.snapshot()
    assert 'audit_add' not in skill_versions.configured_tools(fresh)[1]
    assert 'audit_add' in skill_versions.configured_tools(cap)[1]


def test_instruction_only_package_and_failed_install_rolls_back(host, config_root):
    version=transactions.read_config('skills')['version']
    files=package_files()
    files.pop('probe/scripts/skill.py')
    files['probe/SKILL.md']=files['probe/SKILL.md'].replace('  include_tools: audit_add\n','')
    result=host.post('/api/extensions/skills/import',data={'expected_version':version},
        files={'file':('text.zip',archive(files))})
    assert result.status_code==201,result.text
    assert host.post('/api/extensions/skills/import',data={'expected_version':version},
        files={'file':('same.zip',archive(files))}).status_code==409
    files=package_files()
    files['probe/SKILL.md']=files['probe/SKILL.md'].replace('audit-probe','other-probe')
    files['probe/SKILL.md']=files['probe/SKILL.md'].replace('  include_tools: audit_add\n','')
    result=host.post('/api/extensions/skills/import',data={'expected_version':version},
        files={'file':('stale.zip',archive(files))})
    assert result.status_code==409,result.text
    assert not (config_root/'skills'/'other-probe').exists()
    assert host.post('/api/extensions/skills/import',data={'expected_version':version},
        files={'file':('bad.zip',archive({'../../escape.py':'bad'}))}).status_code==422


def test_unbound_declared_tool_is_rejected_and_implicit_tool_name_executes(host, config_root, monkeypatch):
    files=package_files()
    version=transactions.read_config('skills')['version']
    missing=host.post('/api/extensions/skills/import',data={'expected_version':version},
        files={'file':('missing.zip',archive(files))})
    assert missing.status_code==422 and '未绑定' in missing.text
    assert not (config_root/'skills'/'audit-probe').exists()
    files['probe/SKILL.md']=files['probe/SKILL.md'].replace('audit_add','add')
    saved=host.post('/api/extensions/skills/import',data={'expected_version':version,'tools':'[{"function":"add"}]'},
        files={'file':('implicit.zip',archive(files))})
    assert saved.status_code==201,saved.text
    monkeypatch.setattr(snapshots,'repository',lambda:MemoryRepository())
    monkeypatch.setattr(snapshots,'RELEASES',config_root/'releases')
    monkeypatch.setattr(skill_versions,'RELEASES',config_root/'releases')
    tools,owners=skill_versions.configured_tools(snapshots.snapshot())
    bound=next(t for t in tools if t.name=='add')
    assert bound.invoke({'a':19,'b':23})==42 and owners['add']=='audit-probe'


def test_mcp_saved_transport_real_discovery_call_disable_remove(host, tmp_path):
    receipt=tmp_path/'receipts.jsonl'
    fixture=Path(__file__).parent/'fixtures'/'mcp_probe_server.py'
    server=dict(id='audit',enabled=True,transport=dict(command=sys.executable,args=['-B',str(fixture),str(receipt)]))
    config=transactions.read_config('mcp')
    config['servers'].append(server)
    saved=host.put('/api/config/mcp',json={'expected_version':config['version'],'config':config})
    assert saved.status_code==200,saved.text
    connected=host.post('/api/config/mcp/test',json={'server':server})
    assert connected.status_code==200,connected.text
    assert connected.json()['tools'][0]['name']=='calculate'
    called=host.post('/api/config/mcp/call',json=dict(server_id='audit',tool='calculate',arguments={'a':19,'b':23}))
    assert called.status_code==200 and '42' in called.text,called.text
    config=saved.json()
    next(s for s in config['servers'] if s['id']=='audit')['enabled']=False
    saved=host.put('/api/config/mcp',json={'expected_version':config['version'],'config':config})
    assert saved.status_code==200
    assert host.post('/api/config/mcp/call',json=dict(server_id='audit',tool='calculate',arguments={'a':1,'b':2})).status_code==409
    assert len(receipt.read_text().splitlines())==1
    config=saved.json();config['servers']=[s for s in config['servers'] if s['id']!='audit']
    assert host.put('/api/config/mcp',json={'expected_version':config['version'],'config':config}).status_code==200


def test_registered_hook_runs_and_live_disable_stops_it(host, config_root, monkeypatch):
    files=package_files()
    files['probe/scripts/skill.py'] += '\ndef validate(payload: dict) -> dict:\n    return {"valid": False, "issues": [{"code": "AUDIT_REJECT", "severity": "error"}]}\n'
    saved=host.post('/api/extensions/skills/import',data={'expected_version':transactions.read_config('skills')['version'],
        'tools':'[{"function":"add","name":"audit_add"}]'},files={'file':('hook.zip',archive(files))})
    assert saved.status_code==201,saved.text
    hooks=transactions.read_config('hooks')
    hooks['hooks'].append(dict(name='audit-validation',enabled=True,required=False,priority=115,
        skill='audit-probe',function='validate'))
    assert host.put('/api/config/hooks',json={'expected_version':hooks['version'],'config':hooks}).status_code==200
    monkeypatch.setattr(snapshots,'repository',lambda:MemoryRepository())
    monkeypatch.setattr(snapshots,'RELEASES',config_root/'releases')
    monkeypatch.setattr(skill_versions,'RELEASES',config_root/'releases')
    cap=snapshots.snapshot()
    from backend.hooks.validation import validate
    task=dict(id='hook-fixture',revision=1,capability=cap,charges=[],records=[])
    checked=validate(task)
    assert any(i['code']=='AUDIT_REJECT' for i in checked['issues'])
    hooks=transactions.read_config('hooks')
    next(h for h in hooks['hooks'] if h['name']=='audit-validation')['enabled']=False
    transactions.write_config('hooks',hooks,hooks['version'])
    assert not any(i['code']=='AUDIT_REJECT' for i in validate(task)['issues'])


def test_unreachable_mcp_connection_returns_a_diagnostic_without_registering(host):
    before=transactions.read_config('mcp')
    result=host.post('/api/config/mcp/test',json={'server':dict(id='unreachable',enabled=True,
        url='http://127.0.0.1:1/mcp')})
    assert result.status_code==502,result.text
    assert result.json()['ok'] is False
    assert transactions.read_config('mcp')==before


def test_new_configured_specialist_is_really_delegated_by_native_supervisor(host, config_root, monkeypatch):
    from types import SimpleNamespace
    from backend.agents import factory
    agents=transactions.read_config('agents')
    agents['agents'].append(dict(name='audit-expert',enabled=True,type='agent',description='Audit fixture expert',
        skills=[],prompt='Return the audit receipt.'))
    assert host.put('/api/config/agents',json={'expected_version':agents['version'],'config':agents}).status_code==200
    monkeypatch.setattr(snapshots,'repository',lambda:MemoryRepository())
    monkeypatch.setattr(snapshots,'RELEASES',config_root/'releases')
    monkeypatch.setattr(skill_versions,'RELEASES',config_root/'releases')
    class Model(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self
    model=Model(messages=iter([
        AIMessage(content='',tool_calls=[dict(name='task',args={'subagent_type':'audit-expert',
            'description':'Return the audit receipt.'},id='delegate')]),
        AIMessage(content='AUDIT_SPECIALIST_RECEIPT'),AIMessage(content='委派已完成')]))
    class Client:
        async def aclose(self):
            pass
    monkeypatch.setattr(factory,'make_model',lambda *args:(model,Client()))
    async def execute():
        async with factory.make_graph({},SimpleNamespace(execution_runtime=False)) as graph:
            return await graph.ainvoke({'messages':[{'role':'user','content':'委派audit-expert'}]})
    result=asyncio.run(execute())
    delegated=[m for m in result['messages'] if isinstance(m,ToolMessage) and m.name=='task']
    assert len(delegated)==1 and 'AUDIT_SPECIALIST_RECEIPT' in str(delegated[0].content)
