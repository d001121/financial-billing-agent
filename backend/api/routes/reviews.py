"""Human revisions and approval bound to the current artifact version."""
import asyncio

from fastapi import APIRouter, Request

from backend.extensions.skill_versions import function
from backend.harness.dispatch import check
from backend.infrastructure.repository import loads, now, repository
from backend.tools.artifacts import reconcile_saved, validate_and_store
from backend.tools.review import settle_saved
from backend.harness.feedback import pending_feedback
from backend.infrastructure.repository import Conflict

from ..responses import response
from ..schemas import export_binding
from ..task_runtime import require_idle

router = APIRouter(tags=['reviews'])

# A settled extraction may be closed by the caller even when fields stay null.
# Processing, input-waiting and budget states still expect a concrete answer.
SETTLED_REVIEW_STATUSES = frozenset({
    'completed_with_gaps', 'awaiting_review', 'needs_review',
    'waiting_review', 'ready_for_review', 'review_deferred',
})


@router.patch('/api/tasks/{task_id}/revision')
async def revise_task(task_id: str, request: Request):
    body = loads(await request.body())
    task = repository().get('task', task_id)
    await require_idle(task)
    task = check(task_id, skill='human-review', allow_paused=True)
    payload = dict(task, **{k: v for k, v in body.items() if k in
                   ('expected_revision', 'operations', 'reason', 'accounting_entity')})
    result = await asyncio.to_thread(function(task['capability'], 'human-review', 'apply_revision'), payload)
    if not result['valid']:
        return response(result, 409 if any(i['code'] == 'REVISION_CONFLICT' for i in result['issues']) else 422)
    def apply(current):
        current['history'] = [*current.get('history', []), result]
        current.update(revision=result['revision'], records=result['records'],
                       reason=body['reason'], approval=None, validation=None, export=None,
                       status='awaiting_review', auto_review=None, review_confirmation=None,
                       feedback=None)
        if 'accounting_entity' in body:
            current['accounting_entity'] = body['accounting_entity']
        recalculated = function(current['capability'], 'human-review', 'prepare_recalculation')(
            {'task': current, 'review': result})
        current.update(recalculated)
    task = await asyncio.to_thread(repository().mutate, 'task', task_id, apply,
                                   expected_revision=body['expected_revision'])
    await asyncio.to_thread(reconcile_saved, task_id)
    task = await asyncio.to_thread(settle_saved, task_id)
    await asyncio.to_thread(repository().event, task_id, 'human_revision', revision=task['revision'], reason=body['reason'])
    return response(task)


@router.post('/api/tasks/{task_id}/complete-review')
async def complete_review(task_id: str, request: Request):
    """Let the caller finish review with gaps instead of forcing every field."""
    body = loads(await request.body())
    task = repository().get('task', task_id)
    if task.get('deleted_at'):
        raise KeyError('账单已从工作台删除')
    if task['revision'] != body.get('expected_revision'):
        raise Conflict('账单已更新，请刷新后重新提交')
    if (task.get('review_confirmation') or {}).get('revision') == task['revision']:
        return response(task)
    if (task.get('review_request') or {}).get('state') == 'pending':
        raise Conflict('当前还有待回答的问题，请先处理后再完成审核')
    if task.get('status') not in SETTLED_REVIEW_STATUSES:
        raise Conflict('账单仍在处理或有待补充的信息，暂不能完成审核')
    await require_idle(task)
    check(task_id, skill='human-review', allow_paused=True)
    if not task.get('records'):
        raise ValueError('当前还没有可完成审核的费用记录')
    reason = (body.get('reason') or '').strip() or '调用方确认完成审核；未提供的字段保持null'
    def complete(current):
        current['review_confirmation'] = dict(
            decision='completed_with_gaps', revision=current['revision'],
            at=now(), reason=reason)
        current['status'] = 'completed'
        current['summary'] = '已完成审核；未提供的字段保持null，可随时修订补充'
    saved = await asyncio.to_thread(repository().mutate, 'task', task_id, complete,
                                    expected_revision=task['revision'])
    await asyncio.to_thread(repository().event, task_id, 'review_completed',
                            revision=saved['revision'], reason=reason)
    return response(saved)


@router.post('/api/tasks/{task_id}/approve')
async def approve_task(task_id: str, request: Request):
    body = loads(await request.body())
    task = repository().get('task', task_id)
    await require_idle(task)
    check(task_id, skill='human-review', allow_paused=True)
    if pending_feedback(task):
        raise Conflict('人工修改尚待智能体处理，请继续任务后确认最终结果')
    task = repository().get('task', task_id)
    if body.get('decision') not in ('approve', 'reject') or not body.get('reason'):
        raise ValueError('请提供approve/reject及审核依据reason')
    checked = await asyncio.to_thread(validate_and_store, task_id)
    if body['decision'] == 'approve' and not checked['ok']:
        return response(dict(message='校验尚未通过，不能批准正式导出', validation=checked), 422)
    binding = function(task['capability'], 'human-review', 'approval_binding')(export_binding(task))
    task = await asyncio.to_thread(repository().mutate, 'task', task_id, lambda t: t.update(
        approval=dict(decision=body['decision'], binding=binding, reason=body['reason'], at=now()),
        status='approved' if body['decision'] == 'approve' else 'awaiting_review'),
        expected_revision=body['expected_revision'])
    repository().event(task_id, 'approval', decision=body['decision'], revision=task['revision'])
    return response(task)
