"""Measure overlapping active calls once, apart from human waiting."""
import time
import asyncio
from contextlib import contextmanager, asynccontextmanager
from backend.infrastructure.repository import repository


@contextmanager
def active(task_id):
    if not task_id:
        yield
        return
    def start(task):
        usage = task.get('usage') or {}
        task['usage'] = usage
        if not usage.get('active_depth', 0):
            usage['active_since'] = time.time()
        usage['active_depth'] = usage.get('active_depth', 0) + 1
    def finish(task):
        usage = task['usage']
        usage['active_depth'] = max(0, usage.get('active_depth', 1) - 1)
        if not usage['active_depth']:
            start = usage.pop('active_since', time.time())
            usage['active_seconds'] = float(usage.get('active_seconds', 0)) + time.time() - float(start)
    repo = repository()
    def update(transform):
        if hasattr(repo, 'mutate_fields'):
            return repo.mutate_fields('task', task_id, ['usage'], transform)
        return repo.mutate('task', task_id, transform)
    update(start)
    try:
        yield
    finally:
        update(finish)


@asynccontextmanager
async def active_async(task_id):
    """Keep database timing updates off the Agent Server event loop."""
    interval = active(task_id)
    await asyncio.to_thread(interval.__enter__)
    try:
        yield
    finally:
        await asyncio.to_thread(interval.__exit__, None, None, None)
