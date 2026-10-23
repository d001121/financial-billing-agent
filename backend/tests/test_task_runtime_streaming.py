"""Background runs must emit the same native protocol as the Vue subscriber."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langgraph._internal._constants import CONFIG_KEY_DURABILITY

from backend.api import task_runtime
from backend.tests.test_host import FakeRepository
from backend.extensions import skill_versions


@pytest.fixture
def empty_capability(monkeypatch, tmp_path):
    (tmp_path / 'streaming-fixture' / 'skills').mkdir(parents=True)
    monkeypatch.setattr(skill_versions, 'RELEASES', tmp_path)
    return {'version':'streaming-fixture', 'config':{'skills':{'skills':[]}}}


@pytest.mark.asyncio
@pytest.mark.parametrize('command', [None, {'resume': {'request': 'answer'}}])
async def test_background_and_resume_emit_native_activity(monkeypatch, command, empty_capability):
    task = dict(id='isolated-activity', thread_id='isolated-thread', revision=3, status='queued', control='running',
                capability=empty_capability)
    create = AsyncMock(return_value=({'run_id': 'isolated-run'} if command is None else
        {'type': 'success', 'id': 1, 'result': {'run_id': 'isolated-run'}}))
    repo = FakeRepository()
    repo.objects['task', task['id']] = task
    monkeypatch.setattr(task_runtime, 'sdk', lambda: SimpleNamespace(http=SimpleNamespace(post=create)))
    monkeypatch.setattr(task_runtime, 'repository', lambda: repo)

    await task_runtime.start_run(task, message='read all sources', command=command)

    args, kwargs = create.call_args
    envelope = kwargs['json']
    if command is not None:
        assert args == ('/threads/isolated-thread/commands',)
        assert envelope['method'] == 'run.start'
        params = envelope['params']
        assert params['multitaskStrategy'] == 'reject'
    else:
        assert args == ('/threads/isolated-thread/runs',)
        params = envelope
        assert params['config']['configurable']['__event_streaming_v2'] is True
        assert {'messages', 'checkpoints', 'updates', 'tasks'} <= set(params['stream_mode'])
        assert not {'tools', 'lifecycle'}.intersection(params['stream_mode'])
        assert params['durability'] == 'sync' and params['stream_resumable']
        assert params['multitask_strategy'] == 'reject'
        assert 'command' not in params
    assert params['assistant_id'] == 'workorder-agent'
    assert params['config']['configurable'][CONFIG_KEY_DURABILITY] == 'sync'
    assert params['metadata'] == {'task_id': task['id'], 'revision': 3}
    if command is not None:
        assert params['input'] == command['resume']
        assert params['force_resume'] is True
    else:
        assert 'read all sources' in params['input']['messages'][0]['content']
    saved = repo.get('task', task['id'])
    assert saved['run_id'] == 'isolated-run' and saved['status'] == 'running'
    assert saved['run_status'] == 'pending'


@pytest.mark.asyncio
async def test_failed_native_start_does_not_mark_task_running(monkeypatch, empty_capability):
    create = AsyncMock(side_effect=RuntimeError('native server unavailable'))
    save = Mock()
    monkeypatch.setattr(task_runtime, 'sdk', lambda: SimpleNamespace(http=SimpleNamespace(post=create)))
    monkeypatch.setattr(task_runtime, 'save_fields', save)
    with pytest.raises(RuntimeError, match='native server unavailable'):
        await task_runtime.start_run(dict(id='isolated', thread_id='thread', revision=1,
            capability=empty_capability), message='read')
    save.assert_not_called()


@pytest.mark.asyncio
async def test_protocol_error_inside_http_200_does_not_mark_task_running(monkeypatch):
    post = AsyncMock(return_value={'type': 'error', 'error': 'unknown_error', 'message': 'native start failed'})
    save = Mock()
    monkeypatch.setattr(task_runtime, 'sdk', lambda: SimpleNamespace(http=SimpleNamespace(post=post)))
    monkeypatch.setattr(task_runtime, 'save_fields', save)
    with pytest.raises(RuntimeError, match='native start failed'):
        await task_runtime.start_run(dict(id='isolated', thread_id='thread', revision=1))
    save.assert_not_called()
