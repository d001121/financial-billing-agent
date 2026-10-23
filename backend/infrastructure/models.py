"""One model factory, including Deep Agent summarization requests."""
import os
import json
import asyncio
import ssl
import httpx
from langchain_openai import ChatOpenAI

from backend.harness.budget import consume
from backend.harness.dispatch import PolicyDenied

TLS_CONTEXT = ssl.create_default_context()


def make_model(task_id=None, runtime=None, request_guard=None, *, budget_scope=None):
    runtime = runtime or {}

    async def before_send(request):
        if request.method == 'POST' and '/chat/completions' in request.url.path:
            body = json.loads(request.content)
            if body.get('enable_thinking') is not False:
                raise PolicyDenied('模型请求未明确关闭思考，已拦截')
            if request_guard is not None:
                await asyncio.to_thread(request_guard)
            await asyncio.to_thread(consume, task_id, 'model_calls', scope=budget_scope)

    client = httpx.AsyncClient(event_hooks={'request': [before_send]}, verify=TLS_CONTEXT,
                              timeout=runtime.get('model_timeout', 120))
    model = ChatOpenAI(model=os.environ['LLM_MODEL_NAME'], api_key=os.environ['LLM_API_KEY'],
                       base_url=os.environ['LLM_BASE_URL'], extra_body={'enable_thinking': False},
                       temperature=0, max_tokens=runtime.get('max_tokens', 10000),
                       max_retries=0, http_async_client=client, timeout=runtime.get('model_timeout', 120))
    return model, client
