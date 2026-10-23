"""Persist Skill review decisions and expose native resumable confidence forms.

LangChain Docs MCP: /oss/python/langgraph/interrupts (tools, replay/idempotency).
Reference MCP: langgraph.types.interrupt; langchain 1.4.6/langgraph 1.2.16.
Business scoring and approval binding remain in the pinned portable Skills.
"""
import asyncio

from langgraph.types import interrupt

from backend.extensions.skill_versions import function
from backend.infrastructure.repository import Conflict, now, repository
from .artifacts import save_fields, validate_and_store


def settle_saved(task_id, *, confirmation=None):
    """Use fresh checks; automatic verification never pretends to be human approval."""
    task = repository().get('task', task_id)
    if task.get('charges') and not task.get('records'):
        # Saved candidates must reach the bill even when the model ended without
        # an explicit reconcile call. Recording them does not approve anything.
        from .artifacts import reconcile_saved
        reconcile_saved(task_id)
        task = repository().get('task', task_id)
    validation = validate_and_store(task_id, task=task)
    task = repository().get('task', task_id)
    if task['revision'] != validation['revision']:
        raise Conflict('核验过程中版本已变化，请重试当前版本')
    from backend.api.schemas import export_binding
    cap = task['capability']
    confidence = validation.get('confidence') or {}
    result = function(cap, 'billing-export', 'build_export')(task)
    if 'review_required' not in confidence:
        return save_fields(task_id, task['revision'], export=result,
            status='awaiting_review' if not validation['ok'] else 'ready_for_review')
    if confirmation is not None:
        if not isinstance(confirmation, dict):
            raise ValueError('请提供当前版本的核对结果')
        if confirmation.get('expected_revision') != task['revision']:
            raise Conflict('复核版本已变化，请保留输入并查看最新结果')
    values = function(cap, 'human-review', 'review_outcome')(dict(task=task, export=result,
        binding=export_binding(task), confirmation=confirmation, at=now()))
    return save_fields(task_id, task['revision'], **values)


async def finalize_with_review(task_id):
    """A saved pending form always reaches the same interrupt on replay."""
    task = await asyncio.to_thread(repository().get, 'task', task_id)
    if any(r.get('revision') == task['revision'] and r.get('state') in ('starting', 'running', 'proposed')
           and r.get('model_seen') for r in task.get('conversation', [])):
        # A reply may have staged a correction that commits after this native
        # loop. Do not ask the same question against its unmodified old records.
        return await asyncio.to_thread(settle_saved, task_id)
    if task.get('capability', {}).get('config', {}).get('runtime', {}).get('agent_style') == 'codex':
        # Like a Codex answer: publish the actual result and explicit gaps now.
        # The user may inspect/edit it; a score does not block the native run.
        return await asyncio.to_thread(settle_saved, task_id)
    pending = task.get('confidence_interrupt')
    if not pending:
        task = await asyncio.to_thread(settle_saved, task_id)
        confidence = (task.get('validation') or {}).get('confidence') or {}
        if task['status'] != 'awaiting_review' or not confidence.get('review_required'):
            return task
        pending = dict(kind='confidence_review', revision=task['revision'],
            threshold=confidence['policy']['review_threshold'], items=confidence['review_items'],
            description='仅以下已有值低于置信度阈值，请对照原文核对；可在费用表直接修改后继续。')
        task = await asyncio.to_thread(save_fields, task_id, task['revision'], confidence_interrupt=pending)
    while True:
        answer = interrupt(pending)
        current = await asyncio.to_thread(repository().get, 'task', task_id)
        if isinstance(answer, dict) and isinstance(answer.get('message'), str):
            # Natural-language feedback must reach the model; it is never a
            # deterministic confirmation. ConversationReplies routes native END
            # back to model when the historical tool was return_direct.
            reply = next((r for r in current.get('conversation', [])
                          if r['id'] == answer.get('reply_id') and r['revision'] == current['revision']), None)
            if reply and answer.get('expected_revision') == current['revision']:
                return await asyncio.to_thread(save_fields, task_id, current['revision'], confidence_interrupt=None)
        if not isinstance(answer, dict) or answer.get('expected_revision') != current['revision']:
            pending = dict(pending, revision=current['revision'],
                description='核对期间账单已更新，您的输入已保留，请对照当前版本后继续。')
            continue
        try:
            task = await asyncio.to_thread(settle_saved, task_id, confirmation=answer)
        except Conflict:
            # Consume the stale native answer before exposing the next form.
            pending = dict(pending, description='提交期间账单又有更新，请核对当前版本后继续。')
            continue
        break
    # Clear only after the native answer has been consumed and persisted.
    task = await asyncio.to_thread(save_fields, task_id, task['revision'], confidence_interrupt=None)
    await asyncio.to_thread(repository().event, task_id, 'confidence_review',
                           revision=task['revision'], decision=answer['decision'])
    return task
