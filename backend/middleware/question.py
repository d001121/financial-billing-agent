"""Deterministic boundary for user questions: no candidate, no question."""

import asyncio

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import ToolMessage

from backend.infrastructure.repository import repository


class AskUserPolicy(AgentMiddleware):
    """Keep the business artifact independent of unanswered UI questions."""

    def __init__(self, task_id):
        self.task_id = task_id

    async def awrap_tool_call(self, request, handler):
        if request.tool_call.get('name') != 'ask_user' or not self.task_id:
            return await handler(request)
        try:
            task = await asyncio.to_thread(repository().get, 'task', self.task_id)
        except Exception:
            return await handler(request)
        call_id = request.tool_call.get('id')
        if not str(task.get('accounting_entity') or '').strip():
            return ToolMessage(
                content='调用方没有提供记账主体：先保存费用候选，不要用 ask_user 在提取阶段阻塞；'
                        '保存后宿主会打开 conversation_review 主体核对，调用方在聊天中回复后'
                        '由 human-review Skill 应用。',
                tool_call_id=call_id, name='ask_user', status='error',
            )
        if not task.get('records'):
            return ToolMessage(
                content='当前还没有已保存的费用候选。请先调用 save_document_extraction 保存候选，'
                        '保存成功后才能向用户提问。',
                tool_call_id=call_id, name='ask_user', status='error',
            )
        return await handler(request)
