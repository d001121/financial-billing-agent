"""Deterministic model/tools for an isolated real Agent Server, never business data.

Run using the temporary config described in agent-activity-streaming.md.
Only the model and material are fixtures; create_agent, server, SSE and Vue are real.
"""
import asyncio
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool


class ActivityFixtureModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

    def _stream(self, *args, **kwargs):
        for chunk in super()._stream(*args, **kwargs):
            time.sleep(0.12)
            yield chunk


@tool
async def read_material(file_path: str) -> str:
    """Read a synthetic material without accessing disk or external services."""
    await asyncio.sleep(3)
    return 'Synthetic material: Handling Fee 50 USD; reference TEST-001.'


@tool
async def compare_fields(reference_no: str) -> str:
    """Compare synthetic fields without touching any financial records."""
    await asyncio.sleep(3)
    return 'Synthetic comparison complete: TEST-001 / 50 USD.'


def make_graph():
    def call(text, name, arguments, call_id):
        return AIMessage(content=text, additional_kwargs={'tool_calls': [
            {'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': arguments}},
        ]})
    model = ActivityFixtureModel(messages=iter([
        call('正在读取 合成材料。', 'read_material', '{"file_path":"synthetic.md"}', 'fixture-read'),
        call('已读取材料， 正在交叉核对 字段。', 'compare_fields', '{"reference_no":"TEST-001"}', 'fixture-compare'),
        '合成验证完成： 编号 TEST-001， 金额 50 USD。',
    ]))
    return create_agent(model=model, tools=[read_material, compare_fields])


app = FastAPI()
app.mount('/app', StaticFiles(directory=Path(__file__).resolve().parents[3] / 'frontend' / 'dist', html=True))
