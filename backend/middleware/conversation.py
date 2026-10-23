"""Native middleware/tools: interpret a real reply, commit through the pinned Skill.

Docs MCP custom middleware: tools, ModelRequest.override, after_agent state updates
and hook_config(can_jump_to=['model']). LangChain 1.4.6/LangGraph 1.2.16.
The framework owns interruption and execution. Business edits use apply_revision;
only transport provenance and the pending proposal live in this adapter.
"""
import asyncio
import re
from typing import Literal

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain.messages import AIMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langchain_core.tools import ToolException
from langgraph.types import interrupt

from backend.extensions.skill_versions import function
from backend.harness.dispatch import check
from backend.harness.stopping import active_stop
from backend.hooks.completion import completion_question
from backend.infrastructure.repository import Conflict, dumps, now, repository
from backend.tools.artifacts import reconcile_saved
from backend.tools.review import settle_saved

CHAT_TOOLS = {'read_task_context', 'read_document_sources', 'read_markdown_evidence',
              'read_file', 'ls', 'glob', 'grep', 'record_review_decision', 'ask_user'}


def active_reply(task):
    return next((r for r in reversed(task.get('conversation') or [])
                 if r['state'] in ('starting', 'running', 'proposed')
                 and r['revision'] == task['revision']), None)


def reply_by_id(task, reply_id):
    """Return a reply row even after it has been consumed by the harness."""
    return next((r for r in reversed(task.get('conversation') or [])
                 if r.get('id') == reply_id), None)


def reply_context(task_id):
    repo = repository()
    return (repo.get_fields('task', task_id, ['conversation', 'review_request', 'automatic_stop'])
            if hasattr(repo, 'get_fields') else repo.get('task', task_id))


def reply_task_context(task_id):
    repo = repository()
    fields = ['conversation', 'review_request', 'records', 'charges',
              'accounting_entity', 'status']
    return (repo.get_fields('task', task_id, fields)
            if hasattr(repo, 'get_fields') else repo.get('task', task_id))


async def mark_reply_seen(task_id, revision, reply_id):
    def seen(current):
        item = active_reply(current)
        if item and item['id'] == reply_id:
            item['model_seen'] = True
    repo = repository()
    if hasattr(repo, 'mutate_fields'):
        await asyncio.to_thread(repo.mutate_fields, 'task', task_id, ['conversation'], seen,
                                expected_revision=revision)
    else:
        await asyncio.to_thread(repo.mutate, 'task', task_id, seen, expected_revision=revision)


def _role_is_explicit(text: str) -> bool:
    """Return whether the caller actually stated a payment relationship."""
    value = (text or '').lower()
    return bool(re.search(r'收款|付款|付费|应收|应付|ar\b|ap\b|pay(?:er|ment)?|paid|payer|creditor|debtor', value))


def _normalise_review_operations(task, operations, text):
    """Bind model-produced edits to the current revision without guessing.

    A single current charge can safely absorb a stale id from a previous
    revision.  When several charges exist, an unknown id is rejected instead
    of allowing the model to keep guessing.  Relationship fields are ignored
    unless the caller explicitly mentioned a payment relationship; selecting
    an accounting entity alone must never invent creditor/debtor changes.
    """
    current_ids = [r.get('charge_id') for r in task.get('records') or [] if r.get('charge_id')]
    if not current_ids:
        current_ids = [c.get('charge_id') for c in task.get('charges', []) if c.get('charge_id')]
    explicit_role = _role_is_explicit(text)
    normalized = []
    ignored = []
    for operation in operations or []:
        item = dict(operation)
        field = item.get('field')
        if field in {'creditor', 'debtor', 'posting_type'} and not explicit_role:
            ignored.append(field)
            continue
        charge_id = item.get('charge_id')
        if not charge_id:
            if len(current_ids) == 1:
                item['charge_id'] = current_ids[0]
            else:
                raise ToolException('请指定要修改的费用；可用费用：' + ', '.join(current_ids))
        elif charge_id not in current_ids:
            if len(current_ids) == 1:
                item['charge_id'] = current_ids[0]
            else:
                raise ToolException('当前修订引用了旧费用编号；可用费用：' + ', '.join(current_ids))
        normalized.append(item)
    return normalized, ignored


class ConversationReplies(AgentMiddleware):
    def __init__(self, task_id, revision, cap):
        self.task_id, self.revision, self.cap = task_id, revision, cap

        @tool
        def record_review_decision(reply_id: str, action: Literal['answer', 'edit', 'confirm', 'defer'],
                operations: list[dict] | None = None, set_accounting_entity: bool = False,
                accounting_entity: str | None = None, resolves_pending: bool = False) -> dict:
            """理解调用方本轮真实回复后记录处理意见。修改用现有charge_id和set/delete/split操作；
            主体变更须set_accounting_entity=true。confirm只用于明确确认当前结果，修改不是确认。
            仅生成待提交修订，本轮结束时由human-review Skill事务应用、重算和校验。
            resolves_pending仅在本条回复确实解决当前待答问题时为true；无关聊天或改其他字段保持false。
            """
            # Read first so replaying a call after the revision was committed
            # can be answered idempotently instead of becoming a new model turn.
            task = repository().get('task', task_id)
            reply = active_reply(task)
            historical = reply_by_id(task, reply_id)
            # A model can replay a tool call after a native resume.  Once the
            # proposal was staged (or the reply was consumed), return the
            # original receipt instead of applying the Skill a second time.
            if historical and historical.get('proposal'):
                return dict(proposed=True, idempotent=True,
                            action=historical['proposal'].get('action'),
                            proposal=historical['proposal'],
                            instruction='该回复已生成提案；不要再次调用修订或提取工具。')
            if historical and historical.get('state') == 'completed':
                return dict(proposed=True, idempotent=True,
                            action=(historical.get('proposal') or {}).get('action', action),
                            applied_revision=historical.get('applied_revision'),
                            instruction='该回复已应用；不要重复提交，直接结束本轮。')
            if historical and historical.get('decision_error'):
                return dict(proposed=False, idempotent=True, retryable=False,
                            error=historical['decision_error'],
                            instruction='该回复已被拒绝；不要重复猜测参数，请等待调用方补充新的明确回复。')

            def reject(message, retryable=False):
                def remember(current):
                    item = reply_by_id(current, reply_id)
                    if item and not item.get('proposal'):
                        # Allow one corrected retry (for example after a stale
                        # charge id); any second failure is terminal.
                        if retryable and item.get('retry_count', 0) < 1:
                            item['retry_count'] = item.get('retry_count', 0) + 1
                            item['last_error'] = message
                        else:
                            item['decision_error'] = message
                        item['state'] = 'proposed'
                try:
                    repository().mutate('task', task_id, remember,
                                        expected_revision=task.get('revision'))
                except Exception:
                    pass
                raise ToolException(message)

            task = check(task_id, revision=revision, skill='human-review')
            if not reply or reply['id'] != reply_id:
                return reject('没有对应的真实待处理用户回复')
            edits = operations or []
            if action != 'edit' and (edits or set_accounting_entity):
                # The payload itself expresses an edit; the model's label is
                # not authoritative.  Applying it as an edit keeps the rule
                # "a modification is not a confirmation" without failing the
                # whole human turn over a mislabelled action.
                action = 'edit'
            if action == 'edit' and not (task.get('records') or []) and task.get('charges'):
                # A human answer can arrive before the first finalize (ask_user
                # during intake). Materialize records from the already saved
                # candidates so the edit has a stable target instead of
                # failing every retry with CHARGE_NOT_FOUND.
                try:
                    reconcile_saved(task_id)
                except Exception as exc:
                    return reject(f'候选费用尚未形成可修改记录：{exc}')
                task = check(task_id, revision=revision, skill='human-review')
            if action == 'edit' and not (task.get('records') or []):
                return reject('当前还没有可修改的账单记录；请先保存候选费用，再提交修改', retryable=True)
            current_ids = [r.get('charge_id') for r in task.get('records') or [] if r.get('charge_id')]
            if not current_ids:
                current_ids = [c.get('charge_id') for c in task.get('charges', []) if c.get('charge_id')]
            if len(current_ids) == 1:
                edits = [dict(item, charge_id=item.get('charge_id') or current_ids[0]) for item in edits]
            try:
                edits, ignored = _normalise_review_operations(task, edits, reply['text'])
            except ToolException as exc:
                return reject(str(exc), retryable=True)
            if action == 'edit' and not edits and not set_accounting_entity:
                if ignored:
                    return reject('本轮只选择了记账主体，未明确收付款关系；请说明主体是收款方还是付款方后再修改AR/AP。')
                return reject('请明确用户实际要求修改的字段')
            proposal = dict(action=action, operations=edits, resolves_pending=resolves_pending)
            if ignored:
                proposal['ignored_fields'] = ignored
            if action == 'edit':
                payload = dict(task, expected_revision=revision, operations=edits, reason=reply['text'])
                if set_accounting_entity:
                    payload['accounting_entity'] = accounting_entity
                    proposal['accounting_entity'] = accounting_entity
                result = function(cap, 'human-review', 'apply_revision')(payload)
                if not result['valid']:
                    codes = {issue.get('code') for issue in result['issues']}
                    message = dumps(result['issues'])
                    if codes == {'CHARGE_NOT_FOUND'}:
                        valid = [r.get('charge_id') for r in task.get('records') or [] if r.get('charge_id')]
                        message += '；当前可用费用：' + ', '.join(valid)
                        return reject(message, retryable=True)
                    return reject(message)
            def propose(current):
                latest = active_reply(current)
                if not latest or latest['id'] != reply_id:
                    raise Conflict('回复已被另一轮处理，请读取当前任务')
                latest.update(proposal=proposal, state='proposed')
            repository().mutate('task', task_id, propose, expected_revision=revision)
            return dict(proposed=True, action=action, proposal=proposal,
                        current_revision=revision,
                        instruction='提案已记录；结束本轮时实际提交，无需重新OCR或读取材料。修改不等于批准导出。')

        record_review_decision.handle_tool_error = True
        self.tools = [record_review_decision]
        self.record_tool = record_review_decision

    async def abefore_agent(self, state, runtime):
        if not self.task_id:
            return
        task = await asyncio.to_thread(reply_context, self.task_id)
        review = task.get('review_request') or {}
        if review.get('state') != 'pending' or review.get('revision') != self.revision:
            return
        return await self.await_review(review)

    async def flush(self):
        repo = repository()
        if hasattr(repo, 'flush'):
            await asyncio.to_thread(repo.flush, self.task_id)

    async def await_review(self, review):
        answer = interrupt(dict(kind='conversation_review', request_id=review['id'],
                                description=review['question'], choices=review.get('choices', []),
                                revision=review['revision']))
        current = await asyncio.to_thread(reply_context, self.task_id)
        reply = active_reply(current)
        if (not isinstance(answer, dict) or not reply or answer.get('reply_id') != reply['id']
                or answer.get('expected_revision') != current['revision']):
            raise ValueError('请通过当前会话提交真实回复')
        def answered(saved):
            if saved.get('review_request', {}).get('id') == review['id']:
                saved['review_request']['state'] = 'answered'
        await asyncio.to_thread(repository().mutate, 'task', self.task_id, answered,
                                expected_revision=current['revision'])
        await self.flush()
        return {'messages': [AIMessage(content=review['question'], id='review-question-' + review['id'])]}

    async def clarify_completion(self, task=None):
        task = task or await asyncio.to_thread(repository().get, 'task', self.task_id)
        question = completion_question(task)
        if not question or task.get('control') != 'running':
            return
        from uuid import uuid4
        review = dict(question, id=str(uuid4()), revision=task['revision'], state='pending')
        def reserve(current):
            existing = current.get('review_request') or {}
            if existing.get('state') == 'pending' and existing.get('revision') == current['revision']:
                return
            current.update(review_request=review, status='awaiting_input', auto_review=None,
                           summary=question.get('summary') or 'AR/AP需要补充本主体的收付款关系，已保存的提取结果保持可见。')
        saved = await asyncio.to_thread(repository().mutate, 'task', self.task_id, reserve,
                                        expected_revision=task['revision'])
        await self.flush()
        update = await self.await_review(saved['review_request'])
        return dict(update, jump_to='model')

    async def keep_question(self, reply, revision):
        """Keep an unanswered question in the native checkpoint after another turn."""
        from uuid import uuid4
        review = dict(id=str(uuid4()), revision=revision, source='completion',
                      action='edit', state='pending', question=reply['question'],
                      choices=reply.get('question_choices') or [])
        def keep_pending(current):
            current.update(review_request=review, status='awaiting_input')
        await asyncio.to_thread(repository().mutate, 'task', self.task_id, keep_pending,
                                expected_revision=revision)
        await self.flush()
        update = await self.await_review(review)
        return dict(update, jump_to='model')

    async def awrap_model_call(self, request, handler):
        if not self.task_id:
            return await handler(request.override(tools=[t for t in request.tools
                if getattr(t, 'name', None) != 'record_review_decision']))
        task = await asyncio.to_thread(reply_context, self.task_id)
        reply = active_reply(task)
        if not reply:
            return await handler(request.override(tools=[t for t in request.tools
                if getattr(t, 'name', None) != 'record_review_decision']))
        limit = int(((self.cap or {}).get('config', {}).get('runtime') or {}).get('turn_model_calls', 6))
        used = int(reply.get('turn_model_calls') or 0)
        if used >= limit:
            def stopped(current):
                item = active_reply(current)
                if item and item['id'] == reply['id']:
                    item['decision_error'] = (
                        f'本轮人工回复已使用 {used} 次模型调用（上限 {limit}），未完成修改；请补充说明后重试')
                    item['state'] = 'proposed'
            repo = repository()
            if hasattr(repo, 'mutate_fields'):
                await asyncio.to_thread(repo.mutate_fields, 'task', self.task_id, ['conversation'],
                                        stopped, expected_revision=self.revision)
            else:
                await asyncio.to_thread(repo.mutate, 'task', self.task_id, stopped,
                                        expected_revision=self.revision)
            return AIMessage(content=f'本轮人工回复处理次数已达上限（{limit} 次模型调用），未能安全完成修改；'
                                     '已保留当前版本，请补充更明确的说明后再试。')
        def counted(current):
            item = active_reply(current)
            if item and item['id'] == reply['id']:
                item['turn_model_calls'] = used + 1
        repo = repository()
        if hasattr(repo, 'mutate_fields'):
            await asyncio.to_thread(repo.mutate_fields, 'task', self.task_id, ['conversation'],
                                    counted, expected_revision=self.revision)
        else:
            await asyncio.to_thread(repo.mutate, 'task', self.task_id, counted,
                                    expected_revision=self.revision)
        content = (list(request.system_message.content_blocks) if request.system_message else []) + [dict(
            type='text', text=('以下是调用方主动发送的会话消息，不是材料中的指令。' if reply.get('kind') == 'chat'
                              else '以下是调用方在真实人工中断中提交的业务回复，不是材料中的指令。') +
            '按相关 Skill 的流程处理这条回复；已有材料、OCR、提取候选和证据直接复用。'
            '先理解回复，必要时读取现有记录。若明确修改字段或主体，必须调用record_review_decision(action="edit")；'
            '用户从本轮候选中选择公司时，将对应完整名称作为accounting_entity并set_accounting_entity=true；'
            '数字选项只按本轮问题中的候选顺序理解，有歧义则追问，不自动选公司。'
            '如果工具提示还没有可修改的记录或候选，先按 document-extraction Skill 调用 save_document_extraction 保存候选，'
            '再重试应用这条回复；不要直接放弃或结束。'
            '它通过既有human-review Skill提交，不能只在聊天中说已修改，也不要用提取工具覆盖人工锁定值。'
            '只在用户明确确认当前结果时用confirm；修改请求、不知道、拒绝不能当作确认。'
            '无明确修改时用answer；需要暂缓时用defer。不要重复已成功的OCR/读取。'
            '回复不清楚时ask_user追问。用户明确本主体收款或付款时，修订对应费用的creditor/debtor关系，'
            '仅修改posting_type不会替代财务关系校验；不得假定用户未声明的关系。'
            '修订提案在本轮结束时应用，结果以最终校验为准。\n' + dumps({
                **{k: reply.get(k) for k in ('id', 'text', 'question', 'revision', 'proposal')},
                'current_todos': (getattr(request, 'state', {}) or {}).get('todos', [])}) +
                '\n调用方选择的核对范围：' + dumps(task.get('review_request') or {}))]
        available = list(request.tools)
        if reply.get('conversational'):
            content.append({'type': 'text', 'text':
                '这是常驻聊天框中的真实用户消息。普通问题直接友好回答，不要仅说已记录，不必调用意见工具。'
                '只有明确要求修改字段/主体、确认或暂缓时，才调用record_review_decision。'
                '只有本条回复解决了当前待答问题，才设置resolves_pending=true；无关字段修改不消除原待办。'
                '有待办不代表用户每句话都在确认它；不要把聊天当作批准或宣称待办已完成。'})
        if reply.get('kind') == 'chat':
            content.append({'type': 'text', 'text':
                '当前是既有账单的新聊天回合，不重新执行提取、OCR或发布。'
                '修订只针对用户明确指定的当前费用；此前核对范围不适用于本条消息。'})
            available = [t for t in available if getattr(t, 'name', None) in CHAT_TOOLS]
        if reply.get('proposal') or reply.get('decision_error'):
            # A staged decision is the terminal boundary for this human turn;
            # keep the model from re-running side effects afterwards.
            available = []
            content.append({'type': 'text', 'text': '本轮人工回复已有处理结果；请直接说明结果并结束，不要调用任何工具。'})
        result = await handler(request.override(system_message=SystemMessage(content=content),
                                               tools=available))
        def observed(current):
            item = active_reply(current)
            if item and item['id'] == reply['id']:
                item['model_seen'] = True
        repo = repository()
        if hasattr(repo, 'mutate_fields'):
            await asyncio.to_thread(repo.mutate_fields, 'task', self.task_id, ['conversation'], observed,
                                    expected_revision=self.revision)
        else:
            await asyncio.to_thread(repo.mutate, 'task', self.task_id, observed,
                                    expected_revision=self.revision)
        return result

    async def awrap_tool_call(self, request, handler):
        """Block only the post-decision terminal boundary at dispatch.

        Business ordering is owned by the Skills.  An active human reply
        without a staged decision may use any Skill tool, so the Agent can
        recover from an error (for example save candidates before retrying an
        edit) instead of being trapped by a host allowlist.
        """
        if not self.task_id:
            return await handler(request)
        task = await asyncio.to_thread(reply_context, self.task_id)
        reply = active_reply(task)
        if reply and reply.get('kind') == 'chat' and request.tool_call.get('name') not in CHAT_TOOLS:
            return ToolMessage(content='本轮是既有账单聊天；请使用只读工具或record_review_decision处理明确修改。',
                               tool_call_id=request.tool_call.get('id'), name=request.tool_call.get('name'), status='error')
        if reply and (reply.get('proposal') or reply.get('decision_error')):
            name = request.tool_call.get('name')
            return ToolMessage(
                content='本轮人工回复已记录处理结果；请直接用文字说明结果并结束，不要调用工具。',
                tool_call_id=request.tool_call.get('id'), name=name, status='error')
        return await handler(request)

    @hook_config(can_jump_to=['model', 'end'])
    async def aafter_agent(self, state, runtime):
        if not self.task_id:
            return
        task = await asyncio.to_thread(reply_context, self.task_id)
        review = task.get('review_request') or {}
        if active_stop(task):
            # after_agent hooks execute in reverse order: settle first here,
            # so completion can open the real todo before TaskOutcome runs.
            full = await asyncio.to_thread(repository().get, 'task', self.task_id)
            if full.get('charges'):
                await asyncio.to_thread(reconcile_saved, self.task_id)
            full = await asyncio.to_thread(settle_saved, self.task_id)
            return await self.clarify_completion(full)
        if (review.get('state') == 'pending' and review.get('source') == 'completion'
                and review.get('revision') == task['revision']):
            update = await self.await_review(review)
            return dict(update, jump_to='model')
        reply = active_reply(task)
        if not reply or task['revision'] != self.revision:
            return await self.clarify_completion()
        if reply.get('decision_error'):
            def failed(current):
                item = active_reply(current)
                if item and item['id'] == reply['id']:
                    item.update(state='failed', completed_at=now())
                if current.get('status') in ('queued', 'processing', 'running',
                                             'awaiting_review', 'awaiting_input', 'starting'):
                    current['status'] = 'incomplete'
                current['summary'] = '本轮人工回复未能安全应用：' + reply['decision_error']
            await asyncio.to_thread(repository().mutate, 'task', self.task_id, failed,
                                    expected_revision=self.revision)
            await self.flush()
            # No jump_to: 'end' means the first after_agent hook, which is this
            # node itself, so returning it here recursed to the 512 limit.
            return {'messages': [AIMessage(content='本轮回复未能安全应用：' + reply['decision_error'] + '请补充明确字段后再继续。',
                                           id='reply-error-' + reply['id'])]}
        if not reply.get('model_seen'):
            # A historical confidence tool may be return_direct. Native routing
            # gives its free-text response to the model, rather than approving it.
            return {'jump_to': 'model'}
        if reply.get('last_error') and not reply.get('proposal'):
            return dict(jump_to='model', messages=[AIMessage(
                content='本轮修改提案尚未应用：' + reply['last_error'] +
                        '。请使用当前费用ID纠正一次；无法明确目标则追问，不要把回复标为完成。',
                id='reply-retry-' + reply['id'])])
        proposal = reply.get('proposal') or {'action': 'answer'}
        if proposal['action'] == 'edit':
            task = await asyncio.to_thread(repository().get, 'task', self.task_id)
            payload = dict(task, expected_revision=self.revision, reason=reply['text'],
                           operations=proposal['operations'])
            if 'accounting_entity' in proposal:
                payload['accounting_entity'] = proposal['accounting_entity']
            result = await asyncio.to_thread(function(self.cap, 'human-review', 'apply_revision'), payload)
            if not result['valid']:
                raise ValueError(dumps(result['issues']))
            def commit(current):
                item = active_reply(current)
                if not item or item['id'] != reply['id']:
                    raise Conflict('这条回复已处理，请查看当前版本')
                current.setdefault('history', []).append(result)
                current.update(revision=result['revision'], records=result['records'], reason=reply['text'],
                    approval=None, validation=None, export=None, auto_review=None, review_confirmation=None,
                    confidence_interrupt=None, status='processing')
                if 'accounting_entity' in proposal:
                    current['accounting_entity'] = proposal['accounting_entity']
                current.update(function(self.cap, 'human-review', 'prepare_recalculation')(
                    {'task': current, 'review': result}))
                item.update(state='completed', applied_revision=current['revision'], completed_at=now())
                if current.get('feedback'):
                    current['feedback'].update(state='completed', model_seen=True)
            task = await asyncio.to_thread(repository().mutate, 'task', self.task_id, commit,
                                           expected_revision=self.revision)
            await asyncio.to_thread(reconcile_saved, self.task_id)
            task = await asyncio.to_thread(settle_saved, self.task_id)
            await asyncio.to_thread(repository().event, self.task_id, 'human_revision',
                                    revision=task['revision'], reason=reply['text'], reply_id=reply['id'])
            confidence = (task.get('validation') or {}).get('confidence') or {}
            score = confidence.get('review_score', confidence.get('score'))
            note = ('已有字段置信度暂不可评估。' if score is None else
                    f'已有字段置信度 {score:g}/100（规则支持指标）。')
            validation = task.get('validation') or {}
            errors = [issue for issue in validation.get('issues', [])
                      if issue.get('severity') == 'error']
            if not validation.get('ok'):
                note = (f'整单校验未通过（{len(errors)} 项错误）；' + note)
            items = confidence.get('review_items') or []
            if items:
                note += f'仍有 {len(items)} 个字段的依据需要关注。'
            gaps = list(dict.fromkeys(issue['message'] for issue in (task.get('validation') or {}).get('issues', [])
                                     if issue.get('field') == 'posting_type' and issue.get('message')))
            if gaps:
                note += 'AR/AP尚未确定：' + '；'.join(gaps) + '。请说明当前主体在这笔费用中是收款方还是付款方，或补充双方关系。'
            if (reply.get('conversational') and reply.get('interrupt_id')
                    and not proposal.get('resolves_pending')):
                return await self.keep_question(reply, task['revision'])
            if completion_question(task):
                return await self.clarify_completion(task)
            return {'messages': [AIMessage(content=f'已按您的回复更新至第 {task["revision"]} 版，并重新核对费用。{note}请在下方查看结果与原文。',
                id='reply-result-' + reply['id'])]}
        if proposal['action'] == 'confirm':
            task = await asyncio.to_thread(settle_saved, self.task_id, confirmation=dict(
                expected_revision=self.revision, decision='confirm', reason=reply['text']))
        def complete(current):
            item = active_reply(current)
            if item and item['id'] == reply['id']:
                item.update(state='completed', completed_at=now())
            if proposal['action'] == 'defer':
                current['status'] = 'review_deferred'
        await asyncio.to_thread(repository().mutate, 'task', self.task_id, complete,
                                expected_revision=self.revision)
        await self.flush()
        if reply.get('kind') == 'chat' and proposal['action'] == 'answer':
            # A question about an existing bill does not reopen validation or
            # change its business completion/approval state.
            return
        if (reply.get('conversational') and reply.get('interrupt_id')
                and proposal['action'] == 'answer' and not proposal.get('resolves_pending')):
            return await self.keep_question(reply, self.revision)
        if proposal['action'] != 'defer':
            return await self.clarify_completion()
