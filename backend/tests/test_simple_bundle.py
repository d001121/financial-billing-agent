"""Small native-loop regressions with synthetic files and mocked model HTTP."""
import asyncio
import json

from deepagents.backends import StateBackend
from langchain.messages import ToolMessage
import pytest

from backend.agents.supervisor.agent import build_supervisor
from backend.extensions.skill_versions import skill_module, skill_state
from backend.middleware.assembly import base_stack
from backend.tools.skill_bindings import tools_for
from backend.tests.test_host import host, offline_model, proposed_call


@pytest.mark.parametrize('wrong_amount', [False, True])
def test_files_stay_separate_and_checked_save_needs_no_export_round(host, monkeypatch, wrong_amount):
    repo, _, task = host
    sources = [dict(source_id='invoice-a', format='text', status='ready', blocks=[dict(
        anchor='text', text='Invoice INV-A\nClient pay Carrier: THC USD 100')]),
        dict(source_id='invoice-b', format='text', status='ready', blocks=[dict(
            anchor='text', text='Invoice INV-B\nClient pay Carrier: Handling Charge 50')])]
    repo.mutate('task', 'task-1', lambda t: t.update(status='running', sources=sources,
        charges=[], records=[], chunks=[], coverage=[], extraction=None))
    cap = task['capability']
    module = skill_module('document-extraction', cap['version'])
    refs = module.citation_index(dict(sources=sources))
    calls = []

    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return proposed_call('read_materials', {}, 'read-both')
        if len(calls) == 2:
            reading = json.loads(body['messages'][-1]['content'])
            assert {row['source_id'] for row in reading['content']} == {'invoice-a', 'invoice-b'}
            charges = []
            for source, name, amount, currency in [
                    ('invoice-a', 'THC', 90 if wrong_amount else 100, 'USD'),
                    ('invoice-b', 'Handling Charge', 50, None)]:
                header = next(k for k, r in refs.items() if r['source_id'] == source and r['quote'].startswith('Invoice'))
                fee = next(k for k, r in refs.items() if r['source_id'] == source and name in r['quote'])
                fields = ['charge_item', 'amount', 'creditor', 'debtor'] + (['currency'] if currency else [])
                charges.append(dict(charge_id=source, source_id=source, document_id=source,
                    line_id='fee', reference_no='INV-A' if source == 'invoice-a' else 'INV-B',
                    charge_item=name, amount=amount, currency=currency, creditor='Carrier', debtor='Client',
                    evidence=[dict(ref_id=fee, fields=fields), dict(ref_id=header, fields=['reference_no'])]))
            return proposed_call('save_document_extraction', dict(result=dict(charges=charges)), 'save-both')
        assert len(calls) == 3, 'A checked save must not require another finalization model round'
        receipt = json.loads(body['messages'][-1]['content'])
        assert receipt['record_count'] == 2 and receipt['verification']['ok'] is False
        return dict(role='assistant', content='两张单据已分别保存；第二张未提供币种，保留缺口。')

    async def run():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            backend = StateBackend()
            common, business = tools_for('task-1', cap)
            graph = build_supervisor(model, common, backend,
                base_stack('task-1', 1, cap, backend, business, outcome=True), [])
            return await graph.ainvoke({**skill_state(cap, repo.get('task', 'task-1')),
                'messages': [dict(role='user', content='对照两个文件，提取费用，缺失留空')]})
        finally:
            await http.aclose()

    result = asyncio.run(run())
    saved = repo.get('task', 'task-1')
    records = {r['document_info']['reference_no']: r for r in saved['records']}
    assert set(records) == {'INV-A', 'INV-B'}
    assert records['INV-A']['charge_details']['amount'] == (90 if wrong_amount else 100)
    assert records['INV-A']['charge_details']['currency'] == 'USD'
    assert records['INV-B']['charge_details']['amount'] == 50
    assert records['INV-B']['charge_details']['currency'] is None
    assert all(r['financial_attributes']['posting_type'] == 'AP' for r in records.values())
    assert all(r['charge_details']['payment_term'] is None for r in records.values())
    assert saved['sources'] == sources and saved['approval'] is None
    assert saved['status'] == 'completed_with_gaps' and saved['validation']['ok'] is False
    assert saved['export'] and len(saved['export']['records']) == 2
    if wrong_amount:
        assert any(i.get('field') == 'amount' and i.get('severity') == 'error'
                   for i in saved['validation']['issues'])
    assert len(calls) == saved['usage']['model_calls'] == 3
    assert [m.name for m in result['messages'] if isinstance(m, ToolMessage)] == [
        'read_materials', 'save_document_extraction']


def test_expert_save_remains_a_staging_operation(host):
    _, _, task = host
    cap = task['capability']
    _, business = tools_for('task-1', cap, ['document-extraction'])
    save = next(t for t in business if t.name == 'save_document_extraction')
    assert save.tool_call_schema.model_json_schema()['properties']['finalize']['default'] is False


def test_explicit_staging_invalidates_validation_without_running_financial_checks(host):
    repo, _, task = host
    _, business = tools_for('task-1', task['capability'])
    save = next(t for t in business if t.name == 'save_document_extraction')
    result = save.invoke(dict(result=task['extraction'], finalize=False))
    assert result['saved'] and 'verification' not in result
    assert repo.get('task', 'task-1')['validation'] is None


def test_reconciliation_of_an_existing_candidate_can_finish_after_its_receipt(host, monkeypatch):
    repo, _, task = host
    def arrange(current):
        current['status'] = 'running'
        current['charges'][0]['amount'] = 90  # Contradicts the original 100.
    repo.mutate('task', 'task-1', arrange)
    calls = []
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return proposed_call('reconcile_task_charges', {}, 'check-existing')
        assert len(calls) == 2
        assert body['messages'][-1]['content'].startswith('{'), body['messages'][-1]['content']
        receipt = json.loads(body['messages'][-1]['content'])
        assert receipt['verification']['ok'] is False
        assert receipt['verification']['review_items']
        return dict(role='assistant', content='原文金额与候选矛盾，保留错误供核对。')
    async def run():
        model, http = offline_model(monkeypatch, 'task-1', respond)
        try:
            cap = task['capability']
            backend = StateBackend()
            common, business = tools_for('task-1', cap)
            graph = build_supervisor(model, common, backend,
                base_stack('task-1', 1, cap, backend, business, outcome=True), [])
            initial = skill_state(cap, repo.get('task', 'task-1'))
            initial['pinned_skills'].append('billing-reconciliation')
            return await graph.ainvoke({**initial,
                'messages': [dict(role='user', content='核对现有候选，不补填字段')]})
        finally:
            await http.aclose()
    result = asyncio.run(run())
    saved = repo.get('task', 'task-1')
    assert len(calls) == saved['usage']['model_calls'] == 2
    assert saved['status'] == 'completed_with_gaps' and saved['approval'] is None
    assert saved['validation']['ok'] is False and saved['export']
    assert [m.name for m in result['messages'] if isinstance(m, ToolMessage)] == ['reconcile_task_charges']
