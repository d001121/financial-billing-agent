"""Small offline checks for reviewed, scoped billing experience retrieval."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.extensions.skill_versions import function
from backend.api.routes import experiences
from backend.api.responses import response
from backend.infrastructure.repository import Conflict
from backend.tests.test_improvement import MemoryRepository


def experience(**changes):
    value = dict(id='exp-1', revision=2, status='active', accounting_entity='Demo Carrier',
        title='裸符号币种核对', problem='只有$不能确认币种',
        applicability='单据只出现货币符号', recommendation='核对原件，无明确币种则留空',
        exceptions='原件明确印有ISO币种', keywords=['币种', 'USD'],
        source=dict(task_id='t1', revision=3), source_refs=[])
    return {**value, **changes}


def test_retrieval_filters_scope_status_and_irrelevant_results():
    retrieve = function(None, 'feedback-improvement', 'retrieve_experiences')
    active = experience()
    records = [active, experience(id='draft', status='draft'),
               experience(id='other', accounting_entity='Other')]
    original = deepcopy(records)
    result = retrieve(records, accounting_entity=' demo carrier ', query='币种 USD')
    assert [r['id'] for r in result] == ['exp-1']
    assert records == original
    assert retrieve(records, accounting_entity=None, query='币种') == []
    assert retrieve(records, accounting_entity='Other', query='unrelated_xyz') == []


def test_draft_validation_preserves_missing_scope_and_rejects_unknown_fields():
    validate = function(None, 'feedback-improvement', 'validate_experience')
    value = experience(accounting_entity=None)
    assert validate(value, activate=False)['valid']
    assert not validate(value, activate=True)['valid']
    assert not validate({**value, 'recommendation': ''}, activate=False)['valid']


def test_summary_context_uses_real_history_and_bounded_source_refs():
    context = function(None, 'feedback-improvement', 'summary_context')
    task = dict(id='t1', revision=3, accounting_entity='Demo Carrier',
        history=[dict(history=[dict(field='currency', before='USD', after=None, reason='裸$')])],
        charges=[dict(charge_id='c1', evidence=[dict(source_id='s1', quote='H/C $50')])],
        sources=[dict(source_id='s1', name='Original', blocks=[dict(text='原文 $50')])])
    result = context(task, '币种不能猜')
    assert result['corrections'][0]['after'] is None
    assert result['source_refs'][0]['source_id'] == 's1'
    assert result['accounting_entity'] == 'Demo Carrier'
    assert '币种不能猜' in result['note']


@pytest.fixture
def library(monkeypatch):
    class Repo(MemoryRepository):
        def list(self, kind, limit=100):
            return super().list(kind)[:limit]
    repo, calls = Repo(), []
    repo.create('task', dict(id='t1', revision=3, accounting_entity='Demo Carrier',
        capability={'version': None}, charges=[], records=[], sources=[],
        history=[dict(history=[dict(field='currency', before='USD', after=None, reason='只有$')])]))
    monkeypatch.setattr(experiences, 'repository', lambda: repo)
    class FakeModel:
        def with_structured_output(self, schema, **options):
            self.schema = schema
            assert options == dict(method='function_calling', include_raw=True)
            return self
        async def ainvoke(self, messages):
            self.guard()
            calls.append(messages)
            content = {key: experience()[key] for key in self.schema.model_fields}
            return dict(parsed=self.schema(**content), parsing_error=None,
                raw=SimpleNamespace(usage_metadata=dict(input_tokens=100, output_tokens=40, total_tokens=140)))
    class Client:
        async def aclose(self):
            pass
    def factory(**kwargs):
        model = FakeModel()
        model.guard = kwargs['request_guard']
        return model, Client()
    monkeypatch.setattr(experiences, 'make_model', factory)
    app = FastAPI()
    app.include_router(experiences.router)
    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return response(dict(message=str(exc)), 409 if isinstance(exc, Conflict) else 422)
    with TestClient(app) as client:
        yield client, repo, calls


def summarize(client, **changes):
    return client.post('/api/improvements/experiences/summarize', json=dict(
        task_id='t1', expected_revision=3, **changes))


def test_summary_reuse_review_pause_and_edit_do_not_change_source(library):
    client, repo, calls = library
    before = repo.get('task', 't1')
    first = summarize(client)
    assert first.status_code == 201, first.text
    card = first.json()['experience']
    assert card['status'] == 'draft' and card['source']['revision'] == 3
    assert summarize(client).json()['reused'] is True and len(calls) == 1
    job = repo.list('experience_summary')[0]
    assert job['usage']['model_calls'] == 1 and job['usage']['total_tokens'] == 140
    url = '/api/improvements/experiences/' + card['id']
    assert client.post(url + '/review', json=dict(action='activate', expected_revision=1)).status_code == 422
    active = client.post(url + '/review', json=dict(action='activate', approved=True, expected_revision=1)).json()['experience']
    assert active['status'] == 'active'
    assert client.patch(url, json=dict(expected_revision=2, title='change')).status_code == 409
    paused = client.post(url + '/review', json=dict(action='pause', expected_revision=2)).json()['experience']
    edited = client.patch(url, json=dict(expected_revision=paused['revision'], title='重新核对币种')).json()['experience']
    assert edited['status'] == 'draft' and edited['review'] is None
    assert repo.get('task', 't1') == before
    assert client.patch(url, json=dict(expected_revision=edited['revision'], accounting_entity='Other')).status_code == 422


def test_missing_entity_cannot_activate_and_stale_summary_has_no_model_call(library):
    client, repo, calls = library
    repo.mutate('task', 't1', lambda t: t.update(accounting_entity=None))
    assert client.post('/api/improvements/experiences/summarize', json=dict(
        task_id='t1', expected_revision=2)).status_code == 409
    assert not calls
    card = summarize(client).json()['experience']
    result = client.post('/api/improvements/experiences/' + card['id'] + '/review',
        json=dict(action='activate', approved=True, expected_revision=1))
    assert result.status_code == 422 and '主体' in result.text


def test_failed_summary_requires_explicit_retry_and_never_creates_fake_card(library, monkeypatch):
    client, repo, calls = library
    def broken(**kwargs):
        kwargs['request_guard']()
        calls.append('failed request')
        raise RuntimeError('provider secret details')
    monkeypatch.setattr(experiences, 'make_model', broken)
    assert summarize(client).status_code == 422
    assert summarize(client).status_code == 422 and len(calls) == 1
    assert summarize(client, retry_failed=True).status_code == 422 and len(calls) == 2
    assert repo.list('experience') == []
    assert repo.list('experience_summary')[0]['usage']['model_calls'] == 2


def test_native_tool_uses_snapshot_scope_live_pause_and_records_only_real_returns(library, monkeypatch):
    from backend.tools import skill_bindings
    from backend.config.transactions import read_config
    client, repo, _ = library
    cap = dict(version=None, experiences=[experience()], config=dict(skills=read_config('skills'), runtime=read_config('runtime')))
    repo.create('experience', experience())
    repo.mutate('task', 't1', lambda t: t.update(capability=cap))
    monkeypatch.setattr(skill_bindings, 'repository', lambda: repo)
    monkeypatch.setattr(skill_bindings, 'check', lambda *args, **kwargs: repo.get('task', 't1'))
    common, _ = skill_bindings.tools_for('t1', cap)
    tool = next(t for t in common if t.name == 'search_reviewed_experiences')
    runtime = deepcopy(cap['config']['runtime'])
    monkeypatch.setattr(skill_bindings, 'read_config', lambda kind: runtime)
    runtime['use_reviewed_experiences'] = False
    assert tool.invoke(dict(query='币种'))['enabled'] is False
    assert repo.list('experience_use') == []
    hidden, _ = skill_bindings.tools_for('t1', cap)
    assert 'search_reviewed_experiences' not in [t.name for t in hidden]
    runtime['use_reviewed_experiences'] = True
    assert len(tool.invoke(dict(query='币种'))['experiences']) == 1
    assert len(repo.list('experience_use')) == 1
    tool.invoke(dict(query='币种'))
    assert len(repo.list('experience_use')) == 1
    repo.mutate('experience', 'exp-1', lambda t: t.update(status='paused'))
    assert tool.invoke(dict(query='币种'))['experiences'] == []
    repo.mutate('experience', 'exp-1', lambda t: t.update(status='active', revision=3))
    assert tool.invoke(dict(query='币种'))['experiences'] == []


def test_new_snapshots_freeze_reviewed_experience_revisions(library, monkeypatch, tmp_path):
    from backend.extensions import snapshots
    _, repo, _ = library
    monkeypatch.setattr(snapshots, 'repository', lambda: repo)
    monkeypatch.setattr(snapshots, 'RELEASES', tmp_path)
    repo.create('experience', experience())
    before = snapshots.snapshot()
    assert before['experiences'][0]['revision'] == 2
    repo.mutate('experience', 'exp-1', lambda t: t.update(status='paused', revision=3))
    after = snapshots.snapshot()
    assert after['experiences'] == [] and before['version'] != after['version']
    assert before['experiences'][0]['status'] == 'active'


def test_disabled_usage_snapshot_excludes_experiences_and_keeps_mapping_registry(library, monkeypatch, tmp_path):
    from backend.extensions import snapshots
    from backend.tools import skill_bindings
    _, repo, _ = library
    original_read = snapshots.read_config
    def read(kind):
        value = original_read(kind)
        if kind == 'runtime':
            value['use_reviewed_experiences'] = False
        return value
    monkeypatch.setattr(snapshots, 'read_config', read)
    monkeypatch.setattr(snapshots, 'repository', lambda: repo)
    monkeypatch.setattr(snapshots, 'RELEASES', tmp_path)
    repo.create('experience', experience())
    repo.create('improvement_registry', dict(id='default', active_version='mapping-v1', versions=[]))
    cap = snapshots.snapshot()
    assert cap['experiences'] == []
    assert cap['improvements']['active_version'] == 'mapping-v1'
    tools, _ = skill_bindings.tools_for('t1', dict(cap, version=None, experiences=[experience()]))
    assert 'search_reviewed_experiences' not in [t.name for t in tools]


def test_task_context_reports_usage_disabled_even_with_pinned_cards(library, monkeypatch):
    from backend.tools import context
    _, repo, _ = library
    repo.mutate('task', 't1', lambda task: task.update(asset_ids=[], capability=dict(
        version=None, experiences=[experience()], config=dict(runtime=dict(agent_style='legacy')))))
    monkeypatch.setattr(context, 'repository', lambda: repo)
    runtime = dict(use_reviewed_experiences=True)
    monkeypatch.setattr(context, 'read_config', lambda kind: runtime)
    tool = context.context_tool('t1')
    assert tool.invoke({})['experience_reference_count'] == 1
    runtime['use_reviewed_experiences'] = False
    result = tool.invoke({})
    assert result['experience_reference_count'] == 0
    assert result['experience_references_enabled'] is False


def test_native_structured_output_uses_one_counted_mock_http_request(library, monkeypatch):
    import httpx
    from backend.infrastructure import models
    from backend.infrastructure.repository import dumps
    client, repo, _ = library
    for key, value in dict(LLM_MODEL_NAME='offline-test', LLM_API_KEY='offline-only',
                           LLM_BASE_URL='https://offline.invalid/v1').items():
        monkeypatch.setenv(key, value)
    sent = []
    def transport(request):
        body = __import__('json').loads(request.content)
        assert body['enable_thinking'] is False
        assert body['tools'][0]['function']['name'] == 'ExperienceDraft'
        sent.append(body)
        content = {key: experience()[key] for key in experiences.skill_module('feedback-improvement').ExperienceDraft.model_fields}
        return httpx.Response(200, json=dict(id='mock-response', model='offline-test',
            choices=[dict(index=0, finish_reason='tool_calls', message=dict(role='assistant', content=None,
                tool_calls=[dict(id='draft-call', type='function', function=dict(name='ExperienceDraft', arguments=dumps(content)))]))],
            usage=dict(prompt_tokens=120, completion_tokens=60, total_tokens=180)))
    original_client = httpx.AsyncClient
    class OfflineClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(transport))
    monkeypatch.setattr(models.httpx, 'AsyncClient', OfflineClient)
    monkeypatch.setattr(experiences, 'make_model', models.make_model)
    result = summarize(client)
    assert result.status_code == 201, result.text
    assert len(sent) == 1
    assert repo.list('experience_summary')[0]['usage']['model_calls'] == 1
    assert repo.list('experience_summary')[0]['usage']['total_tokens'] == 180
