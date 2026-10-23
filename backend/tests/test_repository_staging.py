"""Redis-staged task state with GaussDB write-behind, no external services."""
from copy import deepcopy

import pytest

from backend.infrastructure.repository import Conflict, StagedRepository


class MemoryStore:
    def __init__(self, records=None):
        self.records = records or {}

    def get(self, kind, object_id, required=True):
        if (kind, object_id) in self.records:
            return deepcopy(self.records[(kind, object_id)])
        if required:
            raise KeyError(object_id)
        return None

    def get_fields(self, kind, object_id, fields):
        if (kind, object_id) not in self.records:
            raise KeyError(object_id)
        record = self.records[(kind, object_id)]
        return {key: deepcopy(record.get(key)) for key in dict.fromkeys(('id', 'revision', *fields))}

    def create(self, kind, value):
        value = deepcopy(value)
        value.setdefault('id', 'task-1')
        value.setdefault('revision', 1)
        self.records[(kind, value['id'])] = deepcopy(value)
        return value

    def mutate(self, kind, object_id, transform, expected_revision=None):
        value = self.get(kind, object_id)
        if expected_revision is not None and value['revision'] != expected_revision:
            raise Conflict('stale')
        replacement = transform(value)
        value = value if replacement is None else replacement
        value['updated_at'] = 'durable'
        self.records[(kind, object_id)] = deepcopy(value)
        return deepcopy(value)

    def replace(self, kind, object_id, value, expected_revision=None):
        value = deepcopy(value)
        current = self.get(kind, object_id)
        if expected_revision is not None and current['revision'] != expected_revision:
            raise Conflict('stale')
        value['updated_at'] = 'durable'
        self.records[(kind, object_id)] = deepcopy(value)
        return value


class MemoryCache:
    def __init__(self):
        self.values = {}
        self.dirty = set()
        self.fail = False

    def get(self, key):
        self._check()
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self._check()
        self.values[key] = value
        return True

    def sadd(self, key, value):
        self._check()
        self.dirty.add(value)
        return 1

    def sismember(self, key, value):
        self._check()
        return value in self.dirty

    def srem(self, key, value):
        self._check()
        self.dirty.discard(value)
        return 1

    def smembers(self, key):
        self._check()
        return set(self.dirty)

    def delete(self, key):
        self._check()
        self.values.pop(key, None)
        return 1

    def _check(self):
        if self.fail:
            raise RuntimeError('redis unavailable')


def staged(task=None):
    store = MemoryStore()
    if task:
        store.create('task', task)
    return StagedRepository(store=store, cache=MemoryCache()), store


def test_mutations_stay_in_cache_until_flush():
    repo, store = staged({'title': 'bill', 'revision': 1, 'materials': ['raw']})
    cache = repo.cache()

    result = repo.mutate('task', 'task-1', lambda task: task.update(title='edited', revision=2),
                         expected_revision=1)

    assert result['title'] == 'edited'
    assert repo.get('task', 'task-1')['title'] == 'edited'
    assert store.get('task', 'task-1')['title'] == 'bill'
    assert 'task-1' in cache.dirty

    repo.flush('task-1')

    assert store.get('task', 'task-1')['title'] == 'edited'
    assert store.get('task', 'task-1')['revision'] == 2
    assert 'task-1' not in cache.dirty


def test_mutate_fields_projects_and_merges_without_touching_material():
    repo, store = staged({'title': 'bill', 'revision': 1, 'usage': {'calls': 1},
                          'materials': [{'body': 'x' * 1000}]})
    repo.get('task', 'task-1')
    seen = {}

    def bump(projection):
        seen.update(projection)
        projection['usage'] = {'calls': 2}

    repo.mutate_fields('task', 'task-1', ['usage'], bump, expected_revision=1)

    assert seen == {'id': 'task-1', 'revision': 1, 'usage': {'calls': 1}}
    cached = repo.get('task', 'task-1')
    assert cached['usage'] == {'calls': 2}
    assert cached['materials'] == [{'body': 'x' * 1000}]
    assert store.get('task', 'task-1')['usage'] == {'calls': 1}


@pytest.mark.parametrize('cache_failure', [False, True])
def test_progress_projection_does_not_persist_absent_read_fields(cache_failure):
    # Bill4: a progress receipt reads optional collections before the first save.
    # Projection placeholders must not turn those absent lists into stored nulls.
    repo, store = staged({'title': 'bill', 'revision': 1, 'charges': []})
    repo.cache().fail = cache_failure

    def claim(projection):
        assert projection['candidate_digests'] is None
        projection['dispatch_history'] = {'attempts': {'call-1': {'status': 'running'}}}

    repo.mutate_fields('task', 'task-1',
        ['dispatch_history', 'candidate_digests', 'documents', 'totals'], claim,
        expected_revision=1)

    def first_save(task):
        assert 'candidate_digests' not in task
        assert 'documents' not in task and 'totals' not in task
        assert 'first' not in task.get('candidate_digests', [])
        task.setdefault('candidate_digests', []).append('first')

    repo.mutate('task', 'task-1', first_save, expected_revision=1)
    repo.flush('task-1')
    result = store.get('task', 'task-1')
    assert result['candidate_digests'] == ['first']
    assert result['dispatch_history']['attempts']['call-1']['status'] == 'running'


def test_projection_keeps_explicit_clear_and_nested_change():
    repo, _ = staged({'title': 'bill', 'revision': 1, 'usage': {'calls': 1},
                      'approval': {'revision': 1}, 'optional': None})

    def change(projection):
        projection['usage']['calls'] += 1
        projection['approval'] = None

    result = repo.mutate_fields('task', 'task-1',
        ['usage', 'approval', 'optional', 'absent'], change, expected_revision=1)
    assert result['usage'] == {'calls': 2}
    assert result['approval'] is None and result['optional'] is None
    assert 'absent' not in result


def test_flush_refuses_to_overwrite_a_newer_durable_revision():
    repo, store = staged({'title': 'bill', 'revision': 1})
    repo.mutate('task', 'task-1', lambda task: task.update(title='staged'), expected_revision=1)
    store.records[('task', 'task-1')]['revision'] = 3

    with pytest.raises(Conflict):
        repo.flush('task-1')

    assert 'workorder:task:task-1' not in repo.cache().values
    assert 'task-1' not in repo.cache().dirty


def test_redis_failure_falls_back_to_durable_writes():
    repo, store = staged({'title': 'bill', 'revision': 1})
    repo.cache().fail = True

    repo.mutate('task', 'task-1', lambda task: task.update(title='direct'), expected_revision=1)

    assert store.get('task', 'task-1')['title'] == 'direct'


def test_flush_dirty_persists_every_staged_task():
    repo, store = staged()
    store.create('task', {'id': 'task-1', 'revision': 1})
    store.create('task', {'id': 'task-2', 'revision': 1})
    repo.mutate('task', 'task-1', lambda task: task.update(title='one'), expected_revision=1)
    repo.mutate('task', 'task-2', lambda task: task.update(title='two'), expected_revision=1)

    flushed = repo.flush_dirty()

    assert sorted(flushed) == ['task-1', 'task-2']
    assert store.get('task', 'task-1')['title'] == 'one'
    assert store.get('task', 'task-2')['title'] == 'two'
    assert repo.cache().dirty == set()


def test_read_through_does_not_mark_an_unchanged_task_dirty():
    repo, store = staged({'title': 'bill', 'revision': 1})

    repo.get('task', 'task-1')
    repo.get_fields('task', 'task-1', ['title'])

    assert repo.cache().dirty == set()


def test_policy_check_projects_only_when_the_task_is_not_returned(monkeypatch):
    from backend.harness import dispatch

    reads = {'full': 0, 'fields': 0}

    class Store(MemoryStore):
        def get(self, kind, object_id, required=True):
            reads['full'] += 1
            return super().get(kind, object_id, required)

        def get_fields(self, kind, object_id, fields):
            reads['fields'] += 1
            return super().get_fields(kind, object_id, fields)

    store = Store({('task', 'task-1'): {'id': 'task-1', 'revision': 1, 'control': 'running',
                                        'capability': {'config': {'runtime': {}}}}})
    repo = StagedRepository(store=store, cache=MemoryCache())
    monkeypatch.setattr(dispatch, 'repository', lambda: repo)
    monkeypatch.setattr(dispatch, 'read_config', lambda name: {'hooks': [
        {'name': 'capability', 'enabled': True}, {'name': 'budget', 'enabled': True}]})

    dispatch.check('task-1', policy_only=True)
    assert reads == {'full': 0, 'fields': 1}

    task = dispatch.check('task-1')
    assert task['capability'] == {'config': {'runtime': {}}}
    assert reads['full'] == 1
