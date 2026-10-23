"""Offline host integration checks; production storage remains GaussDB.

Native API evidence: Docs MCP /oss/python/langchain/test/unit-testing and
/middleware/custom; Reference MCP ToolCallRequest and ChatOpenAI. Verified with
langchain 1.4.6, langgraph 1.2.16, langchain-openai 1.7.2, deepagents 0.7.29.
Only network/storage boundaries are replaced, never the agent execution loop.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
from threading import Barrier, RLock
from types import SimpleNamespace

from fastapi.testclient import TestClient
import httpx
from langchain.messages import ToolMessage
from langchain.agents.middleware import ToolRetryMiddleware
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain.tools import tool
from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from langgraph.prebuilt.tool_node import ToolCallRequest
import pytest

from backend.api import app
from backend.api.routes import assets, confidence, exports, reviews, tasks
from backend.extensions import snapshots, skill_versions
from backend.harness import budget, dispatch, timing
from backend.hooks import registry, validation
from backend.infrastructure import models
from backend.infrastructure.repository import Conflict
from backend.middleware import dispatch as dispatch_middleware, mcp_tools
from backend.middleware import outcome
from backend.middleware import feedback as feedback_middleware
from backend.middleware import conversation as conversation_middleware
from backend.middleware import handoff as handoff_middleware
from backend.api.routes import conversation as conversation_routes
from backend.tools import artifacts, context, skill_bindings
from backend.tools import review as review_runtime


class FakeRepository:
    """Copy-on-write transactions matching the production repository contract."""

    def __init__(self):
        self.objects = {}
        self.receipts = []
        self.lock = RLock()

    def get(self, kind, object_id, required=True):
        with self.lock:
            result = self.objects.get((kind, object_id))
            if result is None and required:
                raise KeyError(object_id)
            return deepcopy(result)

    def mutate(self, kind, object_id, transform, expected_revision=None):
        with self.lock:
            current = self.get(kind, object_id)
            if expected_revision is not None and current['revision'] != expected_revision:
                raise Conflict('记录已更新，请刷新后重试')
            replacement = transform(current)
            current = current if replacement is None else replacement
            self.objects[kind, object_id] = deepcopy(current)
            return deepcopy(current)

    def event(self, task_id, event, **values):
        with self.lock:
            self.receipts.append(dict(task_id=task_id, event=event, **deepcopy(values)))

    def events(self, task_id, limit=100):
        return deepcopy([e for e in self.receipts if e['task_id'] == task_id][-limit:])

    def list(self, kind, limit=100):
        with self.lock:
            return [deepcopy(value) for (key, _), value in self.objects.items() if key == kind][:limit]

    def list_projection(self, kind, fields, *, arrays=None, limit=100, exclude_deleted=False):
        rows = self.list(kind, limit=limit)
        return [{**{k: row.get(k) for k in fields},
                 **{k: [{field: item.get(field) for field in selected if field in item}
                        for item in row.get(k, [])] for k, selected in (arrays or {}).items()}}
                for row in rows if not exclude_deleted or not row.get('deleted_at')]


@pytest.fixture
def host(monkeypatch, tmp_path):
    """Use real portable Skills and hooks against an isolated transactional store."""
    for key, value in dict(LLM_MODEL_NAME='offline-test', LLM_API_KEY='offline-test-key',
                           LLM_BASE_URL='https://offline.invalid/v1',
                           REDIS_URL='redis://offline.invalid:6379/0').items():
        monkeypatch.setenv(key, value)
    repo = FakeRepository()
    monkeypatch.setattr(skill_bindings, 'DATA', tmp_path / 'data')
    for module in (snapshots, skill_versions):
        monkeypatch.setattr(module, 'RELEASES', tmp_path / 'releases')
    for module in (snapshots, skill_bindings, artifacts, context, dispatch,
                   budget, timing, dispatch_middleware, assets, confidence, tasks, reviews, exports, review_runtime, outcome,
                   feedback_middleware, conversation_middleware, conversation_routes, handoff_middleware):
        monkeypatch.setattr(module, 'repository', lambda: repo)
    monkeypatch.setattr(validation, 'repository', lambda: repo, raising=False)
    monkeypatch.setattr(sys.modules['backend.api.app'], 'repository', lambda: repo)
    cap = snapshots.snapshot()
    live = deepcopy(cap['config'])
    for module in (snapshots, skill_versions, dispatch, registry,
                   dispatch_middleware, mcp_tools):
        monkeypatch.setattr(module, 'read_config', lambda kind: deepcopy(live[kind]))

    charge = dict(charge_id='c1', source_id='doc', line_id='line1', document_id='doc',
                  charge_item='THC', amount=Decimal('100'), currency='USD', reference_no='INV-1',
                  creditor='Carrier', debtor='Client', issuer='Carrier', recipient='Client',
                  evidence=[dict(source_id='doc', anchor='p1', quote='THC USD 100')])
    task = dict(id='task-1', revision=1, control='running', status='awaiting_review',
                capability=cap, usage=dict(model_calls=0, tool_calls=0, active_seconds=0),
                accounting_entity='Client', reason='核对原件', asset_ids=[], run_id=None,
                existing_records=[], update_instructions=[], records=[], charges=[charge],
                sources=[dict(source_id='doc', status='ready', blocks=[
                    dict(anchor='p1', text='THC USD 100', authoritative=True)])],
                chunks=[dict(chunk_id='chunk1', source_id='doc', anchor='p1')],
                coverage=[dict(source_id='doc', anchor='p1', chunk_id='chunk1',
                               status='extracted', reason='已逐行提取', charge_ids=['c1'])],
                totals=[], issues=[], intake_issues=[], approval=None, validation=None, export=None)
    linked = skill_versions.function(cap, 'evidence-linking', 'link_evidence')(task)
    assert linked['valid']
    task['charges'] = linked['charges']
    task['extraction'] = {k: deepcopy(task[k]) for k in ('charges', 'coverage', 'totals', 'issues')}
    task['records'] = skill_versions.function(cap, 'billing-reconciliation', 'reconcile_charges')(task)['records']
    repo.objects['task', task['id']] = deepcopy(task)
    assert validation.validate(task)['ok']
    return repo, live, task


def request_for(name, **args):
    return ToolCallRequest(tool_call=dict(name=name, args=args, id='call-1', type='tool_call'),
                           tool=None, state={}, runtime=None)


def history_case(host):
    repo, _, task = host
    previous = deepcopy(task)
    previous.update(id='previous', status='completed', validation=dict(ok=True, revision=1))
    repo.objects['task', 'previous'] = previous
    repo.mutate('task', task['id'], lambda t: t.update(history_mode='automatic'))
    return repo, task


def test_automatic_history_is_used_by_native_reconcile_without_user_json(host):
    repo, task = history_case(host)
    audit = [dict(revision=1, history=[], reason='既有人工修订记录')]
    repo.mutate('task', task['id'], lambda t: t.update(history=deepcopy(audit)))
    result = artifacts.reconcile_saved(task['id'])
    current = repo.get('task', task['id'])
    assert current['history'] == audit
    assert current['records'][0]['operation'] == 'NO_CHANGE'
    assert current['history_lookup']['candidate_count'] == 1
    assert current['records'][0]['history_match']['task_id'] == 'previous'
    assert result['validation']['ok'], result['validation']['issues']
    assert context.context_tool(task['id']).invoke({})['history_lookup']['status'] == 'searched'


def test_automatic_history_amount_update_uses_original_values_for_unmodified_fields(host):
    repo, task = history_case(host)
    def old_values(previous):
        previous['records'][0]['charge_details'].update(amount=Decimal('80'), payment_term='CC')
        previous['records'][0]['document_info']['document_date'] = '2026-10-01'
    repo.mutate('task', 'previous', old_values)
    artifacts.reconcile_saved(task['id'], [dict(reference_no='INV-1', charge_item='THC', changes=dict(amount=100))])
    current = repo.get('task', task['id'])
    assert current['records'][0]['operation'] == 'UPDATE'
    assert current['records'][0]['charge_details']['amount'] == 100
    assert current['records'][0]['charge_details']['payment_term'] == 'CC'
    assert current['records'][0]['document_info']['document_date'] == '2026-10-01'
    assert current['validation']['ok'], current['validation']['issues']
    assert repo.get('task', 'previous')['records'][0]['charge_details']['amount'] == 80


def test_automatic_history_pins_mapping_for_validation_and_export(host, monkeypatch):
    repo, task = history_case(host)
    mapping = {'THC': 'Custom Fee', 'Terminal Handling Charge': 'Custom Fee'}
    repo.mutate('task', task['id'], lambda t: t['capability'].update(
        improvements={'active_version': 'offline-custom-mapping'}))
    resolve = artifacts.function
    def bound(capability, skill, operation):
        if (skill, operation) == ('feedback-improvement', 'resolve_mapping'):
            return lambda *args: mapping
        return resolve(capability, skill, operation)
    monkeypatch.setattr(artifacts, 'function', bound)
    result = artifacts.reconcile_saved(task['id'])
    current = repo.get('task', task['id'])
    assert current['charge_mapping'] == mapping
    assert current['records'][0]['operation'] == 'NO_CHANGE'
    assert result['validation']['ok'], result['validation']['issues']
    assert validation.validate(current)['ok']


def test_automatic_history_waits_for_entity_then_refreshes_without_another_model_call(host):
    repo, task = history_case(host)
    repo.mutate('task', task['id'], lambda t: t.update(accounting_entity=None))
    artifacts.reconcile_saved(task['id'])
    assert repo.get('task', task['id'])['history_lookup']['status'] == 'waiting_entity'
    repo.mutate('task', task['id'], lambda t: t.update(accounting_entity='Client', revision=2))
    artifacts.reconcile_saved(task['id'])
    current = repo.get('task', task['id'])
    assert current['records'][0]['operation'] == 'NO_CHANGE'
    assert current['history_lookup']['revision'] == 2
    assert current['usage']['model_calls'] == 0


def test_history_change_blocks_approval_and_export_until_reconciled(host):
    repo, task = history_case(host)
    artifacts.reconcile_saved(task['id'])
    repo.mutate('task', 'previous', lambda t: t.update(deleted_at='2026-10-23'))
    checked = validation.validate(repo.get('task', task['id']))
    assert not checked['ok']
    assert any(i['code'] == 'HISTORY_STALE' for i in checked['issues'])
    client = TestClient(app)
    assert approve(client, task['id']).status_code == 422
    assert client.get(f'/api/tasks/{task["id"]}/export').status_code == 422
    refreshed = artifacts.reconcile_saved(task['id'])
    assert refreshed['validation']['ok']
    assert repo.get('task', task['id'])['records'][0]['operation'] == 'CREATE'


def test_history_query_failure_never_becomes_empty_history(host, monkeypatch):
    repo, task = history_case(host)
    def unavailable(*args, **kwargs):
        raise RuntimeError('offline history store unavailable')
    monkeypatch.setattr(repo, 'list_projection', unavailable)
    with pytest.raises(RuntimeError, match='history store'):
        artifacts.reconcile_saved(task['id'])
    checked = validation.validate(repo.get('task', task['id']))
    assert not checked['ok']
    assert any(i['code'] == 'HISTORY_UNAVAILABLE' for i in checked['issues'])


def test_history_refreshes_after_entity_revision_and_checks_all_rows(host, monkeypatch):
    repo, task = history_case(host)
    calls = []
    read = repo.list_projection
    def projection(*args, **kwargs):
        calls.append(kwargs.get('limit'))
        return read(*args, **kwargs)
    monkeypatch.setattr(repo, 'list_projection', projection)
    artifacts.reconcile_saved(task['id'])
    repo.mutate('task', task['id'], lambda t: t.update(accounting_entity='Carrier', revision=2))
    artifacts.reconcile_saved(task['id'])
    current = repo.get('task', task['id'])
    assert current['history_lookup']['revision'] == 2
    assert current['existing_records'] == []
    assert all(limit is None for limit in calls)


def test_explicit_api_history_scope_and_old_snapshots_do_not_read_global_history(host, monkeypatch):
    repo, _, task = host
    monkeypatch.setattr(repo, 'list_projection', lambda *a, **kw: pytest.fail('provided scope must stay local'))
    artifacts.reconcile_saved(task['id'])
    assert repo.get('task', task['id'])['records'][0]['operation'] == 'CREATE'


@pytest.mark.parametrize(('body', 'expected'), [({}, 'automatic'),
    ({'existing_records': []}, 'provided'), ({'existing_bills': []}, 'provided'),
    ({'history_mode': 'automatic'}, 'automatic')])
def test_new_task_history_mode_uses_api_default_and_preserves_explicit_scope(host, monkeypatch, body, expected):
    repo, _, template = host
    repo.objects['asset', 'file-1'] = dict(id='file-1')
    async def thread(**kwargs):
        return dict(thread_id='offline-thread')
    async def start(value, **kwargs):
        return value
    def create(kind, value):
        value = dict(value, id='created', revision=1)
        repo.objects[kind, 'created'] = deepcopy(value)
        return value
    monkeypatch.setattr(repo, 'create', create, raising=False)
    monkeypatch.setattr(tasks, 'sdk', lambda: SimpleNamespace(threads=SimpleNamespace(create=thread)))
    monkeypatch.setattr(tasks, 'snapshot', lambda: template['capability'])
    monkeypatch.setattr(tasks, 'start_run', start)
    response = TestClient(app).post('/api/tasks', json=dict(asset_ids=['file-1'], **body))
    assert response.status_code == 201, response.text
    assert repo.get('task', 'created')['history_mode'] == expected


def test_invalid_history_modes_fail_before_any_external_action(host):
    client = TestClient(app)
    for body in (dict(history_mode='anything'), dict(existing_records='invalid'),
                 dict(history_mode='automatic', existing_records=[dict(amount=100)])):
        assert client.post('/api/tasks', json=body).status_code == 422


def test_bundle_extraction_shares_mail_context_with_later_attachment_batch(host):
    repo, _, task = host
    sources = [dict(source_id='mail', format='eml', status='ready', blocks=[dict(
        anchor='mail/body', kind='mail_body', text='Invoice BUNDLE-1: carrier charges customer USD 50.')])]
    sources.extend(dict(source_id=f'attachment-{i}', parent_source_id='mail', status='ready',
        format='text', blocks=[dict(anchor='body', text=f'BUNDLE-1 fee-{i} USD 10')]) for i in range(13))
    repo.mutate('task', task['id'], lambda current: current.update(sources=sources))
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    prepare = next(tool for tool in business if tool.name == 'prepare_document_extraction')
    first = prepare.invoke({})
    later = prepare.invoke({'offset': 12, 'limit': 1})
    assert first['mode'] in ('read', 'search')
    assert len(first['materials']) == 14
    assert {m['source_id'] for m in first['materials']} >= {'mail', 'attachment-11'}
    # Bundle reading ignores legacy pagination: every batch sees the same files.
    assert first['content'] == later['content']
    assert any(w['source_id'] == 'mail' and 'BUNDLE-1' in w['text'] for w in first['content'])
    assert any(w['source_id'] == 'attachment-11' for w in first['content'])
    assert repo.get('task', task['id'])['revision'] == task['revision']

    targeted = prepare.invoke({'source_id': 'attachment-11'})
    assert {m['source_id'] for m in targeted['materials']} == {
        m['source_id'] for m in first['materials']}


def test_markdown_native_search_then_exact_evidence_without_fulltext_in_context(host, monkeypatch, tmp_path):
    repo, _, task = host
    intake = skill_versions.skill_module('document-intake')
    body = '\n'.join(f'Unrelated paragraph {i}' for i in range(3000)) + '\nINVOICE TARGET-9 EUR 50\n'
    source = dict(source_id='long-doc', name='synthetic.txt', format='text', status='ready',
        blocks=[dict(anchor='body', text=body, authoritative=True)])
    intake.write_markdown(source, tmp_path)
    line = next(s['line'] for s in source['markdown']['spans'] if 'TARGET-9' in s['quote'])
    repo.mutate('task', task['id'], lambda current: current.update(sources=[source]))
    seen = []
    def respond(request):
        seen.append(request)
        if len(seen) == 1:
            return proposed_call('prepare_document_extraction', {}, 'manifest')
        if len(seen) == 2:
            return proposed_call('grep', dict(pattern='TARGET-9', path='/materials/', output_mode='content'), 'find')
        if len(seen) == 3:
            return proposed_call('read_markdown_evidence', dict(source_id='long-doc', start_line=line, limit=1), 'quote')
        return dict(role='assistant', content='Found TARGET-9, EUR 50.')
    async def exercise():
        _, business = skill_bindings.tools_for(task['id'], task['capability'])
        selected = [t for t in business if t.name in ('prepare_document_extraction', 'read_markdown_evidence')]
        assert all('runtime' not in t.tool_call_schema.model_json_schema().get('properties', {}) for t in selected)
        model, client = offline_model(monkeypatch, task['id'], respond)
        graph = create_agent(model, tools=selected, middleware=[FilesystemMiddleware(
            backend=StateBackend(), tools=['grep', 'read_file', 'ls'])])
        try:
            result = await graph.ainvoke({'messages': [{'role':'user','content':'Find the invoice'}]})
            assert '/materials/long-doc.md' in result['files']
            content = '\n'.join(str(m.content) for m in result['messages'])
            assert 'TARGET-9' in content and 'Unrelated paragraph 0' not in content
            assert len(content) < len(body) // 4
            assert len(seen) == 4
        finally:
            await client.aclose()
    asyncio.run(exercise())
    receipt = repo.get('task', task['id'])['material_reads'][0]
    assert receipt['start_line'] == receipt['end_line'] == line
    assert receipt['eof'] and not receipt['truncated']


def test_extraction_messages_do_not_repeat_schema_or_full_evidence_results(host):
    repo, _, task = host
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    tools = {t.name: t for t in business}
    prepared = tools['prepare_document_extraction'].invoke({})
    assert 'schema' not in prepared  # already supplied by the native save tool
    linked = tools['link_task_evidence'].invoke({})
    assert linked['valid'] is True and 'issues' in linked
    assert 'charges' not in linked and 'documents' not in linked
    assert repo.get('task', task['id'])['evidence']['charges']
    assert tools['prepare_export'].return_direct is False


def test_pdf_supplement_returns_only_new_blocks_and_keeps_all_saved_blocks(host):
    repo, _, task = host
    pdf = dict(source_id='pdf', format='pdf', status='ready', content_id='sha256:test',
        blocks=[dict(anchor='page:1/native', kind='native_preview', text='B/L HBL-1',
                     page=1, authoritative=False),
                dict(anchor='ocr/pages:1/document:1', kind='ocr_structured', text='{}')],
        metadata=dict(page_count=1, ocr_ranges=[dict(pages=[1], status='ready')]))
    repo.mutate('task', task['id'], lambda t: t['sources'].append(pdf))
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    read = next(t for t in business if t.name == 'read_document_sources')
    result = read.invoke(dict(source_ids=['pdf'], method='text', reason='OCR缺编号'))
    assert result['reads'][0]['added_anchors'] == ['page:1/embedded']
    assert 'material_bundle' not in result
    saved = repo.get('task', task['id'])
    pdf_source = next(s for s in saved['sources'] if s['source_id'] == 'pdf')
    anchors = [b['anchor'] for b in pdf_source['blocks']]
    assert anchors.count('page:1/embedded') == 1
    assert 'page:1/native' in anchors and 'ocr/pages:1/document:1' in anchors
    again = read.invoke(dict(source_ids=['pdf'], method='text', reason='再次读取'))
    assert again['reads'][0]['added_anchors'] == []


def test_save_can_run_deterministic_checks_without_a_separate_model_turn(host):
    repo, _, task = host
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    save = next(t for t in business if t.name == 'save_document_extraction')
    result = save.invoke(dict(result=task['extraction'], finalize=True))
    saved = repo.get('task', task['id'])
    assert result['saved'] is True and result['validation']['ok'] is True
    assert saved['records'] and saved['evidence']['valid'] is True
    assert saved['usage']['model_calls'] == 0


def test_pdf_supplement_is_task_bound_and_refreshes_complete_bundle(host):
    repo, _, task = host
    pdf = dict(source_id='pdf', format='pdf', status='ready', content_id='sha256:test',
        blocks=[dict(anchor='page:1/native', kind='native_preview', text='B/L HBL-1',
                     page=1, authoritative=False)],
        metadata=dict(page_count=1, ocr_ranges=[dict(pages=[1], status='ready')]))
    def add_pdf(t):
        t['sources'].append(pdf)
        t['intake'] = [dict(asset_id='asset', sources=deepcopy(t['sources']))]
    repo.mutate('task', task['id'], add_pdf)
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    read = next(t for t in business if t.name == 'read_document_sources')
    denied = read.invoke(dict(name='read_document_sources', id='outside', type='tool_call',
        args=dict(source_ids=['other-task'], method='text', reason='字段核对')))
    assert denied.status == 'error' and '不属于' in denied.content
    wrong_format = read.invoke(dict(name='read_document_sources', id='wrong-format', type='tool_call',
        args=dict(source_ids=['doc'], method='text', reason='字段核对')))
    assert wrong_format.status == 'error' and '仅支持PDF' in wrong_format.content
    assert repo.get('task', task['id'])['sources'] == task['sources'] + [pdf]
    result = read.invoke(dict(source_ids=['pdf'], method='text', reason='OCR缺编号'))
    saved = repo.get('task', task['id'])
    assert len(saved['sources']) == 2 and saved['revision'] == task['revision']
    assert {s['source_id'] for s in saved['sources']} == {'doc', 'pdf'}
    assert saved['evidence'] is None and saved['validation'] is None
    assert result['reads'][0]['added_anchors'] == ['page:1/embedded']
    reading = result.get('reading') or {}
    assert {m['source_id'] for m in reading.get('materials', [])} >= {'doc', 'pdf'}
    assert saved['intake'][0]['sources'] == saved['sources']
    repeated = read.invoke(dict(source_ids=['pdf'], method='text', reason='确认已读取'))
    assert repeated['reads'][0]['added_anchors'] == []


def test_ocr_supplement_updates_markdown_evidence_without_multimodal_tool(host, monkeypatch, tmp_path):
    from hashlib import sha256
    from PIL import Image
    repo, _, task = host
    path = tmp_path / 'image.png'
    Image.new('RGB', (20, 20), 'white').save(path)
    image = dict(source_id='img', format='image', path=str(path), status='ready',
        content_id='sha256:' + sha256(path.read_bytes()).hexdigest(), metadata={}, blocks=[])
    def setup(t):
        t['sources'].append(image)
        t['source_urls'] = {'img:frame:1': 'https://files.test/image.png'}
        t['intake'] = [dict(sources=deepcopy(t['sources']), artifacts=[], issues=[])]
    repo.mutate('task', task['id'], setup)
    monkeypatch.setattr(skill_bindings, 'asset_file', lambda record: path)
    monkeypatch.setattr(skill_bindings, 'ASSETS', tmp_path / 'assets')
    monkeypatch.setenv('OCR_RESPONSE_FORMAT', 'text')
    monkeypatch.setenv('OBS_ENABLE', 'false')
    sent = []
    def ocr(endpoint, *, json, timeout):
        sent.append(json)
        return httpx.Response(200, json='Amount EUR 50', request=httpx.Request('POST', endpoint))
    monkeypatch.setattr(httpx, 'post', ocr)
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    assert 'view_source_image' not in {t.name for t in business}
    read = next(t for t in business if t.name == 'read_document_sources')
    args = dict(source_ids=['img'], method='ocr', frame=1, reason='字段缺口')
    result = read.invoke(dict(name=read.name, id='ocr-call', type='tool_call', args=args))
    assert isinstance(result, ToolMessage) and result.status == 'success'
    assert all(b['type'] == 'text' for b in result.content_blocks)
    assert 'Amount EUR 50' in result.content  # text reading returns the OCR text, not an image
    saved = repo.get('task', task['id'])
    image = saved['sources'][-1]
    assert 'Amount EUR 50' in image['markdown']['text']
    assert image['blocks'][0]['frame'] == 1 and image['blocks'][0]['raw_response']
    assert saved['intake'][0]['sources'] == saved['sources']
    assert {a['kind'] for a in saved['intake'][0]['artifacts']} >= {'ocr_raw', 'markdown', 'markdown_map'}
    assert saved['evidence'] is None and saved['validation'] is None
    assert saved['revision'] == task['revision'] and len(sent) == 1
    read.invoke(args)
    assert len(sent) == 1  # successful recheck reused
    denied = read.invoke(dict(name=read.name, id='bad', type='tool_call',
        args=dict(args, source_ids=['other-task'])))
    assert denied.status == 'error'


def test_resume_without_saved_checkpoint_never_creates_a_new_run(host, monkeypatch):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda current: current.update(
        thread_id='old-thread', usage=dict(model_calls=1), status='paused', control='paused'))

    async def missing_checkpoint(*args, **kwargs):
        return {'checkpoint': None, 'values': {}}

    monkeypatch.setattr(tasks, 'sdk', lambda: SimpleNamespace(
        threads=SimpleNamespace(get_state=missing_checkpoint)))
    result = TestClient(app).post('/api/tasks/task-1/control', json={'action': 'resume'})
    assert result.status_code == 409
    assert '检查点不可用' in result.json()['message']
    assert repo.get('task', task['id'])['control'] == 'paused'


@pytest.mark.parametrize('denial', ['pause', 'skill', 'mcp', 'revision', 'budget', 'agent'])
def test_dispatch_denial_prevents_actual_handler(host, denial):
    """Changes after planning stop dispatch and do not consume an allowed call."""
    repo, live, task = host
    name, provenance = 'save_document_extraction', {}
    if denial == 'pause':
        repo.mutate('task', task['id'], lambda t: t.update(control='paused'))
    elif denial == 'skill':
        next(s for s in live['skills']['skills'] if s['name'] == 'document-extraction')['enabled'] = False
    elif denial == 'mcp':
        name, provenance = 'remote_tool', {'remote_tool': 'remote'}
        live['mcp']['servers'] = [dict(id='remote', enabled=False)]
    elif denial == 'revision':
        repo.mutate('task', task['id'], lambda t: t.update(revision=2))
    elif denial == 'budget':
        repo.mutate('task', task['id'], lambda t: t['capability']['config']['runtime'].update(tool_calls=0))
    elif denial == 'agent':
        name = 'task'
        live['agents']['agents'] = []
    called = []

    async def handler(request):
        called.append(request)
        return ToolMessage(content='executed', tool_call_id='call-1')

    guard = dispatch_middleware.DispatchPolicy(task['id'], 1, provenance=provenance)
    result = asyncio.run(guard.awrap_tool_call(request_for(name, subagent_type='document-expert'), handler))
    assert result.status == 'error'
    assert not called
    assert repo.get('task', task['id'])['usage']['tool_calls'] == 0
    assert repo.receipts[-1]['event'] == 'dispatch_denied'


def test_successful_dispatch_records_receipt_and_shared_tool_usage(host):
    repo, _, task = host

    async def handler(request):
        return ToolMessage(content='executed', tool_call_id=request.tool_call['id'])

    guard = dispatch_middleware.DispatchPolicy(task['id'], 1)
    result = asyncio.run(guard.awrap_tool_call(request_for('read_task_context'), handler))
    saved = repo.get('task', task['id'])
    assert result.content == 'executed'
    assert saved['usage']['tool_calls'] == 1
    assert saved['usage']['active_depth'] == 0
    assert repo.receipts[-1]['event'] == 'tool_receipt'


def test_native_retry_rechecks_pause_before_retrying_the_actual_handler(host):
    """The official retry middleware re-enters the innermost dispatch guard."""
    repo, _, task = host
    executions = []
    guard = dispatch_middleware.DispatchPolicy(task['id'], 1)
    retry = ToolRetryMiddleware(max_retries=2, retry_on=(ConnectionError,), initial_delay=0, jitter=False)

    async def flaky_handler(request):
        executions.append(request.tool_call['id'])
        repo.mutate('task', task['id'], lambda t: t.update(control='paused'))
        raise ConnectionError('transient failure during the first dispatch')

    async def guarded_handler(request):
        return await guard.awrap_tool_call(request, flaky_handler)

    result = asyncio.run(retry.awrap_tool_call(request_for('read_task_context'), guarded_handler))
    assert result.status == 'error'
    assert executions == ['call-1']
    assert repo.get('task', task['id'])['usage']['tool_calls'] == 1
    assert repo.receipts[-1]['event'] == 'dispatch_denied'


def test_real_model_http_requests_disable_thinking_and_share_task_budget(host, monkeypatch):
    """Separate parent/subagent models debit one task at the actual HTTP boundary."""
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t['capability']['config']['runtime'].update(model_calls=2))
    sent = []

    def transport(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=dict(id='chat-test', object='chat.completion', created=1,
            model='offline-test', choices=[dict(index=0, message=dict(role='assistant', content='ok'),
                                               finish_reason='stop')],
            usage=dict(prompt_tokens=1, completion_tokens=1, total_tokens=2)))

    native_client = httpx.AsyncClient

    class OfflineClient(native_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(transport))

    monkeypatch.setattr(models.httpx, 'AsyncClient', OfflineClient)
    monkeypatch.setenv('LLM_API_KEY', 'offline-test-key')
    monkeypatch.setenv('LLM_BASE_URL', 'https://offline.invalid/v1')
    monkeypatch.setenv('LLM_MODEL_NAME', 'offline-test')

    async def exercise():
        parent, parent_http = models.make_model(task['id'])
        child, child_http = models.make_model(task['id'])
        try:
            assert (await parent.ainvoke('parent request')).content == 'ok'
            assert (await child.ainvoke('subagent request')).content == 'ok'
            with pytest.raises(Exception) as failure:
                await child.ainvoke('budget exhausted')
            causes, current = [], failure.value
            while current is not None:
                causes.append(current)
                current = current.__cause__
            assert any(isinstance(cause, dispatch.PolicyDenied) for cause in causes)
        finally:
            await parent_http.aclose()
            await child_http.aclose()

    asyncio.run(exercise())
    assert len(sent) == 2
    assert all(body['enable_thinking'] is False for body in sent)
    assert repo.get('task', task['id'])['usage']['model_calls'] == 2


def test_request_with_thinking_enabled_never_reaches_transport(host, monkeypatch):
    repo, _, task = host
    sent = []
    native_client = httpx.AsyncClient
    class OfflineClient(native_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(lambda request: sent.append(request)))

    monkeypatch.setattr(models.httpx, 'AsyncClient', OfflineClient)

    async def exercise():
        _, client = models.make_model(task['id'])
        try:
            with pytest.raises(dispatch.PolicyDenied, match='思考'):
                await client.post('https://offline.invalid/v1/chat/completions', json={'enable_thinking': True})
        finally:
            await client.aclose()

    asyncio.run(exercise())
    assert not sent
    assert repo.get('task', task['id'])['usage']['model_calls'] == 0


def approve(client, task_id, revision=1):
    return client.post(f'/api/tasks/{task_id}/approve', json=dict(
        decision='approve', reason='人工回读原件确认', expected_revision=revision))


def test_formal_export_requires_approval_for_the_current_arguments(host):
    repo, _, task = host
    client = TestClient(app)
    denied = client.get(f'/api/tasks/{task["id"]}/export')
    assert denied.status_code == 422
    assert 'APPROVAL_REQUIRED' in {i['code'] for i in denied.json()['validation']['issues']}
    assert approve(client, task['id']).status_code == 200
    accepted = client.get(f'/api/tasks/{task["id"]}/export', params={'revision': 1})
    assert accepted.status_code == 200
    assert accepted.json()[0]['charge_details']['amount'] == 100
    assert repo.get('task', task['id'])['last_export']['revision'] == 1

    def change_args(current):
        current['records'][0]['charge_details']['amount'] = Decimal('125')

    repo.mutate('task', task['id'], change_args)
    changed = client.get(f'/api/tasks/{task["id"]}/export')
    assert changed.status_code == 422
    assert 'STALE_APPROVAL' in {i['code'] for i in changed.json()['validation']['issues']}


@pytest.mark.parametrize('name', sorted(registry.REQUIRED))
def test_formal_export_cannot_bypass_a_disabled_required_hook(host, name):
    repo, live, task = host
    client = TestClient(app)
    assert approve(client, task['id']).status_code == 200
    next(h for h in live['hooks']['hooks'] if h['name'] == name)['enabled'] = False
    denied = client.get(f'/api/tasks/{task["id"]}/export')
    assert denied.status_code in (409, 422)
    assert 'last_export' not in repo.get('task', task['id'])
    assert not any(e['event'] == 'export' for e in repo.receipts)


def test_old_edit_is_rejected_and_human_revision_invalidates_approval(host):
    repo, _, task = host
    client = TestClient(app)
    assert approve(client, task['id']).status_code == 200
    assert client.get(f'/api/tasks/{task["id"]}/export').status_code == 200
    source_before = repo.get('task', task['id'])['sources']
    edit = dict(expected_revision=1, reason='回读原件，金额为125', operations=[
        dict(op='set', charge_id='c1', field='charge_details.amount', value='125')])
    changed = client.patch(f'/api/tasks/{task["id"]}/revision', json=edit)
    assert changed.status_code == 200, changed.text
    current = repo.get('task', task['id'])
    assert current['revision'] == 2
    assert current['records'][0]['charge_details']['amount'] == Decimal('125')
    assert current['records'][0]['human_confirmed']['charge_details.amount']['revision'] == 2
    assert current['approval'] is None and current['auto_review'] is None
    assert current['export']['revision'] == 2  # Rebuilt draft is not approval.
    assert current['sources'] == source_before
    assert client.get(f'/api/tasks/{task["id"]}/export').status_code == 422
    assert client.get(f'/api/tasks/{task["id"]}/export', params={'revision': 1}).status_code == 409
    stale = client.patch(f'/api/tasks/{task["id"]}/revision', json={
        **edit, 'operations': [dict(op='set', charge_id='c1', field='amount', value='999')]})
    assert stale.status_code == 409
    assert repo.get('task', task['id'])['records'][0]['charge_details']['amount'] == Decimal('125')


def test_confidence_is_read_only_current_and_bound_to_task_skill_version(host):
    repo, live, task = host
    client = TestClient(app)
    before = repo.get('task', task['id'])
    result = client.get(f'/api/tasks/{task["id"]}/confidence')
    assert result.status_code == 200, result.text
    assert result.json()['revision'] == 1
    assert result.json()['calibrated'] is False
    assert result.json()['capability_version'] == task['capability']['version']
    assert repo.get('task', task['id']) == before
    assert repo.receipts == []
    score_skill = next(s for s in live['skills']['skills'] if s['name'] == 'billing-confidence')
    score_skill['enabled'] = False
    assert client.get(f'/api/tasks/{task["id"]}/confidence').json()['score'] is None
    score_skill['enabled'] = True
    cap = deepcopy(task['capability'])
    cap['config']['skills']['skills'] = [s for s in cap['config']['skills']['skills']
                                        if s['name'] != 'billing-confidence']
    repo.mutate('task', task['id'], lambda t: t.update(capability=cap))
    historical = client.get(f'/api/tasks/{task["id"]}/confidence').json()
    assert historical['score'] is None and historical['band'] == 'unavailable'
    assert historical['records'] == []


def test_preview_resolves_saved_anchor_and_does_not_change_task(host):
    repo, live, task = host
    client = TestClient(app)
    before = repo.get('task', task['id'])
    result = client.get(f'/api/tasks/{task["id"]}/sources/doc/preview',
                        params={'anchor': 'p1', 'quote': 'THC USD 100', 'field': 'amount', 'value': '100'})
    assert result.status_code == 200, result.text
    assert result.json()['target']['located'] is True
    assert 'bbox' not in result.json()['target']
    assert result.json()['content_url'].endswith('/sources/doc/content')
    assert repo.get('task', task['id']) == before
    missing = client.get(f'/api/tasks/{task["id"]}/sources/doc/preview', params={'anchor': 'unknown'})
    assert missing.status_code == 200 and not missing.json()['target']['located']
    assert client.get(f'/api/tasks/{task["id"]}/sources/not-owned/preview').status_code == 404
    next(s for s in live['skills']['skills'] if s['name'] == 'evidence-linking')['enabled'] = False
    assert client.get(f'/api/tasks/{task["id"]}/sources/doc/preview').status_code == 409


def test_disabled_human_review_blocks_edits_before_mutation(host):
    repo, live, task = host
    before = repo.get('task', task['id'])
    next(s for s in live['skills']['skills'] if s['name'] == 'human-review')['enabled'] = False
    result = TestClient(app).patch(f'/api/tasks/{task["id"]}/revision', json=dict(
        expected_revision=1, reason='验收热停用', operations=[
            dict(op='set', charge_id='c1', field='charge_details.amount', value='125')]))
    assert result.status_code == 409
    assert repo.get('task', task['id']) == before


def test_hallucinated_total_cannot_pass_approval_even_when_extracted_sum_matches(host):
    repo, _, task = host
    def corrupt_total(t):
        t['sources'][0]['blocks'].append(dict(anchor='total', text='TOTAL USD 150'))
        t['totals'] = [dict(source_id='doc', amount=Decimal('100'), currency='USD',
            evidence=[dict(source_id='doc', anchor='total', quote='TOTAL USD 150')])]
    repo.mutate('task', task['id'], corrupt_total)
    current = repo.get('task', task['id'])
    checked = validation.validate(current)
    assert not checked['ok']
    assert 'TOTAL_VALUE_UNSUPPORTED' in {i['code'] for i in checked['issues']}
    client = TestClient(app)
    score = client.get(f'/api/tasks/{task["id"]}/confidence').json()
    assert not score['eligible_for_quick_confirm']
    assert approve(client, task['id']).status_code == 422
    assert client.get(f'/api/tasks/{task["id"]}/export').status_code == 422


@pytest.mark.parametrize("case", ["missing_fields", "number_format", "location", "wrong_name", "ambiguous_currency"])
def test_source_semantics_are_real_approval_and_export_gates(host, case):
    repo, _, task = host
    def replace_material(current):
        charge = current["charges"][0]
        text = "THC USD 100 QTY 2"
        if case == "missing_fields":
            refs = [dict(source_id="doc", anchor="p1", quote="QTY 2", field="quantity")]
        elif case == "number_format":
            text, charge["amount"] = "THC USD 1,234", Decimal("1234")
            refs = [dict(source_id="doc", anchor="p1", quote=text)]
        elif case == "location":
            text = "THC USD 100 | THC USD 100"
            refs = [dict(source_id="doc", anchor="p1", quote=text)]
        elif case == "wrong_name":
            charge["charge_item"] = "Storage Fee"
            refs = [dict(source_id="doc", anchor="p1", quote=text)]
        else:
            text = "THC $100"
            refs = [dict(source_id="doc", anchor="p1", quote=text)]
        current["sources"][0]["blocks"][0]["text"] = text
        charge["evidence"] = refs
    repo.mutate("task", task["id"], replace_material)
    artifacts.reconcile_saved(task["id"])
    client = TestClient(app)
    current = repo.get("task", task["id"])
    assert not current["validation"]["ok"]
    assert {i["code"] for i in current["validation"]["issues"]} & {"FIELD_VALUE_UNSUPPORTED", "FIELD_VALUE_AMBIGUOUS"}
    assert client.get(f'/api/tasks/{task["id"]}/confidence').json()["records"][0]["review_route"] == "blocked"
    assert approve(client, task["id"]).status_code == 422
    assert client.get(f'/api/tasks/{task["id"]}/export').status_code == 422
    assert repo.get("task", task["id"])["approval"] is None


def test_required_hook_false_without_issues_still_blocks_approval(host, monkeypatch):
    _, _, task = host
    original = validation.function
    def resolver(cap, name, entry):
        if name == 'evidence-linking' and entry == 'validate_evidence':
            return lambda payload: {'valid': False, 'issues': []}
        return original(cap, name, entry)
    monkeypatch.setattr(validation, 'function', resolver)
    checked = validation.validate(task)
    assert not checked['ok']
    assert any(i['code'] == 'HOOK_REJECTED' and i['hook'] == 'evidence' for i in checked['issues'])
    assert approve(TestClient(app), task['id']).status_code == 422


def test_concurrent_extraction_batches_merge_inside_transaction(host, monkeypatch):
    """Two proposals read the same revision and both remain in the final artifact."""
    repo, _, task = host
    chunk_ids = ['alpha', 'beta']

    def reset(current):
        current.update(extraction=None, charges=[], records=[], coverage=[], candidate_digests=[],
                       chunks=[dict(chunk_id=cid, source_id='doc', anchor='p1') for cid in chunk_ids])

    repo.mutate('task', task['id'], reset)
    common, business = skill_bindings.tools_for(task['id'], task['capability'])
    save = next(t for t in business if t.name == 'save_document_extraction')
    barrier = Barrier(2)
    original_check = skill_bindings.check

    def synchronized_check(task_id, **kwargs):
        result = original_check(task_id, **kwargs)
        if kwargs.get('skill') == 'document-extraction':
            barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(skill_bindings, 'check', synchronized_check)

    def submit(cid):
        return save.invoke({'result': dict(charges=[dict(
            charge_id=cid, source_id='doc', line_id=cid, charge_item='THC', amount='100', currency='USD',
            evidence=[dict(source_id='doc', anchor='p1', quote='THC USD 100')])],
            coverage=[dict(source_id='doc', anchor='p1', chunk_id=cid, status='extracted',
                           reason='该批次提取完成', charge_ids=[cid])])})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, chunk_ids))
    assert all(result['saved'] for result in results)
    saved = repo.get('task', task['id'])
    assert {c['charge_id'] for c in saved['charges']} == set(chunk_ids)
    assert {c['chunk_id'] for c in saved['coverage']} == set(chunk_ids)
    assert saved['extraction']['valid']
    assert saved['extraction']['issues'] == []
    assert saved['revision'] == 1
    assert saved['approval'] is None and saved['validation'] is None


def test_no_progress_candidate_is_blocked_without_overwriting_saved_artifact(host):
    repo, _, task = host
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    save = next(t for t in business if t.name == 'save_document_extraction')
    proposal = {'result': deepcopy(task['extraction'])}
    assert save.invoke(proposal)['saved']
    saved = repo.get('task', task['id'])
    with pytest.raises(dispatch.PolicyDenied, match='没有进展'):
        save.invoke(proposal)
    assert repo.get('task', task['id']) == saved


def test_repeated_candidates_without_coverage_are_bounded_and_reset_on_revision(host):
    repo, _, task = host
    # Each changed amount has actual supporting text. Evidence-regressing
    # candidates now stop before they can overwrite a supported saved amount.
    repo.mutate('task', task['id'], lambda t: t['sources'][0]['blocks'].extend(
        dict(anchor=f'p{value}', text=f'THC USD {value}') for value in (101, 102, 103)))
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    save = next(t for t in business if t.name == 'save_document_extraction')
    proposal = dict(result=dict(charges=[dict(charge_id='c1', source_id='doc', amount='101',
        evidence=[dict(source_id='doc', anchor='p101', quote='THC USD 101')])]))
    assert save.invoke(proposal)['saved']
    with pytest.raises(dispatch.PolicyDenied, match='没有进展'):
        save.invoke(proposal)
    proposal['result']['charges'][0]['amount'] = '102'
    proposal['result']['charges'][0]['evidence'][0].update(anchor='p102', quote='THC USD 102')
    assert save.invoke(proposal)['saved']
    proposal['result']['charges'][0]['amount'] = '103'
    proposal['result']['charges'][0]['evidence'][0].update(anchor='p103', quote='THC USD 103')
    with pytest.raises(dispatch.PolicyDenied, match='两轮'):
        save.invoke(proposal)
    repo.mutate('task', task['id'], lambda current: current.update(revision=2))
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    save = next(t for t in business if t.name == 'save_document_extraction')
    assert save.invoke(proposal)['saved']


def offline_model(monkeypatch, task_id, responder):
    """Script HTTP responses while keeping native model binding and graph execution."""
    native_client = httpx.AsyncClient

    def transport(request):
        body = json.loads(request.content)
        assert body['enable_thinking'] is False
        message = responder(body)
        return httpx.Response(200, json=dict(id='native-graph-test', object='chat.completion', created=1,
            model='offline-test', choices=[dict(index=0, message=message,
                finish_reason='tool_calls' if message.get('tool_calls') else 'stop')],
            usage=dict(prompt_tokens=1, completion_tokens=1, total_tokens=2)))

    class OfflineClient(native_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(transport))

    monkeypatch.setattr(models.httpx, 'AsyncClient', OfflineClient)
    monkeypatch.setenv('LLM_API_KEY', 'offline-test-key')
    monkeypatch.setenv('LLM_BASE_URL', 'https://offline.invalid/v1')
    monkeypatch.setenv('LLM_MODEL_NAME', 'offline-test')
    return models.make_model(task_id)


def proposed_call(name, args, call_id):
    return dict(role='assistant', content='', tool_calls=[dict(id=call_id, type='function',
        function=dict(name=name, arguments=json.dumps(args, default=str)))])


def test_native_graph_normalizes_empty_call_ids_and_keeps_model_receipts(host, monkeypatch):
    from backend.middleware.recovery import ToolCallIdNormalization
    from langchain.messages import AIMessage
    repo, _, task = host
    seen = []
    @tool
    def probe() -> str:
        """Return a stable offline probe result."""
        return 'done'
    def respond(body):
        seen.append(body)
        return proposed_call('probe', {}, '') if len(seen) == 1 else dict(role='assistant', content='done')
    async def exercise():
        model, client = offline_model(monkeypatch, task['id'], respond)
        graph = create_agent(model, tools=[probe], middleware=[
            dispatch_middleware.DispatchPolicy(task['id'], 1), ToolCallIdNormalization()])
        try:
            return await graph.ainvoke({'messages':[{'role':'user','content':'probe'}]})
        finally:
            await client.aclose()
    state = asyncio.run(exercise())
    ai = next(m for m in state['messages'] if isinstance(m, AIMessage) and m.tool_calls)
    result = next(m for m in state['messages'] if isinstance(m, ToolMessage))
    assert ai.tool_calls[0]['id'] and ai.tool_calls[0]['id'] == result.tool_call_id
    assert result.status == 'success' and len(seen) == 2
    receipts = [e for e in repo.receipts if e['event'] == 'model_round_receipt']
    assert len(receipts) == 2 and all(e['status'] == 'success' and e['input_tokens'] == 1 for e in receipts)


def test_ocr_progress_uses_native_custom_stream(host, monkeypatch, tmp_path):
    from hashlib import sha256
    from PIL import Image
    repo, _, task = host
    path = tmp_path/'progress.png'
    Image.new('RGB', (11, 11), 'white').save(path)
    source = dict(source_id='progress', format='image', path=str(path), status='ready',
        content_id='sha256:'+sha256(path.read_bytes()).hexdigest(), metadata={}, blocks=[])
    repo.mutate('task', task['id'], lambda current: current.update(sources=[source],
        source_urls={'progress:frame:1':'https://offline.test/image.png'}, intake=[]))
    monkeypatch.setattr(skill_bindings, 'asset_file', lambda record: path)
    monkeypatch.setattr(skill_bindings, 'ASSETS', tmp_path/'assets')
    monkeypatch.setenv('OCR_RESPONSE_FORMAT', 'text')
    monkeypatch.setenv('OBS_ENABLE', 'false')
    monkeypatch.setattr(httpx, 'post', lambda endpoint, **kwargs: httpx.Response(200,
        json='Handling EUR 10', request=httpx.Request('POST',endpoint)))
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    read = next(t for t in business if t.name == 'read_document_sources')
    calls = []
    def respond(body):
        calls.append(body)
        return proposed_call(read.name, dict(source_ids=['progress'], method='ocr', frame=1,
            reason='核对模糊费用'), 'progress-call') if len(calls)==1 else dict(role='assistant',content='done')
    async def exercise():
        model, client = offline_model(monkeypatch, task['id'], respond)
        graph = create_agent(model, tools=[read])
        try:
            return [event async for event in graph.astream({'messages':[{'role':'user','content':'核对费用'}]}, stream_mode='custom')]
        finally:
            await client.aclose()
    events = asyncio.run(exercise())
    stages = [e['stage'] for e in events if e.get('type')=='intake_progress']
    assert stages == ['uploading','requesting','ocr_complete']
    assert events[-1]['receipt']['http_status']==200


def test_auto_review_completion_exports_without_an_artificial_human_approval(host):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: (t['charges'][0].update(reference_no=None),
        t['records'][0]['document_info'].update(reference_no=None)) and None)
    saved = review_runtime.settle_saved(task['id'])
    assert saved['status'] == 'completed'
    assert saved['auto_review']['mode'] == 'automatic'
    assert saved['approval'] is None
    assert saved['validation']['confidence']['review_required'] is False
    result = TestClient(app).get(f'/api/tasks/{task["id"]}/export')
    assert result.status_code == 200, result.text
    # Same-revision changes must also invalidate the exact financial binding.
    repo.mutate('task', task['id'], lambda t: t['records'][0]['charge_details'].update(amount=200))
    assert TestClient(app).get(f'/api/tasks/{task["id"]}/export').status_code == 422


def test_complete_review_accepts_gaps_without_formal_approval(host):
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(status='completed_with_gaps'))
    result = TestClient(app).post('/api/tasks/task-1/complete-review',
                                  json={'expected_revision': 1})
    assert result.status_code == 200, result.text
    saved = repo.get('task', 'task-1')
    assert saved['status'] == 'completed'
    assert saved['review_confirmation']['revision'] == 1
    assert saved['approval'] is None


def test_complete_review_closes_any_settled_review_state_once(host):
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(status='awaiting_review'))
    result = TestClient(app).post('/api/tasks/task-1/complete-review',
                                  json={'expected_revision': 1})
    assert result.status_code == 200, result.text
    saved = repo.get('task', 'task-1')
    assert saved['status'] == 'completed'
    assert saved['review_confirmation'] == dict(
        decision='completed_with_gaps', revision=1,
        at=saved['review_confirmation']['at'],
        reason='调用方确认完成审核；未提供的字段保持null')
    # A repeated acknowledgement is idempotent and does not bump the revision.
    again = TestClient(app).post('/api/tasks/task-1/complete-review',
                                 json={'expected_revision': 1})
    assert again.status_code == 200, again.text
    assert repo.get('task', 'task-1')['revision'] == 1


def test_complete_review_rejects_processing_or_pending_question(host):
    repo, _, task = host
    repo.mutate('task', 'task-1', lambda t: t.update(status='processing'))
    assert TestClient(app).post('/api/tasks/task-1/complete-review',
                                json={'expected_revision': 1}).status_code == 409
    repo.mutate('task', 'task-1', lambda t: t.update(
        status='awaiting_review',
        review_request=dict(id='q1', state='pending', revision=1, question='请补充')))
    assert TestClient(app).post('/api/tasks/task-1/complete-review',
                                json={'expected_revision': 1}).status_code == 409
    saved = repo.get('task', 'task-1')
    assert saved['status'] == 'awaiting_review' and saved.get('review_confirmation') is None


def test_stack_caps_model_calls_per_run_below_the_task_budget(host):
    from langchain.agents.middleware import ContextEditingMiddleware, ModelCallLimitMiddleware
    from backend.middleware.assembly import base_stack
    repo, _, task = host
    cap = task['capability']
    limits = cap['config']['runtime']
    _, business = skill_bindings.tools_for('task-1', cap)
    stack = base_stack('task-1', 1, cap, StateBackend(), business, outcome=True)
    guards = [item for item in stack if isinstance(item, ModelCallLimitMiddleware)]
    run_guard = next(item for item in guards if item.run_limit)
    assert run_guard.run_limit == limits.get('run_model_calls', 16)
    assert run_guard.exit_behavior == 'end'
    assert any(item.thread_limit == limits['model_calls'] for item in guards)
    editing = next(item for item in stack if isinstance(item, ContextEditingMiddleware))
    edit = editing.edits[0]
    assert edit.trigger == limits.get('context_edit_trigger', 8000)
    assert edit.keep == limits.get('context_edit_keep', 3)
    assert set(edit.exclude_tools) == {'save_document_extraction', 'prepare_export', 'ask_user'}
    # A historical capability without the new key still gets a bounded run.
    legacy = {**cap, 'config': {**cap['config'], 'runtime': {
        key: value for key, value in limits.items() if key != 'run_model_calls'}}}
    stack = base_stack('task-1', 1, legacy, StateBackend(), business, outcome=True)
    fallback = next(item.run_limit for item in stack
                    if isinstance(item, ModelCallLimitMiddleware) and item.run_limit)
    assert fallback == limits['model_calls'] - limits['turn_model_calls']


def test_subject_can_be_submitted_after_budget_exhaustion_without_new_model_calls(host):
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t.update(status='budget_exhausted',
        usage={**t['usage'], 'model_calls': t['capability']['config']['runtime']['model_calls']}))
    response = TestClient(app).patch(f'/api/tasks/{task["id"]}/revision', json=dict(
        expected_revision=1, accounting_entity='Carrier', operations=[], reason='调用方补充本次主体'))
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['revision'] == 2 and saved['accounting_entity'] == 'Carrier'
    assert saved['records'][0]['financial_attributes']['posting_type'] == 'AR'
    assert saved['usage']['model_calls'] == task['capability']['config']['runtime']['model_calls']


def test_native_confidence_interrupt_correct_edit_then_resume_without_reextracting(host, monkeypatch):
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
    repo, _, task = host
    # This specifically verifies the historical score-gated policy. Current
    # Codex-style tasks publish gaps without a mandatory confidence interrupt.
    repo.mutate('task', task['id'], lambda t: t['capability']['config']['runtime'].update(agent_style='legacy'))
    repo.mutate('task', task['id'], lambda t: (t['charges'][0].update(reference_no=None),
        t['records'][0]['document_info'].update(reference_no=None)) and None)
    repo.mutate('task', task['id'], lambda t: t['charges'][0].update(amount=Decimal('125')))
    artifacts.reconcile_saved(task['id'])
    seen = []
    def respond(body):
        seen.append(body)
        return proposed_call('prepare_export', {}, 'finish-bill') if len(seen) == 1 else dict(role='assistant', content='核验结束')
    async def exercise():
        _, business = skill_bindings.tools_for(task['id'], task['capability'])
        finish = next(t for t in business if t.name == 'prepare_export')
        model, client = offline_model(monkeypatch, task['id'], respond)
        config = {'configurable': {'thread_id': 'synthetic-confidence-review'}}
        graph = create_agent(model, tools=[finish], checkpointer=InMemorySaver())
        try:
            paused = await graph.ainvoke({'messages': [{'role':'user','content':'完成核验'}]}, config)
            value = paused['__interrupt__'][0].value
            assert value['kind'] == 'confidence_review'
            assert {item['field'] for item in value['items']} == {'amount'}
            assert repo.get('task', task['id'])['auto_review'] is None
            stale = await graph.ainvoke(Command(resume={'decision':'confirm','expected_revision':0}), config)
            assert stale['__interrupt__'][0].value['revision'] == 1
            assert repo.get('task', task['id'])['auto_review'] is None
            changed = TestClient(app).patch(f'/api/tasks/{task["id"]}/revision', json=dict(
                expected_revision=1, operations=[dict(op='set',charge_id='c1',field='amount',value=100)], reason='对照原文更正为100'))
            assert changed.status_code == 200, changed.text
            result = await graph.ainvoke(Command(resume={'decision':'confirm','expected_revision':2}), config)
            assert not result.get('__interrupt__')
        finally:
            await client.aclose()
    asyncio.run(exercise())
    saved = repo.get('task', task['id'])
    assert saved['status'] == 'completed'
    assert saved['confidence_interrupt'] is None
    assert saved['records'][0]['charge_details']['amount'] == Decimal('100')
    assert saved['sources'] == task['sources']
    assert sum(e['event'] == 'confidence_review' for e in repo.receipts) == 1


def test_running_edit_has_its_own_error_code_and_is_retryable(host, monkeypatch):
    from backend.api import task_runtime
    repo, _, task = host
    repo.mutate('task', task['id'], lambda t: t.update(run_id='run', thread_id='thread'))
    class Runs:
        async def get(self, *args):
            return {'status':'running'}
    monkeypatch.setattr(task_runtime, 'sdk', lambda: SimpleNamespace(runs=Runs()))
    response = TestClient(app).patch(f'/api/tasks/{task["id"]}/revision', json=dict(
        expected_revision=1, accounting_entity='Carrier', operations=[], reason='补主体'))
    assert response.status_code == 409 and response.json()['error'] == 'AGENT_RUNNING'
    assert repo.get('task', task['id'])['revision'] == 1


def test_native_after_agent_finalizes_even_if_model_omits_export_tool(host, monkeypatch):
    repo, _, task = host
    def start(t):
        t['status'] = 'running'
        t['charges'][0]['reference_no'] = None
        t['records'][0]['document_info']['reference_no'] = None
    repo.mutate('task', task['id'], start)
    async def exercise():
        model, client = offline_model(monkeypatch, task['id'], lambda body: dict(role='assistant',content='完成提取'))
        try:
            graph = create_agent(model, tools=[], middleware=[outcome.TaskOutcome(task['id'])])
            await graph.ainvoke({'messages':[{'role':'user','content':'完成核验'}]})
        finally:
            await client.aclose()
    asyncio.run(exercise())
    assert repo.get('task', task['id'])['status'] == 'completed'
    assert repo.get('task', task['id'])['auto_review']['mode'] == 'automatic'


def test_native_mcp_stdio_discovery_dispatch_and_hot_disable(host, monkeypatch, tmp_path):
    """An actual stdio tool executes once; disabling its server blocks the next call."""
    repo, live, task = host
    live['mcp']['servers'] = [dict(id='probe', enabled=True)]
    receipt_path = tmp_path / 'mcp-receipts.jsonl'
    server_path = Path(__file__).parent / 'fixtures' / 'mcp_probe_server.py'
    seen = []

    def respond(body):
        seen.append(body)
        names = {t['function']['name'] for t in body.get('tools', [])}
        if len(seen) == 1:
            assert 'calculate' in names
            return proposed_call('calculate', {'a': 19, 'b': 23}, 'mcp-first')
        if len(seen) == 2:
            assert 'calculate' in names
            live['mcp']['servers'][0]['enabled'] = False
            return proposed_call('calculate', {'a': 1, 'b': 2}, 'mcp-disabled')
        assert 'calculate' not in names
        return dict(role='assistant', content='已保留第一次回执，禁用后未执行第二次调用')

    async def exercise():
        adapter = MCPAdapter({'mcpServers': {'probe': dict(command=sys.executable,
            args=['-B', str(server_path), str(receipt_path)])}})
        model, client = offline_model(monkeypatch, task['id'], respond)
        try:
            async with asyncio.timeout(30):
                async with adapter:
                    discovered = await adapter.list_tools(cache_mode='refresh')
                assert [t.name for t in discovered] == ['calculate']
                graph = create_agent(model, tools=[], middleware=[
                    mcp_tools.MCPTools(discovered, {'calculate': 'probe'}),
                    dispatch_middleware.DispatchPolicy(task['id'], 1, provenance={'calculate': 'probe'})])
                return await graph.ainvoke({'messages': [{'role': 'user', 'content': '核对MCP派发'}]})
        finally:
            await adapter.client.close()
            await client.aclose()

    result = asyncio.run(exercise())
    messages = [m for m in result['messages'] if isinstance(m, ToolMessage)]
    assert len(messages) == 2
    assert messages[0].status == 'success' and '42' in str(messages[0].content)
    assert messages[1].status == 'error' and '禁用' in messages[1].content
    external_receipts = [json.loads(line) for line in receipt_path.read_text().splitlines()]
    assert external_receipts == [{'a': 19, 'b': 23, 'result': 42}]
    assert repo.get('task', task['id'])['usage']['tool_calls'] == 1
    assert [e['event'] for e in repo.receipts].count('tool_receipt') == 1


def test_native_skill_read_discloses_and_executes_portable_package_function(host, monkeypatch):
    """Reading the real SKILL.md exposes its tool, executed by native ToolNode."""
    repo, _, task = host
    cap = task['capability']
    package_function = skill_versions.function(cap, 'billing-reconciliation', 'reconcile_charges')
    portable_tool = tool('reconcile_task_charges')(package_function)
    seen = []

    def respond(body):
        seen.append(body)
        names = {t['function']['name'] for t in body.get('tools', [])}
        if len(seen) == 1:
            assert 'read_file' in names and 'reconcile_task_charges' not in names
            return proposed_call('read_file', {'file_path': '/skills/billing-reconciliation/SKILL.md'}, 'skill-read')
        if len(seen) == 2:
            assert 'reconcile_task_charges' in names
            return proposed_call('reconcile_task_charges', {'payload': dict(charges=task['charges'],
                existing_records=[], accounting_entity='Client', revision=1)}, 'skill-execute')
        return dict(role='assistant', content='Skill费用校验已执行')

    async def exercise():
        model, client = offline_model(monkeypatch, task['id'], respond)
        backend = StateBackend()
        graph = create_agent(model, tools=[], middleware=[dispatch_middleware.DispatchPolicy(task['id'], 1),
            FilesystemMiddleware(backend=backend, tools=['read_file']),
            SkillsMiddleware(backend=backend, sources=['/skills/'], tools=[portable_tool])])
        try:
            return await graph.ainvoke({'messages': [{'role': 'user', 'content': '加载并执行财务Skill'}],
                'files': skill_versions.skill_files(cap, names=['billing-reconciliation'])})
        finally:
            await client.aclose()

    result = asyncio.run(exercise())
    execution = next(m for m in result['messages'] if isinstance(m, ToolMessage)
                     and m.name == 'reconcile_task_charges')
    # Native ToolNode uses repr for a mapping containing Decimal; retain it as
    # a tool message instead of adding a production serialization wrapper.
    assert execution.status == 'success'
    assert "'valid': True" in execution.content
    assert "'operation': 'CREATE'" in execution.content
    assert "'posting_type': 'AP'" in execution.content
    assert "'amount': Decimal('100')" in execution.content
    assert len(seen) == 3
    assert repo.get('task', task['id'])['usage']['tool_calls'] == 2


def test_intake_supplemented_ocr_url_is_saved_then_used_by_original_skill(host, monkeypatch, tmp_path):
    """The caller can repair a missing download URL without replacing the parser."""
    from hashlib import sha256
    from PIL import Image

    repo, _, task = host
    asset_root = tmp_path / 'assets'
    image_path = asset_root / 'asset-1' / 'invoice.png'
    image_path.parent.mkdir(parents=True)
    Image.new('RGB', (30, 20), 'white').save(image_path)
    monkeypatch.setattr(skill_bindings, 'ASSETS', asset_root)
    repo.objects['asset', 'asset-1'] = dict(id='asset-1', name='invoice.png',
        relative_path='asset-1/invoice.png', sha256=sha256(image_path.read_bytes()).hexdigest())
    repo.mutate('task', task['id'], lambda t: t.update(asset_ids=['asset-1'],
        source_urls={'unrelated.pdf': 'https://files.example/unrelated.pdf'}))
    cache = SimpleNamespace(get=lambda key: None, setex=lambda *args: None)
    monkeypatch.setattr(skill_bindings.redis.Redis, 'from_url', lambda *args, **kwargs: cache)
    sent = []
    expected_url = 'https://files.example/invoice.png'

    def simulated_ocr(endpoint, *, json, timeout):
        current = repo.get('task', task['id'])
        assert current['source_urls']['invoice.png'] == expected_url
        assert current['ocr_text_pointer'] == '/data/text'
        sent.append(dict(endpoint=endpoint, payload=json))
        return httpx.Response(200, json={'data': {'text': 'THC USD 100'}},
                              request=httpx.Request('POST', endpoint))

    monkeypatch.setattr(httpx, 'post', simulated_ocr)
    _, business = skill_bindings.tools_for(task['id'], task['capability'])
    intake = next(t for t in business if t.name == 'intake_documents')
    result = asyncio.run(intake.ainvoke(dict(source_urls={'invoice.png': expected_url},
                                           ocr_text_pointer='/data/text')))
    saved = repo.get('task', task['id'])
    # Blank pixels have no supplemental text; that diagnostic must not turn
    # successful mandatory remote OCR or URL repair into an intake failure.
    assert all(not i.get('blocking', True) for i in result['issues']) and len(sent) == 1
    assert sent[0]['payload'] == dict(file=expected_url, task='orderChange', callBack='', taskType='')
    assert saved['source_urls']['unrelated.pdf'] == 'https://files.example/unrelated.pdf'
    assert saved['source_urls']['invoice.png'] == expected_url
    assert saved['sources'][0]['status'] == 'ready'
    assert saved['sources'][0]['blocks'][0]['text'] == 'THC USD 100'
    assert Path(saved['sources'][0]['blocks'][0]['raw_response']).is_file()

