"""Task creation, projections, Agent control, and artifact queries."""
import asyncio

from fastapi import APIRouter, Request, Query
import httpx
from langgraph_sdk.errors import NotFoundError

from backend.extensions.snapshots import snapshot
from backend.infrastructure.repository import Conflict, loads, repository, now
from backend.tools.artifacts import save_fields

from ..dependencies import sdk
from ..responses import response
from ..task_runtime import require_idle, start_run, sync_task, continue_feedback
from backend.harness.feedback import pending_feedback, revision_feedback

router = APIRouter(tags=['tasks'])


@router.post('/api/tasks')
async def create_task(request: Request):
    body = loads(await request.body())
    history_mode = body.get('history_mode', 'provided' if (
        'existing_records' in body or 'existing_bills' in body) else 'automatic')
    if history_mode not in {'automatic', 'provided'}:
        raise ValueError('history_mode须为automatic/provided')
    existing = body.get('existing_records', body.get('existing_bills', []))
    if not isinstance(existing, list) or any(not isinstance(row, dict) for row in existing):
        raise ValueError('已有账单须为对象数组')
    if history_mode == 'automatic' and existing:
        raise ValueError('自动历史检索不能同时提供手工旧账单范围')
    ids = body.get('asset_ids', [])
    if not ids:
        raise ValueError('至少选择一个材料')
    for asset_id in ids:
        await asyncio.to_thread(repository().get, 'asset', asset_id)
    cap = await asyncio.to_thread(snapshot)
    thread = await sdk().threads.create(metadata={'application': 'workorder-agent'})
    task = await asyncio.to_thread(repository().create, 'task', dict(title=body.get('title') or '新建账单核对',
        accounting_entity=body.get('accounting_entity'), asset_ids=ids,
        instructions=body.get('instructions', ''), existing_records=existing, history_mode=history_mode,
        update_instructions=body.get('update_instructions', []), source_urls=body.get('source_urls', {}),
        ocr_text_pointer=body.get('ocr_text_pointer'), thread_id=thread['thread_id'], run_id=None,
        status='queued', control='running', capability=cap, records=[], charges=[], sources=[], issues=[],
        usage={'model_calls': 0, 'tool_calls': 0, 'active_seconds': 0},
        reason='初次生成', validation=None, approval=None, export=None))
    try:
        task = await start_run(task, message='请处理本任务的材料并生成账单建议。调用方指令：' + task['instructions'])
    except Exception as exc:
        save_fields(task['id'], task['revision'], status='error', summary=f'官方Server运行创建失败: {type(exc).__name__}')
        raise
    return response(task, 201)


@router.get('/api/tasks')
def list_tasks():
    return response(repository().list_projection('task', (
        'id', 'title', 'accounting_entity', 'status', 'control', 'revision', 'created_at', 'updated_at',
        'thread_id', 'run_id', 'asset_ids', 'summary', 'usage', 'run_status'),
        counts={'record_count': 'records', 'issue_count': 'issues'}, exclude_deleted=True))


@router.delete('/api/tasks/{task_id}')
async def delete_task(task_id: str, expected_revision: int = Query(..., ge=1)):
    """Remove an idle bill from the workspace, retaining material and audit history."""
    task = await asyncio.to_thread(repository().get, 'task', task_id)
    if task.get('deleted_at'):
        return response(dict(id=task_id, deleted=True))
    if task['revision'] != expected_revision:
        raise Conflict('账单已更新，请刷新后重新选择删除')
    if task.get('thread_id'):
        try:
            thread = await sdk().threads.get(task['thread_id'])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
        else:
            if thread['status'] == 'busy':
                raise Conflict('账单仍在处理中，请先暂停，等在途操作结束后再删除')
    try:
        await require_idle(task)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
    if (not task.get('thread_id') and not task.get('run_id')
            and task.get('control') not in ('paused', 'cancelled')
            and task.get('status') in ('queued', 'running', 'processing')):
        raise Conflict('账单仍在处理中，请先暂停后再删除')
    def remove(current):
        if (current.get('run_id'), current.get('control')) != (task.get('run_id'), task.get('control')):
            raise Conflict('账单运行状态已更新，请刷新后重试')
        current['deleted_at'] = now()
    await asyncio.to_thread(repository().mutate, 'task', task_id, remove, expected_revision=expected_revision)
    return response(dict(id=task_id, deleted=True))


@router.get('/api/tasks/{task_id}')
async def get_task(task_id: str):
    task = await asyncio.to_thread(repository().get, 'task', task_id)
    if task.get('deleted_at'):
        raise KeyError('账单已从工作台删除')
    task = await sync_task(task)
    task['events'] = await asyncio.to_thread(repository().events, task_id, 40)
    return response(task)


@router.get('/api/tasks/{task_id}/artifacts')
def artifacts(task_id: str):
    task = repository().get('task', task_id)
    if task.get('deleted_at'):
        raise KeyError('账单已从工作台删除')
    return response(dict(task_id=task_id, revision=task['revision'], sources=task.get('sources', []),
        intake=task.get('intake', []), charges=task.get('charges', []), coverage=task.get('coverage', []),
        records=task.get('records', []), validation=task.get('validation'), export=task.get('export'),
        events=repository().events(task_id, 100)))


@router.post('/api/tasks/{task_id}/control')
async def control_task(task_id: str, request: Request):
    body = loads(await request.body())
    task = repository().get('task', task_id)
    if task.get('deleted_at'):
        raise KeyError('账单已从工作台删除')
    if body['action'] in ('pause', 'cancel'):
        state = 'paused' if body['action'] == 'pause' else 'cancelled'
        task = save_fields(task_id, task['revision'], control=state, status=state)
        if task.get('run_id'):
            try:
                run = await sdk().runs.get(task['thread_id'], task['run_id'])
            except NotFoundError:
                run = {'status': 'unknown'}
            if run['status'] in ('pending', 'running'):
                await sdk().runs.cancel(task['thread_id'], task['run_id'], action='interrupt', wait=True)
        repository().event(task_id, 'control', action=body['action'])
        return response(task)
    if body['action'] == 'resume':
        await require_idle(task, allow_feedback=True)
        state = {}
        if task.get('thread_id'):
            try:
                state = await sdk().threads.get_state(task['thread_id'], subgraphs=True)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                state = {}
            if task.get('usage', {}).get('model_calls', 0) and not state.get('checkpoint'):
                raise Conflict('检查点不可用，不能直接续跑；请保留当前业务产物并核对恢复数据')
        task = save_fields(task_id, task['revision'], control='running')
        # Explicitly continuing a historical edit also delivers its saved human
        # feedback. This does not change its revision or pinned Skill capability.
        latest = (task.get('history') or [{}])[-1]
        if not task.get('feedback') and latest.get('revision') == task['revision']:
            task = save_fields(task_id, task['revision'], feedback=revision_feedback(
                latest, task.get('reason', ''), now()))
        if body.get('resume') is not None:
            task = await start_run(task, command={'resume': body['resume']})
        elif body.get('message'):
            task = await start_run(task, message=body['message'])
        elif pending_feedback(task):
            task = await continue_feedback(task)
        elif any(t.get('interrupts') for t in state.get('tasks', [])):
            raise Conflict('当前在等待用户回复，请在聊天中说明本次目标后继续')
        elif not state.get('next'):
            task = await start_run(task, human_reply=True, message=(
                '调用方要求继续当前未完成任务。先检查已保存结果和未完成事项，自主选择必要的核对或追问；'
                '复用原材料、OCR和候选，不重新开始整单，不把旧待办当成用户唯一目标。'))
        else:
            task = await start_run(task)
        return response(task)
    if body['action'] == 'restart':
        # A rebuilt task has no checkpoint to resume.  This starts a new turn
        # from the preserved materials instead of pretending to resume.
        await require_idle(task, allow_feedback=True)
        task = save_fields(task_id, task['revision'], control='running')
        message = body.get('message') or (
            '请继续处理本任务的材料并生成账单建议。调用方指令：' + (task.get('instructions') or ''))
        task = await start_run(task, message=message)
        return response(task)
    raise ValueError('action必须是pause/cancel/resume/restart')
    raise ValueError('action必须是pause/cancel/resume')
