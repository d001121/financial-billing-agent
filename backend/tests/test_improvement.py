"""Offline HTTP integration: native LangSmith experiments run real financial Skills."""
from copy import deepcopy
from threading import RLock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.api.routes import improvements
from backend.api.responses import response
from backend.extensions.skill_versions import function
from backend.infrastructure.repository import Conflict


class MemoryRepository:
    """Replace persistence only; retain copy-on-write atomic mutation semantics."""

    def __init__(self):
        self.objects = {}
        self.lock = RLock()

    def get(self, kind, object_id, required=True):
        with self.lock:
            value = self.objects.get((kind, object_id))
            if value is None and required:
                raise KeyError(object_id)
            return deepcopy(value)

    def list(self, kind):
        with self.lock:
            return [deepcopy(value) for (k, _), value in self.objects.items() if k == kind]

    def create(self, kind, value):
        with self.lock:
            value = deepcopy(value)
            value.setdefault('revision', 1)
            value.setdefault('created_at', '2026-10-21T00:00:00+00:00')
            self.objects[kind, value['id']] = value
            return deepcopy(value)

    def mutate(self, kind, object_id, transform, expected_revision=None):
        with self.lock:
            current = self.get(kind, object_id)
            if expected_revision is not None and current['revision'] != expected_revision:
                raise Conflict('stale revision')
            replacement = transform(current)
            current = current if replacement is None else replacement
            self.objects[kind, object_id] = deepcopy(current)
            return deepcopy(current)


@pytest.fixture
def host(monkeypatch):
    repo = MemoryRepository()
    repo.create('task', dict(id='t1', revision=3, accounting_entity='Demo Carrier',
        capability={'version': None}, records=[], charges=[], asset_ids=['source-1']))
    monkeypatch.setattr(improvements, 'repository', lambda: repo)
    monkeypatch.setattr(improvements, 'snapshot', lambda: {'version': None})
    app = FastAPI()
    app.include_router(improvements.router)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return response({'error': 'REVISION_CONFLICT', 'message': str(exc)}, 409)

    with TestClient(app) as client:
        yield client, repo


def proposal(client, **changes):
    return client.post('/api/improvements/candidates', json=dict(task_id='t1', expected_revision=3,
        opt_in=True, kind='charge_mapping', scope={'accounting_entity': 'Demo Carrier'},
        proposed_by='human reviewer', before={}, after={'Document Charge': 'Documentation Fee'}, **changes))


def changed_proposal(client, **changes):
    payload = dict(task_id='t1', expected_revision=3, opt_in=True, kind='charge_mapping',
        scope={'accounting_entity': 'Demo Carrier'}, proposed_by='human reviewer', before={},
        after={'Document Charge': 'Documentation Fee'})
    payload.update(changes)
    return client.post('/api/improvements/candidates', json=payload)


def publish(client, candidate_id, **changes):
    body = dict(reviewer='release reviewer', reason='checked native comparison', approved=True,
                expected_active_version='builtin-v1')
    body.update(changes)
    return client.post(f'/api/improvements/candidates/{candidate_id}/publish', json=body)


def test_candidate_requires_opt_in_current_source_and_supported_scope(host):
    client, repo = host
    assert changed_proposal(client, opt_in=False).status_code == 422
    assert changed_proposal(client, expected_revision=2).status_code == 409
    assert changed_proposal(client, scope={'issuer': 'Demo Carrier'}).status_code == 422
    created = proposal(client)
    assert created.status_code == 201
    candidate = created.json()['candidate']
    assert candidate['status'] == 'candidate'
    assert candidate['source']['revision'] == 3 and candidate['source']['artifact_digest']
    assert client.get('/api/improvements/candidates').json()['registry']['active_version'] == 'builtin-v1'
    assert repo.get('task', 't1')['revision'] == 3


def test_native_experiment_review_publication_resolution_and_rollback(host):
    client, repo = host
    original_task = repo.get('task', 't1')
    candidate = proposal(client).json()['candidate']
    candidate_id = candidate['id']
    assert publish(client, candidate_id).status_code == 422
    injected = client.post(f'/api/improvements/candidates/{candidate_id}/evaluate', json={'passed': True})
    assert injected.status_code == 422
    assert injected.json()['issues'][0]['code'] == 'MEASURED_EVALUATION_ONLY'
    evaluated = client.post(f'/api/improvements/candidates/{candidate_id}/evaluate', json={})
    assert evaluated.status_code == 200, evaluated.text
    comparison = evaluated.json()['comparison']
    assert comparison['engine'] == 'langsmith-local' and comparison['synthetic'] is True
    assert comparison['final_evaluated'] is True
    assert (comparison['baseline_passes'], comparison['candidate_passes'], comparison['total_cases']) == (5, 7, 7)
    assert all(c['candidate_run_id'] and c['baseline_run_id'] for c in comparison['measured_cases'])
    assert publish(client, candidate_id, approved=False).status_code == 422
    assert publish(client, candidate_id, expected_active_version='outdated').status_code == 409
    old_snapshot = repo.get('improvement_registry', 'default')
    published = publish(client, candidate_id)
    assert published.status_code == 200, published.text
    result = published.json()
    assert result['candidate']['status'] == 'published'
    registry = result['registry']
    resolver = function(None, 'feedback-improvement', 'resolve_mapping')
    assert resolver(registry, {'accounting_entity': 'demo carrier'}) == {'Document Charge': 'Documentation Fee'}
    assert resolver(registry, {'accounting_entity': 'Another Entity'}) == {}
    assert resolver(old_snapshot, {'accounting_entity': 'Demo Carrier'}) == {}
    assert repo.get('task', 't1') == original_task
    assert client.post(f'/api/improvements/candidates/{candidate_id}/evaluate', json={}).status_code == 409
    assert publish(client, candidate_id).status_code == 409
    rolled = client.post('/api/improvements/rollback', json=dict(target_version='builtin-v1',
        reviewer='release reviewer', reason='restore built-in', approved=True,
        expected_active_version=result['published_version']))
    assert rolled.status_code == 200
    assert resolver(rolled.json()['registry'], {'accounting_entity': 'Demo Carrier'}) == {}
    assert len(rolled.json()['registry']['versions']) == 2


def test_wrong_mapping_fails_measured_assertions_before_final_exposure(host):
    client, repo = host
    candidate = changed_proposal(client, after={'Document Charge': 'Storage Fee'}).json()['candidate']
    evaluated = client.post(f"/api/improvements/candidates/{candidate['id']}/evaluate", json={})
    assert evaluated.status_code == 422
    comparison = evaluated.json()['comparison']
    assert comparison['final_evaluated'] is False and comparison['candidate_passes'] < comparison['total_cases']
    assert any(i['code'] == 'CRITICAL_FAILURE' for i in comparison['issues'])
    assert repo.get('improvement_registry', 'default')['final_uses'] == {}
    assert publish(client, candidate['id']).status_code == 422


def test_unknown_alias_and_other_kinds_cannot_claim_measured_release(host):
    client, _ = host
    candidate = changed_proposal(client, after={'Unlabeled Fee': 'Documentation Fee'}).json()['candidate']
    result = client.post(f"/api/improvements/candidates/{candidate['id']}/evaluate", json={})
    assert result.status_code == 422
    assert 'EVALUATION_ALIAS_UNCOVERED' in {i['code'] for i in result.json()['comparison']['issues']}
    draft = changed_proposal(client, kind='prompt', after={'prompt': 'candidate wording'}).json()['candidate']
    result = client.post(f"/api/improvements/candidates/{draft['id']}/evaluate", json={})
    assert result.status_code == 422
    assert result.json()['comparison']['issues'][0]['code'] == 'KIND_DRAFT_ONLY'
    assert publish(client, draft['id']).status_code == 422


def test_exposed_final_data_cannot_select_a_different_candidate(host):
    client, repo = host
    first = proposal(client).json()['candidate']
    assert client.post(f"/api/improvements/candidates/{first['id']}/evaluate", json={}).status_code == 200
    second = changed_proposal(client, proposed_by='different reviewer').json()['candidate']
    result = client.post(f"/api/improvements/candidates/{second['id']}/evaluate", json={})
    assert result.status_code == 422
    assert 'FINAL_DATASET_REUSED' in {i['code'] for i in result.json()['comparison']['issues']}
    assert repo.get('improvement_registry', 'default')['active_version'] == 'builtin-v1'


def test_imported_dataset_selection_disable_and_immutable_labels(host):
    client, repo = host
    data = client.get('/api/improvements/datasets/builtin').json()
    imported = client.post('/api/improvements/datasets', json=dict(name='人工标注合成集',
        labeled_by='audit reviewer', dataset=data))
    assert imported.status_code == 201, imported.text
    saved = imported.json()
    identity = saved['id']
    assert client.get('/api/improvements/datasets/'+identity).json() == data
    candidate = proposal(client).json()['candidate']
    evaluated = client.post(f"/api/improvements/candidates/{candidate['id']}/evaluate",json={'dataset_id':identity})
    assert evaluated.status_code==200,evaluated.text
    comparison=evaluated.json()['comparison']
    assert comparison['dataset_id']==identity and comparison['candidate_passes']==7
    assert repo.get('improvement_registry','default')['final_cases']
    disabled=client.patch('/api/improvements/datasets/'+identity,json={'expected_revision':saved['revision'],'enabled':False})
    assert disabled.status_code==200 and disabled.json()['revision']==saved['revision']+1
    # This test app handles Conflict only; use a raised policy to prove no evaluation occurs.
    from backend.harness.dispatch import PolicyDenied
    with pytest.raises(PolicyDenied,match='禁用'):
        client.post(f"/api/improvements/candidates/{candidate['id']}/evaluate",json={'dataset_id':identity})
    assert client.patch('/api/improvements/datasets/'+identity,json={'expected_revision':saved['revision'],'enabled':True}).status_code==409
    assert client.patch('/api/improvements/datasets/'+identity,json={'expected_revision':disabled.json()['revision'],'enabled':True}).status_code==200


def test_dataset_relabel_does_not_restore_final_independence(host):
    client,_=host
    first=proposal(client).json()['candidate']
    assert client.post(f"/api/improvements/candidates/{first['id']}/evaluate",json={}).status_code==200
    data=client.get('/api/improvements/datasets/builtin').json()
    data['version']='renamed-final'
    result=client.post('/api/improvements/datasets',json=dict(name='renamed',labeled_by='reviewer',dataset=data))
    second=changed_proposal(client,proposed_by='new reviewer').json()['candidate']
    outcome=client.post(f"/api/improvements/candidates/{second['id']}/evaluate",json={'dataset_id':result.json()['id']})
    assert outcome.status_code==422
    assert 'FINAL_DATASET_REUSED' in {i['code'] for i in outcome.json()['comparison']['issues']}


def test_malformed_labels_split_leakage_and_disabled_skill_are_rejected(host, monkeypatch):
    client,_=host
    data=client.get('/api/improvements/datasets/builtin').json()
    first=deepcopy(data['cases'][0])
    first.update(case_id='copied',family_id='new-family',dataset_role='final')
    data['cases'].append(first)
    result=client.post('/api/improvements/datasets',json=dict(name='leaked',labeled_by='reviewer',dataset=data))
    assert result.status_code==422
    assert 'EVALUATION_LEAKAGE' in {i['code'] for i in result.json()['issues']}
    candidate=proposal(client).json()['candidate']
    monkeypatch.setattr(improvements,'enabled_skill',lambda name:False)
    from backend.harness.dispatch import PolicyDenied
    with pytest.raises(PolicyDenied,match='禁用'):
        proposal(client)
    with pytest.raises(PolicyDenied,match='禁用'):
        client.post(f"/api/improvements/candidates/{candidate['id']}/evaluate",json={})
    with pytest.raises(PolicyDenied,match='禁用'):
        publish(client,candidate['id'])
    assert client.get('/api/improvements/candidates').status_code==200


@pytest.mark.parametrize('mutation', [
    lambda data: data.update(label_policy=42),
    lambda data: data['cases'][0].update(case_id=[]),
    lambda data: data['cases'][0]['inputs']['charges'].append('invalid charge'),
    lambda data: data['cases'][0]['inputs']['sources'].append(None),
    lambda data: data['cases'][0]['reference_outputs']['records'].append(1),
])
def test_malformed_dataset_is_rejected_before_experiment(host, mutation):
    client, repo = host
    data = client.get('/api/improvements/datasets/builtin').json()
    mutation(data)
    result = client.post('/api/improvements/datasets', json=dict(
        name='malformed', labeled_by='reviewer', dataset=data))
    assert result.status_code == 422, result.text
    assert result.json()['valid'] is False
    assert repo.list('evaluation_dataset') == []


def test_disabled_feedback_skill_keeps_reviewed_rollback_available(host, monkeypatch):
    client, _ = host
    candidate = proposal(client).json()['candidate']
    assert client.post(f"/api/improvements/candidates/{candidate['id']}/evaluate", json={}).status_code == 200
    published = publish(client, candidate['id']).json()
    monkeypatch.setattr(improvements, 'enabled_skill', lambda name: False)
    # A disabled Skill is absent from new task snapshots; recovery must not use one.
    monkeypatch.setattr(improvements, 'snapshot', lambda: {'version': 'disabled-snapshot'})
    rolled = client.post('/api/improvements/rollback', json=dict(target_version='builtin-v1',
        reviewer='reviewer', reason='disable and restore rules', approved=True,
        expected_active_version=published['published_version']))
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()['registry']['active_version'] == 'builtin-v1'
