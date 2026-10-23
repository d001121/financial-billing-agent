"""Persistent chat and native interrupt replies on the existing thread."""
import asyncio
from uuid import UUID

from fastapi import APIRouter, Request

from backend.extensions.skill_versions import skill_module
from backend.harness.dispatch import check
from backend.infrastructure.repository import Conflict, loads, now, repository
from ..responses import response
from ..task_runtime import require_idle, sdk, start_run

router = APIRouter(tags=['conversation'])


@router.post('/api/tasks/{task_id}/review-conversation')
async def request_review_conversation(task_id: str, request: Request):
    """A user's explicit edit/review action opens a real native question."""
    body = loads(await request.body())
    task = await asyncio.to_thread(repository().get, 'task', task_id)
    if task['revision'] != body.get('expected_revision'):
        raise Conflict('账单已更新，请刷新后重新选择')
    await require_idle(task)
    await asyncio.to_thread(check, task_id, skill='human-review', policy_only=True)
    limits = task['capability']['config']['runtime']
    if any(task.get('usage', {}).get(k, 0) >= limits[k]
           for k in ('model_calls', 'tool_calls', 'active_seconds')):
        raise Conflict('当前任务预算已用尽，无法启动新的会话核对')
    state = await sdk().threads.get_state(task['thread_id'], subgraphs=True)
    if any(t.get('interrupts') for t in state.get('tasks', [])):
        return response(task)  # Focus the existing question, don't create another.
    charge_id = body.get('charge_id')
    if charge_id and not any(r['charge_id'] == charge_id for r in task.get('records', [])):
        raise Conflict('费用已不存在，请刷新后选择')
    action = body.get('action', 'edit')
    questions = {'entity': '请告诉我本次记账主体的正确名称。',
        'confirm': '请核对当前账单。您可以直接回复“确认无误”，也可以说明需要修改的内容。',
        'edit': '请告诉我需要修改的字段和正确内容。',
        'delete': '请确认要删除的费用，或说明需要怎样调整。',
        'split': '请说明这笔费用需要拆成哪几项，以及各项金额和币种。'}
    if action not in questions:
        raise ValueError('不支持的核对请求')
    question = questions[action]
    if charge_id:
        record = next(r for r in task['records'] if r['charge_id'] == charge_id)
        details = record.get('charge_details', {})
        question = f'费用 {charge_id}（{details.get("charge_item") or "未命名"}）：' + question
    from uuid import uuid4
    review = dict(id=str(uuid4()), revision=task['revision'], action=action, charge_id=charge_id,
                  field=body.get('field') or '', question=question, state='pending')
    if action == 'entity':
        build_question = getattr(skill_module('human-review', task['capability'].get('version')), 'entity_question', None)
        candidate = build_question(dict(task, accounting_entity=None, status='awaiting_review')) if build_question else None
        if candidate:
            review.update(question=candidate['question'], choices=candidate['choices'])
    existing = task.get('review_request') or {}
    if existing.get('state') == 'pending' and existing.get('revision') == task['revision']:
        review = existing  # Retry an unanswered request whose prior run never opened an interrupt.
    def reserve(current):
        existing = current.get('review_request') or {}
        if existing.get('state') == 'pending' and existing.get('id') != review['id']:
            raise Conflict('已有核对问题正在打开，请稍候刷新会话')
        current['review_request'] = review
        current['status'] = 'starting'
    task = await asyncio.to_thread(repository().mutate, 'task', task_id, reserve,
                                   expected_revision=task['revision'])
    try:
        return response(await start_run(task, message='调用方选择了账单核对，请在会话中询问具体意见。'))
    except Exception:
        def failed(current):
            if current.get('review_request', {}).get('id') == review['id']:
                current['review_request']['state'] = 'failed'
        await asyncio.to_thread(repository().mutate, 'task', task_id, failed,
                                expected_revision=task['revision'])
        raise


@router.post('/api/tasks/{task_id}/reply')
async def reply_to_agent(task_id: str, request: Request):
    body = loads(await request.body())
    text = body.get('text')
    if not isinstance(text, str) or not text.strip() or len(text) > 12000:
        raise ValueError('请输入回复，最多12000字')
    reply_id = str(UUID(body.get('reply_id', '')))
    task = await asyncio.to_thread(repository().get, 'task', task_id)
    if task.get('deleted_at'):
        raise KeyError('账单已从工作台删除')
    previous = next((r for r in task.get('conversation', []) if r['id'] == reply_id), None)
    if previous:
        if previous['text'] != text.strip() or previous['interrupt_id'] != (body.get('interrupt_id') or ''):
            raise Conflict('同一回复编号不能用于不同内容')
        if previous['state'] != 'failed':
            return response(task)  # Reload/double click never replays an accepted reply.
    if task['revision'] != body.get('expected_revision'):
        raise Conflict('账单版本已变化，请保留输入并刷新后回复当前问题')
    await require_idle(task)
    await asyncio.to_thread(check, task_id, skill='human-review', policy_only=True)
    limits = task['capability']['config']['runtime']
    if any(task.get('usage', {}).get(k, 0) >= limits[k]
           for k in ('model_calls', 'tool_calls', 'active_seconds')):
        raise Conflict('当前任务预算已用尽，回复尚未提交')
    state = await sdk().threads.get_state(task['thread_id'], subgraphs=True)
    pending = [i for t in state.get('tasks', []) for i in t.get('interrupts', [])]
    if not body.get('interrupt_id'):
        review = task.get('review_request') or {}
        if pending or state.get('next') or (review.get('state') == 'pending' and review.get('blocking') is not False):
            raise Conflict('有待处理的问题或尚未结束的步骤，请刷新会话后回复当前待办')
        reply = dict(id=reply_id, text=text.strip(), question='', interrupt_id='', kind='chat',
                     conversational=True, revision=task['revision'], state='starting',
                     model_seen=False, at=now())
        def reserve_chat(current):
            if any(r['state'] in ('starting', 'running', 'proposed')
                   for r in current.get('conversation', [])):
                raise Conflict('上一条消息仍在处理中，请稍候')
            current['conversation'] = [r for r in current.get('conversation', []) if r['id'] != reply_id] + [reply]
        task = await asyncio.to_thread(repository().mutate, 'task', task_id, reserve_chat,
                                       expected_revision=task['revision'])
        try:
            task = await start_run(task, message=text.strip(), message_id='chat-user-' + reply_id)
        except Exception:
            def failed_chat(current):
                for item in current.get('conversation', []):
                    if item['id'] == reply_id and item['state'] == 'starting':
                        item['state'] = 'failed'
            await asyncio.to_thread(repository().mutate, 'task', task_id, failed_chat,
                                    expected_revision=task['revision'])
            raise
        return response(task)
    entry = next((i for i in pending if i.get('id') == body.get('interrupt_id')), None)
    if not entry:
        raise Conflict('这个问题已处理或已变化，请刷新当前会话')
    payload = entry.get('value') or {}
    if not isinstance(payload, dict):
        raise ValueError('当前中断不支持对话回复，请由管理员检查中断定义')
    if payload.get('kind') in ('confidence_review', 'conversation_review'):
        answer = dict(expected_revision=task['revision'], message=text.strip(), reply_id=reply_id)
        question = payload.get('description') or '请核对有疑问的账单字段。'
    elif payload.get('name') == 'ask_user':
        answer = dict(type='respond', message=text.strip())
        question = payload.get('args', {}).get('question') or payload.get('description', '')
    elif payload.get('type') == 'tool_approval':
        # Text is feedback, never implicit permission to execute a gated action.
        answer = dict(type='reject', message='调用方反馈，请先理解再调整：' + text.strip())
        question = payload.get('description') or '请说明这项操作需要怎样调整。'
    else:
        raise ValueError('当前中断不支持对话回复，请由管理员检查中断定义')
    messages = state.get('values', {}).get('messages', [])
    anchor = ('review-question-' + payload['request_id'] if payload.get('kind') == 'conversation_review'
              else messages[-1].get('id') if messages and isinstance(messages[-1], dict) else None)
    reply = dict(id=reply_id, text=text.strip(), question=question, interrupt_id=entry['id'],
        review_context=task.get('review_request') or {},
        conversational=body.get('conversational') is True,
        question_choices=payload.get('choices') or payload.get('args', {}).get('choices') or [],
        kind=payload.get('kind') or payload.get('name'),
        tool_call_id=payload.get('tool_call_id'), anchor_message_id=anchor,
        revision=task['revision'], state='starting', model_seen=False, at=now())
    def reserve(current):
        active = []
        for item in current.get('conversation', []):
            if item['state'] not in ('starting', 'running', 'proposed') or item['id'] == reply_id:
                continue
            # A native resume can finish with a *new* interrupt in the same
            # run.  The prior reply has then been consumed even if the
            # middleware has not written its final state before the next page
            # refresh.  Retain it in the transcript, but do not let it block
            # the new interrupt.
            if item.get('interrupt_id') != entry['id'] and (
                    item.get('model_seen') or current.get('run_status') in ('success', 'interrupted')):
                item.update(state='completed', completed_at=item.get('completed_at') or now())
                continue
            active.append(item)
        if active:
            raise Conflict('上一条回复仍在处理中，请稍候')
        current['conversation'] = [r for r in current.get('conversation', []) if r['id'] != reply_id] + [reply]
    task = await asyncio.to_thread(repository().mutate, 'task', task_id, reserve,
                                   expected_revision=task['revision'])
    try:
        task = await start_run(task, command={'resume': {entry['id']: answer}})
    except Exception:
        def failed(current):
            for item in current.get('conversation', []):
                if item['id'] == reply_id and item['state'] == 'starting':
                    item['state'] = 'failed'
        await asyncio.to_thread(repository().mutate, 'task', task_id, failed,
                                expected_revision=task['revision'])
        raise
    return response(task)
