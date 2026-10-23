"""Inject current feedback using native ModelRequest overrides, including resumes."""
import asyncio

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import SystemMessage

from backend.harness.feedback import feedback_message, pending_feedback
from backend.infrastructure.repository import repository


class RevisionFeedback(AgentMiddleware):
    def __init__(self, task_id, revision):
        self.task_id, self.revision = task_id, revision

    async def awrap_model_call(self, request, handler):
        if not self.task_id:
            return await handler(request)
        repo = repository()
        read = (lambda: repo.get_fields('task', self.task_id, ['feedback', 'accounting_entity'])) \
            if hasattr(repo, 'get_fields') else (lambda: repo.get('task', self.task_id))
        task = await asyncio.to_thread(read)
        if not pending_feedback(task) or task['revision'] != self.revision:
            return await handler(request)
        content = (list(request.system_message.content_blocks) if request.system_message else []) + [
            {'type': 'text', 'text': feedback_message(task)}]
        result = await handler(request.override(system_message=SystemMessage(content=content)))
        # Failed calls do not count as having processed human input.
        def observed(current):
            if (current.get('feedback') or {}).get('revision') == self.revision:
                current['feedback']['model_seen'] = True
        if hasattr(repo, 'mutate_fields'):
            await asyncio.to_thread(repo.mutate_fields, 'task', self.task_id, ['feedback'], observed,
                                    expected_revision=self.revision)
        else:
            await asyncio.to_thread(repo.mutate, 'task', self.task_id, observed,
                                    expected_revision=self.revision)
        return result
