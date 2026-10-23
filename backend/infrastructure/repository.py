"""Opaque application records in GaussDB; Agent Server owns graph persistence."""
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import os
from threading import Lock, RLock
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg_pool import ConnectionPool
import simplejson as json

from backend.config import settings


def now():
    return datetime.now(timezone.utc).isoformat()


def dumps(value):
    return json.dumps(value, ensure_ascii=False, use_decimal=True, allow_nan=False,
                      default=lambda x: x.model_dump() if hasattr(x, 'model_dump') else str(x))


def loads(value):
    return json.loads(value, use_decimal=True)


class Conflict(ValueError):
    pass


class Repository:
    def __init__(self):
        import os
        self.schema = os.environ.get('GAUSSDB_SCHEMA', 'workorder_agent')
        self._pool = None
        self._pool_lock = Lock()

    def pool(self):
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    def configure(connection):
                        connection.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
                        connection.commit()
                    pool = ConnectionPool(kwargs=settings.database_options(), min_size=1, max_size=8,
                                          configure=configure, open=False, timeout=15)
                    pool.open(wait=True)
                    self._pool = pool
        return self._pool

    def close(self):
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    @contextmanager
    def connection(self):
        with self.pool().connection() as connection:
            yield connection

    def initialize(self):
        with psycopg.connect(**settings.database_options()) as connection:
            connection.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(self.schema)))
        with self.connection() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS app_objects (
                kind varchar(48) NOT NULL, object_id varchar(128) NOT NULL,
                revision integer NOT NULL, payload text NOT NULL, updated_at varchar(48) NOT NULL,
                PRIMARY KEY(kind, object_id))''')
            c.execute('''CREATE TABLE IF NOT EXISTS app_events (
                event_id varchar(48) PRIMARY KEY, task_id varchar(128) NOT NULL,
                created_at varchar(48) NOT NULL, payload text NOT NULL)''')

    def get(self, kind, object_id, required=True):
        with self.connection() as c:
            row = c.execute('SELECT payload FROM app_objects WHERE kind=%s AND object_id=%s',
                            (kind, object_id)).fetchone()
        if row:
            return loads(row[0])
        if required:
            raise KeyError(object_id)
        return None

    def get_fields(self, kind, object_id, fields):
        """Read a projection without transferring archived material and evidence."""
        pairs = [sql.SQL('{}, payload::json -> {}').format(sql.Literal(k), sql.Literal(k))
                 for k in dict.fromkeys(('id', 'revision', *fields))]
        with self.connection() as c:
            row = c.execute(sql.SQL('SELECT json_build_object({})::text FROM app_objects '
                'WHERE kind=%s AND object_id=%s').format(sql.SQL(', ').join(pairs)),
                (kind, object_id)).fetchone()
        if not row:
            raise KeyError(object_id)
        return loads(row[0])

    def mutate_fields(self, kind, object_id, fields, transform, expected_revision=None):
        """Lock the row, change selected fields, and merge inside openGauss.

        json_each/json_object_agg work on openGauss 5.0; jsonb_set and the
        PostgreSQL jsonb concatenation operator are unavailable on this server.
        The large opaque payload never makes a round trip for a usage update.
        """
        from copy import deepcopy
        pairs = [sql.SQL('{}, payload::json -> {}').format(sql.Literal(k), sql.Literal(k))
                 for k in dict.fromkeys(('id', 'revision', *fields))]
        with self.connection() as c:
            row = c.execute(sql.SQL('SELECT json_build_object({})::text FROM app_objects '
                'WHERE kind=%s AND object_id=%s FOR UPDATE').format(sql.SQL(', ').join(pairs)),
                (kind, object_id)).fetchone()
            if not row:
                raise KeyError(object_id)
            value = loads(row[0])
            if expected_revision is not None and value['revision'] != expected_revision:
                raise Conflict(f"revision {expected_revision} 已过期；当前为 {value['revision']}")
            before = deepcopy(value)
            replacement = transform(value)
            if replacement is not None:
                value = replacement
            patch = {k: v for k, v in value.items() if k not in before or before[k] != v}
            patch['updated_at'] = now()
            c.execute('''UPDATE app_objects SET payload=(
                SELECT json_object_agg(key,value)::text FROM (
                    SELECT key,value FROM json_each(app_objects.payload::json)
                    WHERE key <> ALL(%s::text[])
                    UNION ALL SELECT key,value FROM json_each(%s::json)
                ) AS merged), revision=%s, updated_at=%s
                WHERE kind=%s AND object_id=%s''',
                (list(patch), dumps(patch), value['revision'], patch['updated_at'], kind, object_id))
        return {**value, 'updated_at': patch['updated_at']}

    def list(self, kind, limit=100):
        with self.connection() as c:
            return [loads(r[0]) for r in c.execute(
                'SELECT payload FROM app_objects WHERE kind=%s ORDER BY updated_at DESC LIMIT %s',
                (kind, limit)).fetchall()]

    def list_projection(self, kind, fields, *, counts=None, arrays=None, limit=100, exclude_deleted=False):
        """Read selected JSON fields; limit=None scans all matching saved objects."""
        pairs = [sql.SQL('{}, payload::json -> {}').format(sql.Literal(key), sql.Literal(key))
                 for key in fields]
        for name, key in (counts or {}).items():
            pairs.append(sql.SQL("{}, CASE WHEN json_typeof(payload::json -> {}) = 'array' "
                                 "THEN json_array_length(payload::json -> {}) ELSE 0 END").format(
                                     sql.Literal(name), sql.Literal(key), sql.Literal(key)))
        for key, selected in (arrays or {}).items():
            entries = [sql.SQL('{}, item -> {}').format(sql.Literal(field), sql.Literal(field))
                       for field in selected]
            pairs.append(sql.SQL("{}, (SELECT COALESCE(json_agg(json_build_object({})), '[]'::json) "
                                 "FROM json_array_elements(CASE WHEN json_typeof(payload::json -> {}) = 'array' "
                                 "THEN payload::json -> {} ELSE '[]'::json END) AS item)").format(
                                     sql.Literal(key), sql.SQL(', ').join(entries),
                                     sql.Literal(key), sql.Literal(key)))
        visibility = sql.SQL("AND (payload::json ->> 'deleted_at') IS NULL ") if exclude_deleted else sql.SQL('')
        bound = sql.SQL('') if limit is None else sql.SQL(' LIMIT %s')
        query = sql.SQL('SELECT json_build_object({})::text FROM app_objects WHERE kind=%s {}'
                        'ORDER BY updated_at DESC{}').format(sql.SQL(', ').join(pairs), visibility, bound)
        params = (kind,) if limit is None else (kind, limit)
        with self.connection() as c:
            return [loads(row[0]) for row in c.execute(query, params).fetchall()]

    def create(self, kind, value):
        value.setdefault('id', str(uuid4()))
        value.setdefault('revision', 1)
        value.setdefault('created_at', now())
        value['updated_at'] = now()
        with self.connection() as c:
            c.execute('INSERT INTO app_objects(kind,object_id,revision,payload,updated_at) VALUES(%s,%s,%s,%s,%s)',
                      (kind, value['id'], value['revision'], dumps(value), value['updated_at']))
        return value

    def replace(self, kind, object_id, value, expected_revision=None):
        """Write a full record without reading its previous payload."""
        value['updated_at'] = now()
        query = ('UPDATE app_objects SET revision=%s,payload=%s,updated_at=%s '
                 'WHERE kind=%s AND object_id=%s')
        params = [value['revision'], dumps(value), value['updated_at'], kind, object_id]
        if expected_revision is not None:
            query += ' AND revision=%s'
            params.append(expected_revision)
        with self.connection() as c:
            changed = c.execute(query, params).rowcount
            if not changed:
                exists = c.execute('SELECT 1 FROM app_objects WHERE kind=%s AND object_id=%s',
                                   (kind, object_id)).fetchone()
                if not exists:
                    raise KeyError(object_id)
                raise Conflict('持久化版本已变化，未覆盖暂存任务')
        return value

    def mutate(self, kind, object_id, transform, expected_revision=None):
        with self.connection() as c:
            row = c.execute('SELECT payload FROM app_objects WHERE kind=%s AND object_id=%s FOR UPDATE',
                            (kind, object_id)).fetchone()
            if not row:
                raise KeyError(object_id)
            value = loads(row[0])
            if expected_revision is not None and value['revision'] != expected_revision:
                raise Conflict(f"revision {expected_revision} 已过期；当前为 {value['revision']}")
            replacement = transform(value)
            if replacement is not None:
                value = replacement
            value['updated_at'] = now()
            c.execute('UPDATE app_objects SET revision=%s,payload=%s,updated_at=%s WHERE kind=%s AND object_id=%s',
                      (value['revision'], dumps(value), value['updated_at'], kind, object_id))
        return value

    def event(self, task_id, event, **values):
        record = dict(id=str(uuid4()), task_id=task_id, event=event, at=now(), **values)
        with self.connection() as c:
            c.execute('INSERT INTO app_events(event_id,task_id,created_at,payload) VALUES(%s,%s,%s,%s)',
                      (record['id'], task_id, record['at'], dumps(record)))
        return record

    def events(self, task_id, limit=100):
        with self.connection() as c:
            return [loads(r[0]) for r in c.execute(
                'SELECT payload FROM app_events WHERE task_id=%s ORDER BY created_at DESC LIMIT %s',
                (task_id, limit)).fetchall()]

    def event_counts(self, task_ids):
        """Count persisted event kinds, independently of the trace display limit."""
        if not task_ids:
            return {}
        with self.connection() as c:
            rows = c.execute('SELECT task_id, payload::json ->> %s, count(*) FROM app_events '
                             'WHERE task_id = ANY(%s) GROUP BY 1, 2',
                             ('event', list(task_ids))).fetchall()
        result = {}
        for task_id, event, count in rows:
            result.setdefault(task_id, {})[event] = count
        return result


class StagedRepository:
    """Redis-staged task state with GaussDB flushed at stage boundaries.

    Reads prefer Redis and fall back to GaussDB. Task mutations update Redis
    and mark the task dirty; ``flush`` writes one durable row. Other record
    kinds and audit events stay direct in GaussDB. If Redis is unavailable the
    class behaves like the durable repository.
    """

    def __init__(self, store=None, cache=None):
        self.store = store or Repository()
        self._cache = cache
        self._cache_lock = Lock()
        self._task_locks = defaultdict(RLock)
        self.ttl = int(os.environ.get('TASK_CACHE_TTL', '3600'))
        self.dirty_key = 'workorder:tasks:dirty'

    def __getattr__(self, name):
        return getattr(self.store, name)

    def _lock(self, task_id):
        return self._task_locks[task_id]

    def _key(self, task_id):
        return f'workorder:task:{task_id}'

    def cache(self):
        if self._cache is not None:
            return self._cache or None
        with self._cache_lock:
            if self._cache is None:
                url = os.environ.get('REDIS_URL')
                if not url:
                    self._cache = False
                else:
                    import redis
                    self._cache = redis.Redis.from_url(url, socket_timeout=3)
        return self._cache or None

    def _read(self, task_id):
        client = self.cache()
        if not client:
            return None
        try:
            raw = client.get(self._key(task_id))
            return loads(raw) if raw else None
        except Exception:
            return None

    def _write(self, task_id, value, dirty=True):
        client = self.cache()
        if not client:
            return False
        try:
            client.setex(self._key(task_id), self.ttl, dumps(value))
            if dirty:
                client.sadd(self.dirty_key, task_id)
            return True
        except Exception:
            return False

    def _load(self, task_id, required=True):
        """Read through cache without marking an unmodified task dirty."""
        cached = self._read(task_id)
        if cached is not None:
            return deepcopy(cached)
        value = self.store.get('task', task_id, required)
        if value is not None:
            self._write(task_id, value, dirty=False)
        return value

    def _dirty(self, task_id):
        client = self.cache()
        if not client:
            return False
        try:
            return bool(client.sismember(self.dirty_key, task_id))
        except Exception:
            return False

    def _clean(self, task_id):
        client = self.cache()
        if not client:
            return
        try:
            client.srem(self.dirty_key, task_id)
        except Exception:
            pass

    def get(self, kind, object_id, required=True):
        if kind != 'task':
            return self.store.get(kind, object_id, required)
        with self._lock(object_id):
            return self._load(object_id, required)

    def get_fields(self, kind, object_id, fields):
        if kind != 'task':
            return self.store.get_fields(kind, object_id, fields)
        with self._lock(object_id):
            cached = self._read(object_id)
            if cached is not None:
                keys = dict.fromkeys(('id', 'revision', *fields))
                return {key: deepcopy(cached.get(key)) for key in keys}
        return self.store.get_fields(kind, object_id, fields)

    def mutate(self, kind, object_id, transform, expected_revision=None):
        if kind != 'task':
            return self.store.mutate(kind, object_id, transform, expected_revision)
        with self._lock(object_id):
            current = self.get('task', object_id)
            if expected_revision is not None and current['revision'] != expected_revision:
                raise Conflict(f"revision {expected_revision} 已过期；当前为 {current['revision']}")
            replacement = transform(current)
            value = current if replacement is None else replacement
            value['updated_at'] = now()
            if self._write(object_id, value):
                return deepcopy(value)
            return self.store.mutate(kind, object_id, lambda _: value,
                                     expected_revision=current['revision'])

    def mutate_fields(self, kind, object_id, fields, transform, expected_revision=None):
        if kind != 'task':
            return self.store.mutate_fields(kind, object_id, fields, transform, expected_revision)
        with self._lock(object_id):
            current = self.get('task', object_id)
            if expected_revision is not None and current['revision'] != expected_revision:
                raise Conflict(f"revision {expected_revision} 已过期；当前为 {current['revision']}")
            keys = dict.fromkeys(('id', 'revision', *fields))
            projection = {key: deepcopy(current.get(key)) for key in keys}
            before = deepcopy(projection)
            replacement = transform(projection)
            changed = projection if replacement is None else replacement
            # Match Repository.mutate_fields: selected absent fields are read
            # as None, but only actual changes belong in the stored record.
            patch = {key: value for key, value in changed.items()
                     if key not in before or before[key] != value}
            value = {**current, **patch, 'updated_at': now()}
            if self._write(object_id, value):
                return deepcopy(value)
            return self.store.mutate(kind, object_id, lambda _: value,
                                     expected_revision=current['revision'])

    def create(self, kind, value):
        created = self.store.create(kind, value)
        if kind == 'task':
            self._write(created['id'], created, dirty=False)
        return created

    def flush(self, task_id):
        """Write the staged task once; keep it dirty if the durable write fails."""
        if not self._dirty(task_id):
            return None
        with self._lock(task_id):
            cached = self._read(task_id)
            if cached is None:
                self._clean(task_id)
                return None
            durable = None
            try:
                durable = (self.store.get_fields('task', task_id, ['revision'])
                           if hasattr(self.store, 'get_fields') else
                           self.store.get('task', task_id, required=False))
            except KeyError:
                durable = None
            if durable is None:
                self.store.create('task', cached)
            else:
                if durable.get('revision', 0) > cached.get('revision', 0):
                    # Another writer moved ahead; drop the stale cache so the
                    # next read reloads the durable version instead of serving it.
                    client = self.cache()
                    if client:
                        try:
                            client.delete(self._key(task_id))
                        except Exception:
                            pass
                    self._clean(task_id)
                    raise Conflict('暂存任务版本落后于持久化版本，未刷库')
                if hasattr(self.store, 'replace'):
                    self.store.replace('task', task_id, cached,
                                       expected_revision=durable.get('revision'))
                else:
                    self.store.mutate('task', task_id, lambda _: cached,
                                      expected_revision=durable.get('revision'))
            self._clean(task_id)
            return cached

    def flush_dirty(self, limit=50):
        client = self.cache()
        if not client:
            return []
        try:
            ids = list(client.smembers(self.dirty_key))[:limit]
        except Exception:
            return []
        flushed = []
        for raw in ids:
            task_id = raw.decode() if isinstance(raw, bytes) else str(raw)
            lock = self._lock(task_id)
            if not lock.acquire(blocking=False):
                # The run owns this task's stage right now; it flushes itself.
                continue
            try:
                self.flush(task_id)
                flushed.append(task_id)
            except Conflict:
                continue
            finally:
                lock.release()
        return flushed


@lru_cache
def repository():
    return StagedRepository()
