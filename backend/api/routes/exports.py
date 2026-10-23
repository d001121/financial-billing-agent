"""Validated draft and approved billing JSON downloads."""
import asyncio

from fastapi import APIRouter
from fastapi.responses import Response

from backend.extensions.skill_versions import function
from backend.harness.dispatch import check
from backend.harness.feedback import pending_feedback
from backend.hooks.validation import validate
from backend.infrastructure.repository import Conflict, now, repository

from ..responses import response
from ..schemas import export_binding
from ..task_runtime import require_idle

router = APIRouter(tags=['exports'])


@router.get('/api/tasks/{task_id}/export')
async def export_task(task_id: str, draft: bool = False, revision: int | None = None):
    task = repository().get('task', task_id)
    await require_idle(task)
    if not draft and pending_feedback(task):
        raise Conflict('人工修改尚待智能体处理，请继续任务后导出正式结果')
    check(task_id, skill='billing-export', allow_paused=True)
    generated = {}
    def form(current):
        if revision is not None and revision != current['revision']:
            raise Conflict('导出revision已过期')
        payload = dict(current, **export_binding(current))
        validation = validate(payload, event='export', require_approval=not draft)
        if not validation['ok'] and not draft:
            generated.update(error=dict(message='当前版本未通过正式导出校验', validation=validation))
            return
        if draft:
            payload['records'] = [{**r, 'operation': 'PENDING_REVIEW'} for r in current.get('records', [])]
        payload['validation_revision'] = current['revision']
        result = function(current['capability'], 'billing-export', 'build_export')(payload)
        if not result['valid']:
            generated.update(error=result)
            return
        generated.update(result, revision=current['revision'])
        current['last_export'] = dict(revision=current['revision'], draft=draft, at=now())
    await asyncio.to_thread(repository().mutate, 'task', task_id, form)
    if 'error' in generated:
        return response(generated['error'], 422)
    repository().event(task_id, 'export', revision=generated['revision'], draft=draft)
    return Response(generated['json'], media_type='application/json', headers={
        'Content-Disposition': f'attachment; filename="bills-r{generated["revision"]}{"-draft" if draft else ""}.json"'})
