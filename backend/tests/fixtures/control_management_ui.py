"""Isolated management UI: real registry, packages, MCP and LangSmith routes.

Only storage and the read-only task list are synthetic. No production task or
configuration is modified. Stop with Ctrl+C; temporary registry is discarded.
"""
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.api.responses import response
from backend.api.routes import extensions, improvements
from backend.config import transactions
from backend.extensions import snapshots, skill_versions
from backend.harness.dispatch import PolicyDenied
from backend.infrastructure.repository import Conflict
from backend.tests.test_improvement import MemoryRepository


def main():
    with tempfile.TemporaryDirectory(prefix='billing-control-ui-') as directory:
        temporary = Path(directory)
        for name in ('config', 'skills', 'agents'):
            shutil.copytree(ROOT / 'backend' / name, temporary / name,
                            ignore=shutil.ignore_patterns('__pycache__', '.*'))
        transactions.ROOT = snapshots.ROOT = temporary
        snapshots.RELEASES = skill_versions.RELEASES = temporary / 'releases'
        repo = MemoryRepository()
        improvements.repository = snapshots.repository = lambda: repo
        cap = snapshots.snapshot()
        task = repo.create('task', dict(id='control-fixture', title='控制台验收 · 合成账单', revision=3,
            accounting_entity='Demo Carrier', capability=cap, records=[], charges=[],
            asset_ids=['fixture-source'], status='completed', control='running'))
        app = FastAPI(title='隔离管理验收')
        app.include_router(extensions.router)
        app.include_router(improvements.router)
        for kind, status in ((KeyError, 404), (Conflict, 409), (ValueError, 422), (PolicyDenied, 409)):
            async def handle(request, exc, code=status):
                return response({'message': str(exc)}, code)
            app.add_exception_handler(kind, handle)

        @app.get('/api/health')
        def health():
            return {'status': 'isolated-test', 'database': 'synthetic-memory', 'redis': 'unused'}

        @app.get('/api/bills')
        def bills():
            return [task]

        @app.get('/api/tasks/control-fixture')
        def source_task():
            return task

        app.mount('/app', StaticFiles(directory=ROOT / 'frontend' / 'dist', html=True))
        print(f'Isolated root: {temporary}', flush=True)
        uvicorn.run(app, host='127.0.0.1', port=2025)


if __name__ == '__main__':
    main()
