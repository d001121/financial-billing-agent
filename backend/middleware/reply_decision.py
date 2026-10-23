"""One bounded structured decision for a free-text human reply.

Separate from the HITL/resume middleware: this class owns only the model intent
call and the proposal staging.  The model uses the official
`with_structured_output` API; the host validates and applies via human-review.

Two host-side guards keep a weak classifier from stalling a review:
* the exact sentence the UI writes when a candidate company is clicked is
  applied deterministically (no model call), and
* field entries the caller never mentioned -- notably ``value=None`` inferred
  by the model -- are dropped instead of clearing data or failing on a null
  charge id.
"""

import asyncio
import re

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import AIMessage

from .conversation import active_reply, mark_reply_seen, reply_context, reply_task_context

ENTITY_TEMPLATE = re.compile(r'^\s*(?:本次)?记账主体是\s*(.+?)\s*[。.!！]?\s*$')
ABSENCE = re.compile(r'没有|无|不存在|未填写|未提供|留空|清空|不适用')
DEFER = re.compile(r'暂缓|跳过|不需要|先不指定|不指定')
# "本次记账主体是A是收款方" or "…，金额50" carry more than an entity; the
# model must interpret them, because the extra part is a second instruction.
ROLE = re.compile(r'收款方|付款方|收款|付款|\bTAR\b|\bSHA\b', re.IGNORECASE)
OTHER_FIELD = re.compile(r'金额|币种|付款方式|单据编号|单据日期|费用|数量|单价|，|,|；|;')

# A bare role answer to the AR/AP question has exactly one meaning. Mapping it
# deterministically avoids handing an already-answered question back to a small
# model that may return no fields and reopen the identical question.
ROLE_ONLY = re.compile(
    r'^\s*(?:本次|当前|本)?(?:记账主体|主体|本公司|我们公司|公司|我)?\s*'
    r'(?:是|作为|为)?\s*(?P<role>收款方|收款人|应收方|债权人|付款方|付款人|应付方|债务人|AR|AP)'
    r'\s*[。.!！]?\s*$', re.IGNORECASE)
ROLE_VALUES = {
    '收款方': 'AR', '收款人': 'AR', '应收方': 'AR', '债权人': 'AR',
    '付款方': 'AP', '付款人': 'AP', '应付方': 'AP', '债务人': 'AP',
}


def role_from_reply(text):
    """Return AR/AP only for a reply that states nothing but the role."""
    match = ROLE_ONLY.match(text or '')
    if not match:
        return None
    raw = match.group('role')
    return raw.upper() if raw.upper() in ('AR', 'AP') else ROLE_VALUES.get(raw)


def role_operations(task, role, entity):
    """Bind the stated role to the entity's side of every affected charge."""
    records = [r for r in task.get('records') or [] if r.get('charge_id')]
    if not records or not entity:
        return None
    target = (task.get('review_request') or {}).get('charge_id')
    rows = [r for r in records if not target or r.get('charge_id') == target]
    if not rows:
        return None
    field = 'creditor' if role == 'AR' else 'debtor'
    operations = []
    for row in rows:
        operations.append(dict(op='set', charge_id=row['charge_id'], field=field, value=entity))
        operations.append(dict(op='set', charge_id=row['charge_id'], field='posting_type', value=role))
    return operations


def entity_from_reply(task, reply):
    """Return the company named by a pure entity sentence or a choice."""
    text = (reply.get('text') or '').strip()
    match = ENTITY_TEMPLATE.match(text)
    candidate = match.group(1).strip() if match else text.rstrip('。.!！')
    if (not candidate or DEFER.search(candidate) or ABSENCE.search(candidate)
            or ROLE.search(candidate) or OTHER_FIELD.search(candidate)):
        return None
    if match:
        return candidate
    choices = (task.get('review_request') or {}).get('choices') or []
    return candidate if candidate in choices else None


class ReplyDecisionMiddleware(AgentMiddleware):
    def __init__(self, task_id, revision, cap, record_tool):
        self.task_id, self.revision, self.cap = task_id, revision, cap
        self.record_tool = record_tool

    async def structured_decision(self, request, task, reply):
        model = getattr(request, 'model', None)
        if model is None or not hasattr(model, 'with_structured_output'):
            return None
        from .decision import ReplyDecision, decision_messages
        try:
            result = await model.with_structured_output(ReplyDecision).ainvoke(
                decision_messages(task, reply))
        except Exception:
            return None
        if isinstance(result, ReplyDecision):
            return result
        try:
            return ReplyDecision.model_validate(result)
        except Exception:
            return None

    async def apply(self, reply, *, operations=None, entity=None, resolves_pending=False):
        payload = dict(reply_id=reply['id'], action='edit', operations=operations or None,
                       set_accounting_entity=entity is not None, accounting_entity=entity,
                       resolves_pending=resolves_pending)
        outcome = await asyncio.to_thread(self.record_tool.invoke, payload)
        await mark_reply_seen(self.task_id, self.revision, reply['id'])
        proposed = isinstance(outcome, dict) and outcome.get('proposed')
        text = ('已按您的回复应用修改。' if proposed else '本轮回复未能自动应用：' + str(outcome))
        return AIMessage(content=text)

    async def awrap_model_call(self, request, handler):
        if not self.task_id:
            return await handler(request)
        task = await asyncio.to_thread(reply_context, self.task_id)
        reply = active_reply(task)
        if not reply:
            return await handler(request)
        full = await asyncio.to_thread(reply_task_context, self.task_id)
        if reply.get('kind') == 'chat':
            full['review_request'] = {}  # A previous review's selected charge is not this chat's scope.
        # Clicking a candidate (or typing the same sentence) is an exact,
        # reversible entity edit; do not depend on a small model to label it.
        entity = entity_from_reply(full, reply)
        if entity:
            if not (full.get('records') or full.get('charges')):
                # Nothing saved yet: the Skill loop must materialize candidates
                # before an entity edit has a target.
                return await handler(request)
            review = full.get('review_request') or {}
            resolves = review.get('field') == 'accounting_entity' or review.get('action') == 'entity'
            return await self.apply(reply, entity=entity, resolves_pending=resolves)
        role = role_from_reply(reply.get('text'))
        if role and reply.get('kind') != 'chat':
            operations = role_operations(full, role, full.get('accounting_entity'))
            if operations:
                review = full.get('review_request') or {}
                return await self.apply(reply, operations=operations,
                                        resolves_pending=review.get('field') == 'posting_type')
        if reply.get('conversational'):
            # Answer questions in the native conversation instead of paying for
            # a classifier which can only return "已记录本轮回复".
            return await handler(request)
        try:
            decision = await self.structured_decision(request, full, reply)
        except Exception:
            decision = None
        if decision is None:
            return await handler(request)
        absence = bool(ABSENCE.search(reply.get('text') or ''))
        target = (full.get('review_request') or {}).get('charge_id')
        records = full.get('records') or []
        operations = []
        for item in decision.fields:
            # A null the caller did not assert is the model "filling gaps",
            # not an instruction to clear a field.
            if item.value is None and not absence:
                continue
            operation = dict(op='set', field=item.field, value=item.value)
            if target:
                operation['charge_id'] = target
            elif len(records) == 1 and records[0].get('charge_id'):
                operation['charge_id'] = records[0]['charge_id']
            operations.append(operation)
        has_entity = decision.accounting_entity is not None
        if (operations or has_entity) and not (records or full.get('charges')):
            # Same reason as above: no saved candidate to edit yet.
            return await handler(request)
        if not operations and not has_entity:
            if decision.action in ('apply', 'ask'):
                # Nothing the host can apply: let the Skill loop save candidates
                # or ask the caller the model's follow-up question.
                return await handler(request)
            payload = dict(reply_id=reply['id'], action=decision.action, operations=None,
                           set_accounting_entity=False, accounting_entity=None)
            outcome = await asyncio.to_thread(self.record_tool.invoke, payload)
            await mark_reply_seen(self.task_id, self.revision, reply['id'])
            proposed = isinstance(outcome, dict) and outcome.get('proposed')
            text = ('已记录本轮回复。' if proposed else '本轮回复未能自动应用：' + str(outcome))
            return AIMessage(content=text)
        # The payload itself is an edit; the model's action label is not
        # authoritative once there is an entity or a concrete field value.
        return await self.apply(reply, operations=operations, entity=decision.accounting_entity)
