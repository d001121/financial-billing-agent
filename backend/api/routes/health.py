"""Application entry point and dependency health endpoints."""
import asyncio
import os

from fastapi import APIRouter
from fastapi.responses import RedirectResponse
import redis

from backend.config import settings
from backend.infrastructure.repository import repository

from ..responses import response

router = APIRouter(tags=['health'])


@router.get('/')
async def index():
    return RedirectResponse('/app/')


@router.get('/api/health')
async def health():
    checks = {}
    try:
        await asyncio.to_thread(repository().list, 'task', 1)
        checks['database'] = {'status': 'ok', 'provider': 'GaussDB'}
    except Exception as exc:
        checks['database'] = {'status': 'error', 'message': str(exc)}
    try:
        cache = redis.Redis.from_url(os.environ['REDIS_URL'], socket_timeout=3)
        await asyncio.to_thread(cache.ping)
        checks['redis'] = {'status': 'ok'}
    except redis.RedisError as exc:
        checks['redis'] = {'status': 'error', 'message': str(exc)}
    return response(dict(status='ok' if all(c['status'] == 'ok' for c in checks.values()) else 'degraded',
                         services=checks, model=os.environ['LLM_MODEL_NAME'], enable_thinking=False,
                         ocr={'endpoint': settings.OCR_URL, 'requires_download_url': True},
                         persistence='官方AsyncSqliteSaver检查点；线程/运行元数据使用本地dev刷盘'))
