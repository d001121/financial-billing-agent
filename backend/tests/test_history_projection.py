"""Projection contract for an untruncated historical scan; no live database."""
from contextlib import contextmanager

from backend.infrastructure.repository import Repository


def test_history_projection_has_no_limit_while_regular_lists_keep_the_default(monkeypatch):
    repo, sent = Repository(), []
    class Cursor:
        def execute(self, query, params):
            sent.append((query.as_string(), params))
            return self
        def fetchall(self):
            return []
    @contextmanager
    def connection():
        yield Cursor()
    monkeypatch.setattr(repo, 'connection', connection)
    repo.list_projection('task', ('id', 'revision'), arrays={'records': ('charge_id',)},
                         limit=None, exclude_deleted=True)
    assert 'LIMIT' not in sent[-1][0]
    assert sent[-1][1] == ('task',)
    assert 'deleted_at' in sent[-1][0]
    assert 'json_array_elements' in sent[-1][0]
    repo.list_projection('task', ('id',))
    assert 'LIMIT %s' in sent[-1][0]
    assert sent[-1][1] == ('task', 100)
