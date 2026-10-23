"""Record task status after the native Agent finishes its current run."""

import asyncio
import json

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain.messages import HumanMessage, SystemMessage, ToolMessage

from backend.infrastructure.repository import dumps, repository
from backend.tools.review import finalize_with_review
from backend.tools.artifacts import verification_summary
from backend.harness.feedback import feedback_context, pending_feedback
from backend.harness.stopping import active_stop


class TaskOutcome(AgentMiddleware):
    def __init__(self, task_id, revision=None):
        self.task_id, self.revision = task_id, revision

    def return_verification(self, task, state):
        """Like a stop-hook observation: let the native loop see an unseen check."""
        if active_stop(task) or task['capability']['config']['runtime'].get('agent_style') != 'codex':
            return
        messages = state.get('messages', [])
        start = next((i for i in range(len(messages) - 1, -1, -1)
                      if isinstance(messages[i], HumanMessage)), 0)
        for message in reversed(messages[start:]):
            if not isinstance(message, ToolMessage) or message.status == 'error':
                continue
            write = message.name in ('save_document_extraction', 'reconcile_task_charges', 'link_task_evidence')
            if not write and message.name != 'prepare_export':
                continue
            result = message.artifact
            if not isinstance(result, dict):
                try:
                    result = json.loads(message.content)
                except (ValueError, TypeError):
                    if write:
                        break
                    continue
            if not isinstance(result, dict):
                if write:
                    break
                continue
            if result.get('revision') == task['revision'] and result.get('verification'):
                return
            # A later write without a check invalidates an earlier receipt,
            # including writes within the same business revision.
            if write:
                break
        return {'jump_to': 'model', 'messages': [SystemMessage(content=
            '当前版本最终核验已返回主控，请根据真实回执决定是否仍需补读、修正、委派或如实结束。'
            '不要重复已完成的检查；直接说明结果、置信度与缺口，无需更新计划。\n' + dumps(dict(
                status=task['status'], verification=verification_summary(task.get('validation') or {}),
                feedback=feedback_context(task) if task.get('feedback') else None,
                issues=(task.get('validation') or {}).get('issues', [])[:12])))]}

    async def flush(self):
        repo = repository()
        if hasattr(repo, 'flush'):
            await asyncio.to_thread(repo.flush, self.task_id)

    @hook_config(can_jump_to=['model'])
    async def aafter_agent(self, state, runtime):
        if self.task_id:
            current = await asyncio.to_thread(repository().get, 'task', self.task_id)
            revision = self.revision if self.revision is not None else current['revision']
            if current['revision'] != revision:
                return
            if active_stop(current):
                # No model reentry after a real stop. Reconcile exactly the
                # retained candidates before deterministic validation/export.
                from backend.tools.artifacts import reconcile_saved
                if current.get('charges'):
                    await asyncio.to_thread(reconcile_saved, self.task_id)
                from backend.tools.review import settle_saved
                await asyncio.to_thread(settle_saved, self.task_id)
                await self.flush()
                return
            # A failed human reply is a terminal boundary for this run; do not
            # finalize and bounce back to the model with the full toolset.
            latest_reply = (current.get('conversation') or [None])[-1]
            latest_input = next((m for m in reversed(state.get('messages', []))
                                 if isinstance(m, HumanMessage)), None)
            last_response = (state.get('messages') or [None])[-1]
            if (latest_reply and latest_reply.get('conversational')
                    and latest_reply.get('state') == 'completed'
                    and latest_reply.get('response_message_id')
                    and latest_reply['response_message_id'] == getattr(last_response, 'id', None)
                    and (latest_reply.get('proposal') or {}).get('action', 'answer') == 'answer'):
                return  # The current question was answered; an old todo is not a new run goal.
            if (latest_reply and latest_reply.get('kind') == 'chat'
                    and latest_reply.get('state') == 'completed'
                    and latest_input and latest_input.id == 'chat-user-' + latest_reply['id']
                    and (latest_reply.get('proposal') or {}).get('action', 'answer') == 'answer'):
                return
            if (latest_reply and latest_reply.get('revision') == current['revision']
                    and (latest_reply.get('state') == 'failed'
                         or latest_reply.get('decision_error'))):
                return
            # ConversationReplies has already committed and revalidated a
            # human edit.  Codex-style turns must close at that deterministic
            # boundary; sending the same reply back to the model only invites
            # a second extraction/revision cycle.  A newly pending native
            # question is the one deliberate exception.
            latest_human = next((item for item in reversed(current.get('conversation') or [])
                                 if item.get('state') == 'completed'
                                 and item.get('applied_revision') == current['revision']), None)
            review_request = current.get('review_request') or {}
            pending_review = (review_request.get('state') == 'pending'
                              and review_request.get('revision') == current['revision'])
            # ConversationReplies already committed and revalidated this human
            # edit (settle_saved).  Bouncing back to the model here would hand
            # it the full toolset again and restart the bill, so close the
            # turn at this deterministic boundary even when the final export
            # is not produced (for example completed_with_gaps).
            if (latest_human and not pending_review
                    and current.get('status') in ('completed', 'completed_with_gaps', 'review_deferred')):
                return
            if pending_feedback(current):
                def complete(task):
                    feedback = task['feedback']
                    feedback['state'] = 'completed' if feedback.get('model_seen') else 'incomplete'
                    if not feedback.get('model_seen'):
                        task.update(status='incomplete', auto_review=None,
                            summary='修改已保存，本轮尚未由智能体处理人工反馈，可继续任务')
                current = await asyncio.to_thread(repository().mutate, 'task', self.task_id, complete,
                                                   expected_revision=revision)
                await self.flush()
                if current['feedback']['state'] == 'incomplete':
                    return
                # Revalidate after the feedback turn even when a return_direct
                # tool has already published its draft.
                current = await finalize_with_review(self.task_id)
                def settled(task):
                    task['feedback']['state'] = ('completed' if task.get('status') == 'completed'
                                                 else 'completed_with_gaps')
                await asyncio.to_thread(repository().mutate, 'task', self.task_id, settled,
                                        expected_revision=revision)
                await self.flush()
                return self.return_verification(current, state)
            needs_check = current.get('status') in ('queued', 'processing', 'running', 'starting', 'awaiting_review')
            changed_after_check = (current.get('status') in ('completed', 'completed_with_gaps')
                                   and current.get('export') is None)
            if current.get('records') and (needs_check or changed_after_check):
                current = await finalize_with_review(self.task_id)
                return self.return_verification(current, state)
            def update(task):
                if task.get('status') in ('queued', 'processing', 'running'):
                    task['status'] = 'incomplete'
                    task['summary'] = '本轮未形成完整账单结果，已保存现有材料与提取内容'
            await asyncio.to_thread(repository().mutate, 'task', self.task_id, update,
                                    expected_revision=revision)
            await self.flush()
