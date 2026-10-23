"""Workspace removal uses isolated records; never deletes real bills or threads."""
from copy import deepcopy
from types import SimpleNamespace

from fastapi.testclient import TestClient
import httpx
import pytest

from backend.api import app
from backend.api import task_runtime
from backend.api.routes import tasks, observability
from backend.harness import dispatch
from backend.tests.test_host import FakeRepository


@pytest.fixture
def workspace(monkeypatch):
    store = FakeRepository()
    original = dict(id='synthetic-delete', revision=3, status='completed', control='running',
                    asset_ids=['original.pdf'], records=[{'amount': 50}],
                    charges=[{'amount': 50}], approval={'revision': 3})
    store.objects['task', original['id']] = deepcopy(original)
    for module in (tasks, observability, dispatch):
        monkeypatch.setattr(module, 'repository', lambda: store)
    return store, original, TestClient(app)


def delete(client, revision=3):
    return client.delete('/api/tasks/synthetic-delete', params={'expected_revision': revision})


def test_remove_retains_revision_originals_results_and_approval_and_is_idempotent(workspace):
    store, original, client = workspace
    assert delete(client).json() == {'id': original['id'], 'deleted': True}
    saved = store.get('task', original['id'])
    assert saved.pop('deleted_at')
    assert saved == original
    assert delete(client, revision=1).status_code == 200


@pytest.mark.parametrize('revision', [1, 2, 4])
def test_stale_selection_cannot_remove_changed_bill(workspace, revision):
    store, original, client = workspace
    assert delete(client, revision).status_code == 409
    assert store.get('task', original['id']) == original


@pytest.mark.parametrize('path,method', [('', 'get'), ('/artifacts', 'get'), ('/control', 'post')])
def test_deleted_bill_is_not_opened_or_resumed(workspace, path, method):
    _, _, client = workspace
    assert delete(client).status_code == 200
    kwargs = {'json': {'action': 'resume'}} if method == 'post' else {}
    assert getattr(client, method)('/api/tasks/synthetic-delete' + path, **kwargs).status_code == 404


def test_deleted_bill_blocks_native_dispatch_and_run_creation(workspace):
    import asyncio
    store, original, client = workspace
    assert delete(client).status_code == 200
    with pytest.raises(dispatch.PolicyDenied, match='删除'):
        dispatch.check(original['id'], allow_paused=True)
    from backend.infrastructure.repository import Conflict
    with pytest.raises(Conflict, match='删除'):
        asyncio.run(task_runtime.start_run(store.get('task', original['id'])))


@pytest.mark.parametrize('thread_status,run_status', [('busy', 'success'), ('idle', 'pending'), ('idle', 'running')])
def test_native_active_run_or_thread_prevents_removal(workspace, monkeypatch, thread_status, run_status):
    store, original, client = workspace
    original.update(thread_id='thread', run_id='run')
    store.objects['task', original['id']] = deepcopy(original)
    async def get_thread(*args):
        return {'status': thread_status}
    async def get_run(*args):
        return {'status': run_status}
    sdk = lambda: SimpleNamespace(threads=SimpleNamespace(get=get_thread), runs=SimpleNamespace(get=get_run))
    monkeypatch.setattr(tasks, 'sdk', sdk)
    monkeypatch.setattr(task_runtime, 'sdk', sdk)
    assert delete(client).status_code == 409
    assert store.get('task', original['id']) == original


def test_historical_missing_native_run_can_be_removed_but_outage_is_not_ignored(workspace, monkeypatch):
    store, original, client = workspace
    original.update(thread_id='thread', run_id='run')
    store.objects['task', original['id']] = deepcopy(original)
    code = 503
    async def missing(*args):
        raise httpx.HTTPStatusError('native server', request=httpx.Request('GET', 'http://offline.invalid'),
                                    response=httpx.Response(code))
    sdk = lambda: SimpleNamespace(threads=SimpleNamespace(get=missing), runs=SimpleNamespace(get=missing))
    monkeypatch.setattr(tasks, 'sdk', sdk)
    monkeypatch.setattr(task_runtime, 'sdk', sdk)
    with pytest.raises(httpx.HTTPStatusError):
        delete(client)
    assert store.get('task', original['id']) == original
    code = 404
    assert delete(client).status_code == 200


def test_queued_without_native_run_requires_pause(workspace):
    store, original, client = workspace
    original['status'] = 'queued'
    store.objects['task', original['id']] = deepcopy(original)
    assert delete(client).status_code == 409
    store.objects['task', original['id']]['control'] = 'paused'
    assert delete(client).status_code == 200


def test_concurrent_resume_during_delete_is_rejected(workspace, monkeypatch):
    store, original, client = workspace
    mutate = store.mutate
    def resumed(*args, **kwargs):
        store.objects['task', original['id']]['run_id'] = 'new-run'
        return mutate(*args, **kwargs)
    monkeypatch.setattr(store, 'mutate', resumed)
    assert delete(client).status_code == 409
    assert not store.get('task', original['id']).get('deleted_at')


def test_user_lists_filter_deleted_and_administrator_traces_keep_history(workspace, monkeypatch):
    store, original, client = workspace
    assert delete(client).status_code == 200
    def project(kind, fields, **kwargs):
        return [] if kwargs.get('exclude_deleted') else [store.get('task', original['id'])]
    monkeypatch.setattr(store, 'list_projection', project, raising=False)
    monkeypatch.setattr(store, 'event_counts', lambda ids: {}, raising=False)
    assert client.get('/api/tasks').json() == []
    assert client.get('/api/bills').json() == []
    assert client.get('/api/traces').json()['tasks'][0]['id'] == original['id']
