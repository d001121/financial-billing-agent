"""Turn a malformed tool call back into a model correction instead of ending.

LangChain records a tool call whose arguments are not valid JSON as an
``InvalidToolCall``.  Its factory helper only patches calls that carry an id;
models frequently emit such calls with an empty id, so the model never sees an
error and the agent loop ends with no result.  This middleware adds a bounded
correction round.
"""

import json
from dataclasses import replace
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain.agents.middleware.types import ModelResponse
from langchain.messages import AIMessage, HumanMessage


class InvalidToolCallRecovery(AgentMiddleware):
    marker = '[tool-call-recovery]'

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    @hook_config(can_jump_to=['model'])
    def after_model(self, state, runtime):
        messages = state.get('messages') or []
        if not messages:
            return None
        invalid = getattr(messages[-1], 'invalid_tool_calls', None)
        if not invalid:
            return None
        used = sum(
            1 for message in messages
            if isinstance(message, HumanMessage) and isinstance(message.content, str)
            and message.content.startswith(self.marker)
        )
        if used >= self.max_retries:
            return None
        details = []
        for call in invalid:
            name = call.get('name') or 'unknown'
            error = call.get('error') or 'arguments are not valid JSON'
            args = call.get('args')
            position = ''
            if isinstance(args, str):
                try:
                    json.loads(args)
                except ValueError as exc:
                    position = f'，第 {exc.pos} 字符'
            details.append(f'{name}: {error}{position}')
        return {
            'messages': [HumanMessage(content=(
                f'{self.marker} 上一轮工具调用未执行：' + '；'.join(details) +
                '。请重新发起该调用并输出合法 JSON。若单次载荷过大，先只保存 charges，'
                'documents 和 source_links 分次保存。'))],
            'jump_to': 'model',
        }


class ToolArgNormalization(AgentMiddleware):
    """Decode JSON strings passed where the tool schema expects an object/array.

    Models frequently double-encode `result` or `todos` as a JSON string.  The
    tool node would only report a validation error, and smaller models tend to
    repeat the same call.  Normalizing the top-level arguments keeps the run
    moving without weakening the tool schema.
    """

    async def awrap_tool_call(self, request, handler):
        tool = getattr(request, 'tool', None)
        args = request.tool_call.get('args') or {}
        properties = {}
        schema = getattr(tool, 'tool_call_schema', None) or getattr(tool, 'args_schema', None)
        if schema is not None:
            try:
                properties = schema.model_json_schema().get('properties', {})
            except Exception:
                properties = {}
        normalized = dict(args)
        changed = False
        for key, value in args.items():
            if not isinstance(value, str) or not value or value[0] not in '[{':
                continue
            spec = properties.get(key) or {}
            types = {spec.get('type')}
            types.update(item.get('type') for item in (spec.get('anyOf') or [])
                         if isinstance(item, dict))
            if not types & {'object', 'array'}:
                continue
            try:
                parsed = json.loads(value)
            except ValueError:
                continue
            if isinstance(parsed, (dict, list)):
                normalized[key] = parsed
                changed = True
        if changed:
            request = request.override(tool_call={**request.tool_call, 'args': normalized})
        return await handler(request)


class ToolCallIdNormalization(AgentMiddleware):
    """Give empty tool-call ids a synthetic id before the tool node runs.

    Some OpenAI-compatible models emit tool calls with an empty id. Normal
    tools tolerate it, but subagent delegation requires a truthy id and fails
    with "Tool call ID is required for subagent invocation".  Normalizing the
    model response keeps the AIMessage and its ToolMessages consistent.
    """

    async def awrap_model_call(self, request, handler):
        result = await handler(request)
        if not isinstance(result, ModelResponse):
            return result
        messages = []
        for message in result.result:
            if isinstance(message, AIMessage) and any(not c.get('id') for c in message.tool_calls):
                message = message.model_copy(update={'tool_calls': [
                    c if c.get('id') else {**c, 'id': 'call-' + uuid4().hex}
                    for c in message.tool_calls]})
            messages.append(message)
        return replace(result, result=messages)
