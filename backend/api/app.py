"""FastAPI assembly mounted inside the official Agent Server."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.harness.dispatch import PolicyDenied
from backend.infrastructure.repository import Conflict, now, repository

from .responses import response
from .routes import assets, confidence, conversation, exports, extensions, health, improvements, experiences, observability, reviews, tasks


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(repository().initialize)
    # The dev runtime may stop between two timer updates. Never count downtime as active work.
    def recover_clocks():
        repo = repository()
        for task in repo.list('task', 10000):
            if task.get('usage', {}).get('active_depth', 0):
                def recover(current):
                    usage = current['usage']
                    usage['interrupted_interval'] = dict(start=usage.pop('active_since', None),
                        recovered_at=now(), duration='unknown_after_process_exit')
                    usage['active_depth'] = 0
                    current.update(status='recovery_required', control='paused')
                repo.mutate('task', task['id'], recover)
                if hasattr(repo, 'flush'):
                    repo.flush(task['id'])
    await asyncio.to_thread(recover_clocks)
    try:
        yield
    finally:
        await asyncio.to_thread(repository().close)


app = FastAPI(title='航运智能账单助手', version='1.0.0', lifespan=lifespan)
for route_group in (health, assets, tasks, confidence, reviews, conversation, exports, extensions, improvements, experiences, observability):
    app.include_router(route_group.router)


@app.middleware('http')
async def persist_staged_tasks(request, call_next):
    """Durable write-behind: every API request is a persistence stage end."""
    response = await call_next(request)
    if request.url.path.startswith('/api'):
        repo = repository()
        if hasattr(repo, 'flush_dirty'):
            try:
                await asyncio.to_thread(repo.flush_dirty)
            except Exception:
                # A durability failure must not turn a served request into an
                # error; the task stays dirty for the next stage boundary.
                pass
    return response


@app.exception_handler(KeyError)
async def missing(request, exc):
    return response({'error': 'NOT_FOUND', 'message': f'记录不存在: {exc}'}, 404)


@app.exception_handler(Conflict)
async def conflict(request, exc):
    return response({'error': getattr(exc, 'code', 'REVISION_CONFLICT'), 'message': str(exc)}, 409)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return response({'error': 'INVALID_INPUT', 'message': str(exc)}, 422)


@app.exception_handler(PolicyDenied)
async def denied(request, exc):
    return response({'error': 'POLICY_DENIED', 'message': str(exc)}, 409)


if (settings.FRONTEND / 'dist').is_dir():
    app.mount('/app', StaticFiles(directory=settings.FRONTEND / 'dist', html=True), name='workbench')
