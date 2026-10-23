"""Bill read models and local execution evidence, using the official thread API."""
import asyncio
from fastapi import APIRouter, HTTPException
import httpx

from backend.infrastructure.repository import repository
from ..dependencies import sdk
from ..read_models import TASK_FIELDS, bill_projection, call_path
from ..responses import response

router = APIRouter(tags=['workspace'])


def bill_rows():
    # Select only business fields from arrays; OCR text/raw artifacts stay out of lists.
    rows = repository().list_projection('task', TASK_FIELDS + ('issues', 'intake_issues', 'validation'),
        arrays={'records': ('document_info', 'transaction_party', 'charge_details', 'issues'),
                'sources': ('source_id', 'name', 'parent_source_id', 'status', 'format')}, exclude_deleted=True)
    return [bill_projection(row) for row in rows]


async def live_status(rows):
    """Batch summaries, then refresh pending interrupts from current checkpoints."""
    ids = list(dict.fromkeys(row['thread_id'] for row in rows if row.get('thread_id')))
    if not ids:
        return rows
    try:
        threads = await sdk().threads.search(ids=ids, limit=len(ids),
            select=['thread_id', 'status', 'interrupts'])
    except httpx.HTTPError as exc:
        raise HTTPException(503, '运行状态暂无法同步，请重新连接后查看待办') from exc
    lookup = {thread['thread_id']: thread for thread in threads}
    by_thread = {}
    for row in rows:
        by_thread.setdefault(row.get('thread_id'), []).append(row)
    gate = asyncio.Semaphore(3)
    async def refresh(thread):
        raw = thread.get('interrupts') or {}
        pending = [item for items in raw.values() for item in items] if isinstance(raw, dict) else raw
        values = [item.get('value') or {} for item in pending if isinstance(item.get('value'), dict)]
        stale = bool(pending and thread['status'] in ('idle', 'error')) or (not pending and thread['status']=='interrupted')
        for row in by_thread.get(thread['thread_id'], []):
            stale |= any(v.get('revision') is not None and v['revision'] != row.get('revision') for v in values)
            review = row.get('review_request') or {}
            if review.get('state') == 'pending' and review.get('revision') == row.get('revision'):
                stale |= review.get('id') not in {v.get('request_id') for v in values}
        # Healthy summaries need no full checkpoint/message reads on every list.
        if not stale:
            return
        async with gate:
            state = await sdk().threads.get_state(thread['thread_id'], subgraphs=True)
        def collect(current):
            found = list(current.get('interrupts') or [])
            for task in current.get('tasks', []):
                found.extend(task.get('interrupts') or [])
                if isinstance(task.get('state'), dict):
                    found.extend(collect(task['state']))
            return found
        pending = collect(state)
        unique = {item.get('id') or str(item): item for item in pending}
        thread['interrupts'] = list(unique.values())
    try:
        await asyncio.gather(*(refresh(thread) for thread in threads))
    except httpx.HTTPError as exc:
        raise HTTPException(503, '当前待答问题暂无法同步，请重新连接后查看待办') from exc
    for row in rows:
        if not row.get('thread_id'):
            continue
        thread = lookup.get(row['thread_id'])
        if thread is None:
            row['thread_status'] = 'unavailable'
            if row.get('status') in ('queued', 'running', 'processing', 'awaiting_input'):
                row.update(status='recovery_required', summary='历史运行线程不可用，材料与结果已保留，请检查恢复条件')
            continue
        row['thread_status'] = thread['status']
        interrupts = thread.get('interrupts') or {}
        pending = [item for items in interrupts.values() for item in items] if isinstance(interrupts, dict) else interrupts
        questions = []
        for item in pending:
            value = item.get('value') or {}
            if isinstance(value, dict):
                question = (value.get('args') or {}).get('question') or value.get('description')
                if question:
                    questions.append(question)
        row['pending_questions'] = questions
        if pending or thread['status'] == 'interrupted':
            if row.get('control') not in ('paused', 'cancelled'):
                row['status'] = ('awaiting_review' if any((item.get('value') or {}).get('kind') == 'confidence_review'
                                 for item in pending if isinstance(item.get('value'), dict)) else 'awaiting_input')
        elif thread['status'] == 'error' and row.get('status') in ('queued', 'running', 'processing'):
            row['status'] = 'error'
        elif thread['status'] == 'idle' and row.get('status') in ('queued', 'running', 'processing'):
            row.update(status='incomplete', summary='本轮处理已结束，已保存现有结果；尚未完成自动核验')
    return rows


@router.get('/api/bills')
async def list_bills():
    return response(await live_status(await asyncio.to_thread(bill_rows)))


@router.get('/api/traces')
async def list_traces():
    rows = await asyncio.to_thread(repository().list_projection, 'task', TASK_FIELDS)
    rows = await live_status(rows)
    counts = await asyncio.to_thread(repository().event_counts, [row['id'] for row in rows])
    revised = 0
    confirmed = 0
    waiting = 0
    for row in rows:
        row['event_counts'] = counts.get(row['id'], {})
        revised += bool(row['event_counts'].get('human_revision'))
        confirmed += bool(row['event_counts'].get('approval'))
        waiting += row.get('status') == 'awaiting_input'
    total = len(rows)
    return response(dict(tasks=rows, sample_size=total, limit=100,
        human=dict(revised_tasks=revised, revision_ratio=revised / total if total else None,
                   confirmation_tasks=confirmed, waiting_input_tasks=waiting,
                   definition='人工干预比例 = 有 human_revision 审计事件的任务数 / 当前列出的任务数；常规确认另计。'),
        quality=dict(accuracy=None, false_positive_rate=None, false_negative_rate=None, labeled_samples=0,
                     status='not_evaluated', reason='当前生产任务未关联独立金标；置信度和人工修改率不作为识别准确率。')))


@router.get('/api/tasks/{task_id}/trace')
async def task_trace(task_id: str):
    task = await asyncio.to_thread(repository().get, 'task', task_id)
    events = await asyncio.to_thread(repository().events, task_id, 1001)
    state, state_error = {}, None
    if task.get('thread_id'):
        try:
            state = await sdk().threads.get_state(task['thread_id'], subgraphs=True)
        except httpx.HTTPError as exc:
            state_error = f'官方线程状态暂不可用：{type(exc).__name__}'
    path = call_path(state)
    counts = await asyncio.to_thread(repository().event_counts, [task_id])
    fields = ('id', 'event', 'at', 'tool', 'call_id', 'revision', 'status', 'elapsed_seconds', 'message', 'reason',
              'flush_seconds', 'flush_status', 'source_id', 'name', 'stage', 'receipt',
              'input_tokens', 'output_tokens', 'cache_read_tokens')
    event_rows = [{key: event[key] for key in fields if key in event} for event in events[:1000]]
    return response(dict(task_id=task_id, revision=task['revision'], usage=task.get('usage', {}),
        events=event_rows, events_truncated=len(events) > 1000, event_counts=counts.get(task_id, {}),
        call_path=path, state_error=state_error,
        path_scope='官方检查点当前可见的工具调用及子图；已完成专家内部调用可能不保留在父检查点，完整耗时回执另列。'))
