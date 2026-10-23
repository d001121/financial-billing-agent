"""Official checkpointer conformance and native approval resume after reopening.

Docs MCP: /langsmith/custom-checkpointer and
/oss/python/langchain/human-in-the-loop. Reference MCP: AsyncSqliteSaver and
HumanInTheLoopMiddleware. Verified combination: sqlite saver 3.1.2,
conformance 0.0.2, LangChain 1.4.6 and LangGraph 1.2.16.
The saver and agent loop are official implementations; all databases are temporary.
"""
import asyncio
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.messages import ToolMessage
from langchain.tools import tool
from langgraph.checkpoint.conformance import checkpointer_test, validate
from langgraph.checkpoint.conformance.capabilities import BASE_CAPABILITIES
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from test_host import offline_model, proposed_call


def test_official_sqlite_required_base_conformance(tmp_path):
    """Run the package's complete required suite, with no skipped base operation."""
    @checkpointer_test(name='AsyncSqliteSaver-3.1.2')
    async def sqlite_saver():
        database = tmp_path / f'conformance-{uuid4().hex}.sqlite'
        async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
            await saver.setup()
            yield saver

    report = asyncio.run(validate(sqlite_saver,
        capabilities={cap.value for cap in BASE_CAPABILITIES}))
    result = report.to_dict()
    result['validation_scope'] = 'All required base capabilities; optional server extensions are unavailable'
    result['tested_capabilities'] = sorted(cap.value for cap in BASE_CAPABILITIES)
    result['versions'] = {name: version(name) for name in (
        'langgraph-checkpoint-sqlite', 'langgraph-checkpoint-conformance',
        'langchain', 'langgraph')}
    report_path = Path(__file__).parent / 'reports' / 'sqlite-conformance.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    assert report.passed_all_base(), result
    for capability in BASE_CAPABILITIES:
        assert result['results'][capability.value]['tests_failed'] == 0
        assert result['results'][capability.value]['tests_skipped'] == 0


def test_native_hitl_survives_closed_reopened_sqlite_without_replaying_tools(monkeypatch, tmp_path):
    """Rebuild the same official agent over an reopened database, then approve."""
    database = tmp_path / 'approval.sqlite'
    receipts = tmp_path / 'tool-receipts.jsonl'
    config = {'configurable': {'thread_id': 'persistent-approval-test'}}
    model_requests = []

    def save_receipt(name):
        with receipts.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'tool': name}) + '\n')

    @tool
    def inspect_original() -> str:
        """Read the original document and retain its observable execution receipt."""
        save_receipt('inspect_original')
        return 'Original document inspected'

    @tool
    def approve_export() -> str:
        """Finish the reviewed export after explicit human approval."""
        save_receipt('approve_export')
        return 'Approved export prepared'

    def respond(body):
        model_requests.append(body)
        completed = {message.get('content') for message in body['messages']
                     if message['role'] == 'tool'}
        if 'Original document inspected' not in completed:
            return proposed_call('inspect_original', {}, 'original-once')
        if 'Approved export prepared' not in completed:
            return proposed_call('approve_export', {}, 'reviewed-once')
        return {'role': 'assistant', 'content': '已恢复并完成审批'}

    async def exercise():
        model, client = offline_model(monkeypatch, None, respond)

        def assemble(saver):
            return create_agent(model, tools=[inspect_original, approve_export],
                middleware=[HumanInTheLoopMiddleware(
                    interrupt_on={'approve_export': {'allowed_decisions': ['approve', 'reject']}},
                    interrupt_mode='per_call')], checkpointer=saver)

        try:
            async with AsyncSqliteSaver.from_conn_string(str(database)) as saver:
                await saver.setup()
                agent = assemble(saver)
                paused = await agent.ainvoke({'messages': [{'role': 'user',
                    'content': '先核对原件，再等待审批导出'}]}, config=config)
                pending = paused['__interrupt__']
                assert len(pending) == 1 and pending[0].value['name'] == 'approve_export'
                interrupt_id = pending[0].id
                assert receipts.read_text(encoding='utf-8').count('inspect_original') == 1
                assert 'approve_export' not in receipts.read_text(encoding='utf-8')

            # The first connection is closed. The graph is rebuilt using the
            # same thread and tools, without passing old state back as input.
            async with AsyncSqliteSaver.from_conn_string(str(database)) as reopened:
                await reopened.setup()
                resumed_agent = assemble(reopened)
                snapshot = await resumed_agent.aget_state(config)
                assert len(snapshot.interrupts) == 1
                assert snapshot.interrupts[0].id == interrupt_id
                previous_tools = [m for m in snapshot.values['messages'] if isinstance(m, ToolMessage)]
                assert [m.name for m in previous_tools] == ['inspect_original']
                finished = await resumed_agent.ainvoke(
                    Command(resume={interrupt_id: {'type': 'approve'}}), config=config)
                assert not finished.get('__interrupt__')
                assert not (await resumed_agent.aget_state(config)).interrupts
                assert finished['messages'][-1].content == '已恢复并完成审批'
        finally:
            await client.aclose()

    asyncio.run(asyncio.wait_for(exercise(), timeout=15))
    calls = [json.loads(line)['tool'] for line in receipts.read_text(encoding='utf-8').splitlines()]
    assert calls == ['inspect_original', 'approve_export']
    assert len(model_requests) == 3
